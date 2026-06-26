"""Steps API router — execution control and status queries."""

import asyncio
from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.config import settings
from src.database import get_db, async_session_factory
from src.models.project import Project
from src.models.step import Step
from src.models.template import Template
from src.models.generation_result import GenerationResult
from src.models.operation_log import OperationLog
from src.schemas.step import (
    StepResponse,
    StepListResponse,
    StepExecuteRequest,
    StepExecuteResponse,
    StepKillResponse,
    ComfyuiResultInStep,
)
from src.services.config_sync import ConfigSyncService
from src.services.vimax_runner import vimax_runner
from src.services.generation_monitor import monitor_generations_realtime
from src.services.progress_manager import (
    get_template_progress,
    get_active_steps,
    get_next_step_name,
    is_last_step,
)

router = APIRouter(prefix="/api/projects", tags=["steps"])


@router.get("/{project_id}/steps", response_model=StepListResponse)
async def list_steps(project_id: int, db: AsyncSession = Depends(get_db)):
    """Get all steps for a project with nested ComfyUI results."""
    result = await db.execute(
        select(Step)
        .options(selectinload(Step.generation_results))
        .where(Step.project_id == project_id)
        .order_by(Step.step_order)
    )
    steps = result.scalars().all()

    step_responses = []
    for s in steps:
        comfyui = []
        for gr in (s.generation_results or []):
            comfyui.append(
                ComfyuiResultInStep(
                    id=gr.id,
                    file_path=gr.file_path,
                    thumbnail_path=gr.thumbnail_path,
                    prompt_id=gr.prompt_id,
                    generation_type=gr.generation_type,
                    duration_seconds=gr.duration_seconds,
                    confirmed=gr.confirmed,
                )
            )
        output_files = []
        if s.output_files:
            import json
            try:
                output_files = json.loads(s.output_files)
            except (json.JSONDecodeError, TypeError):
                pass

        step_responses.append(
            StepResponse(
                id=s.id,
                name=s.name,
                step_order=s.step_order,
                status=s.status,
                started_at=s.started_at,
                completed_at=s.completed_at,
                duration_seconds=s.duration_seconds,
                output_files=output_files,
                retry_count=s.retry_count,
                error_message=s.error_message,
                comfyui_results=comfyui,
            )
        )

    return StepListResponse(steps=step_responses)


@router.post("/{project_id}/steps/execute", response_model=StepExecuteResponse, status_code=202)
async def execute_steps(project_id: int, body: StepExecuteRequest, background_tasks: BackgroundTasks, db: AsyncSession = Depends(get_db)):
    """Start, continue, or retry ViMax pipeline execution."""
    # Get project
    proj_result = await db.execute(select(Project).where(Project.id == project_id))
    project = proj_result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Get steps
    steps_result = await db.execute(
        select(Step).where(Step.project_id == project_id).order_by(Step.step_order)
    )
    steps = steps_result.scalars().all()

    if body.action == "start":
        if project.status == "running":
            raise HTTPException(status_code=409, detail="Project is already running")

        # ── Bidirectional config sync before launching ViMax ──
        # 1) VIMAX_ROOT/configs/ → its configured working_dir
        ConfigSyncService.sync_vimax_configs(settings.VIMAX_ROOT)
        # 2) current project working_dir → VIMAX_ROOT/configs/
        ConfigSyncService.sync_project_to_vimax(project.working_dir, settings.VIMAX_ROOT)

        # Auto-create steps from template if DB is empty (backfill)
        if not steps:
            if not project.template_id:
                raise HTTPException(status_code=400, detail="Project has no template — cannot infer steps")
            tmpl_result = await db.execute(select(Template).where(Template.id == project.template_id))
            template = tmpl_result.scalar_one_or_none()
            if not template:
                raise HTTPException(status_code=400, detail="Template not found")
            progress_steps = get_template_progress(template.directory_name)
            active = get_active_steps(progress_steps)
            if not active:
                raise HTTPException(status_code=400, detail="Template has no steps defined")
            for i, ps in enumerate(active):
                step_obj = Step(project_id=project_id, name=ps.name, step_order=i)
                db.add(step_obj)
            await db.commit()
            # Re-fetch steps after creation
            steps_result = await db.execute(
                select(Step).where(Step.project_id == project_id).order_by(Step.step_order)
            )
            steps = steps_result.scalars().all()

        target_step = steps[0]
        interrupt_step = target_step.name

    elif body.action == "continue":
        if project.status != "running":
            raise HTTPException(status_code=400, detail="Project is not running")

        # ── Bidirectional config sync before continuing ──
        # 1) VIMAX_ROOT/configs/ → its configured working_dir
        ConfigSyncService.sync_vimax_configs(settings.VIMAX_ROOT)
        # 2) current project working_dir → VIMAX_ROOT/configs/
        ConfigSyncService.sync_project_to_vimax(project.working_dir, settings.VIMAX_ROOT)

        # Mark current step as fully_complete
        for s in steps:
            if s.status == "running":
                s.status = "fully_complete"
                s.completed_at = datetime.utcnow()
        await db.commit()

        # Use template progress enum to find next step name
        if not project.template_id:
            raise HTTPException(status_code=400, detail="Project has no template")
        tmpl_result = await db.execute(select(Template).where(Template.id == project.template_id))
        template = tmpl_result.scalar_one_or_none()
        if not template:
            raise HTTPException(status_code=400, detail="Template not found")

        progress_steps = get_template_progress(template.directory_name)
        next_name = get_next_step_name(progress_steps, project.current_step_name)

        if next_name is None or is_last_step(progress_steps, project.current_step_name):
            # All done
            project.status = "completed"
            project.completed_at = datetime.utcnow()
            await db.commit()
            return StepExecuteResponse(
                project_id=project.id,
                status="completed",
                current_step_name="",
                message="All steps completed",
            )

        # Find the next step in DB
        target_step = None
        for s in steps:
            if s.name == next_name:
                target_step = s
                break
        if not target_step:
            raise HTTPException(status_code=500, detail=f"Step '{next_name}' not found in DB (template progress mismatch)")

        interrupt_step = target_step.name

    elif body.action == "retry_step":
        if not body.step_name:
            raise HTTPException(status_code=400, detail="step_name required for retry")
        target_step = None
        for s in steps:
            if s.name == body.step_name:
                target_step = s
                break
        if not target_step:
            raise HTTPException(status_code=404, detail=f"Step '{body.step_name}' not found")
        # Reset only the target step
        for s in steps:
            if s.name == body.step_name:
                s.status = "pending"
                s.started_at = None
                s.completed_at = None
                s.duration_seconds = None
                s.output_files = None
                s.retry_count = (s.retry_count or 0) + 1
                break
        await db.commit()
        interrupt_step = target_step.name

    else:
        raise HTTPException(status_code=400, detail=f"Invalid action: {body.action}")

    # Check another project is not running
    if vimax_runner.is_running and vimax_runner.current_project_id != project_id:
        raise HTTPException(status_code=409, detail="Another project is already running")

    # Update step status
    target_step.status = "running"
    target_step.started_at = datetime.utcnow()
    project.status = "running"
    project.current_step_name = target_step.name
    await db.commit()

    # Launch ViMax (fire and forget — errors surface via project status)
    try:
        await vimax_runner.start(
            project_id=project.id,
            working_dir=project.working_dir,
            interrupt_step=interrupt_step,
            vimax_root=settings.VIMAX_ROOT,
        )
    except RuntimeError as e:
        raise HTTPException(status_code=409, detail=str(e))

    # ── Shared stop event: completion monitor signals this when process exits ──
    gen_stop = asyncio.Event()

    async def _gen_monitor():
        await monitor_generations_realtime(
            project_id=project.id,
            working_dir=project.working_dir,
            stop_event=gen_stop,
        )

    async def _completion_monitor():
        import logging
        _log = logging.getLogger(__name__)
        _log.info("_completion_monitor: started for project %s, step %s", project.id, target_step.name)
        try:
            await vimax_runner.monitor_completion(
                project_id=project.id,
                session_factory=async_session_factory,
            )
            _log.info("_completion_monitor: completed normally for project %s", project.id)
        except Exception:
            _log.exception("_completion_monitor crashed for project %s", project.id)
        finally:
            gen_stop.set()  # signal generation monitor to stop

    # ── Run both monitors concurrently (BackgroundTasks runs sequentially!) ──
    async def _monitor_both():
        await asyncio.gather(_gen_monitor(), _completion_monitor())

    background_tasks.add_task(_monitor_both)
    import logging
    logging.getLogger(__name__).info(
        "execute_steps: scheduled concurrent monitors for project %s, step %s", project.id, target_step.name
    )

    # Record operation
    db.add(OperationLog(
        project_id=project.id,
        user_id=1,
        operation_type="regenerate_step" if body.action == "retry_step" else body.action,
        target_type="step",
        target_name=target_step.name,
        summary=f"Action: {body.action}, step: {target_step.name}",
    ))
    await db.commit()

    return StepExecuteResponse(
        project_id=project.id,
        status="running",
        current_step_name=target_step.name,
        message="ViMax process started",
    )


@router.post("/{project_id}/steps/kill", response_model=StepKillResponse)
async def kill_execution(project_id: int, db: AsyncSession = Depends(get_db)):
    """Force kill the running ViMax process."""
    proj_result = await db.execute(select(Project).where(Project.id == project_id))
    project = proj_result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    await vimax_runner.kill()

    # Update project and current step status
    project.status = "failed"
    project.error_message = "Execution killed by user"
    if project.current_step_name:
        step_result = await db.execute(
            select(Step).where(
                Step.project_id == project_id,
                Step.name == project.current_step_name,
            )
        )
        step = step_result.scalar_one_or_none()
        if step:
            step.status = "failed"
            step.completed_at = datetime.utcnow()
            step.error_message = "Execution killed by user"

    # Record operation
    db.add(OperationLog(
        project_id=project.id,
        user_id=1,
        operation_type="regenerate_step",
        target_type="step",
        target_name=project.current_step_name or "unknown",
        summary="Force killed ViMax process",
        error_message="Execution killed by user",
    ))
    await db.commit()

    return StepKillResponse(status="killed", message="ViMax process terminated")
