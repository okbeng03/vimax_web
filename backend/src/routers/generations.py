"""Generations API router — ComfyUI result management."""

import asyncio
import os
import re
import shutil
import uuid
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.config import settings
from src.database import get_db, async_session_factory
from src.models.project import Project
from src.models.step import Step
from src.models.generation_result import GenerationResult
from src.models.operation_log import OperationLog
from src.schemas.generation_result import (
    GenerationResultResponse,
    GenerationListResponse,
    GenerationsRetryRequest,
    GenerationsGachaRequest,
)
from src.services.comfyui_client import ComfyUIClient
from src.services.config_sync import ConfigSyncService
from src.services.vimax_runner import vimax_runner

router = APIRouter(prefix="/api/projects", tags=["generations"])

# Regex to extract scene/shot from file_path
_SCENE_SHOT_RE = re.compile(r"scene[_\s]*(\d+).*?shots?[_\s/]*(\d+)", re.IGNORECASE)
_SCENE_ONLY_RE = re.compile(r"scene[_\s]*(\d+)", re.IGNORECASE)
_SHOT_ONLY_RE = re.compile(r"shots?[_\s/]*(\d+)", re.IGNORECASE)

# Type ordering for scene_shot sort: images → frames → video → audio → others
_TYPE_ORDER: dict[str, int] = {
    "image": 0,
    "first_frame": 1,
    "last_frame": 2,
    "video": 3,
    "audio": 4,
}


def _compute_relative(file_path: str, working_dir: str) -> str:
    """Compute path relative to working_dir."""
    try:
        return str(Path(file_path).relative_to(working_dir))
    except ValueError:
        return file_path


def _cached_path(file_path: str, working_dir: str) -> Path:
    """Build a caches/ path with a short hash suffix to avoid overwrites on re-cancel."""
    rel = _compute_relative(file_path, working_dir)
    p = Path(rel)
    tag = uuid.uuid4().hex[:8]
    stem = f"{p.stem}_{tag}"
    return Path(working_dir) / "caches" / p.parent / f"{stem}{p.suffix}"


def _extract_scene_shot(file_path: str) -> tuple[int | None, int | None]:
    """Extract scene and shot numbers from a file path.
    
    Supports patterns like:
      - scene_1/shot_2/frame.png
      - scene_01_shot_02_output.mp4
      - scene1_shot2.png
    """
    path_lower = file_path.lower().replace("\\", "/")
    m = _SCENE_SHOT_RE.search(path_lower)
    if m:
        return int(m.group(1)), int(m.group(2))
    scene = _SCENE_ONLY_RE.search(path_lower)
    shot = _SHOT_ONLY_RE.search(path_lower)
    return (int(scene.group(1)) if scene else None,
            int(shot.group(1)) if shot else None)


@router.get("/{project_id}/generations", response_model=GenerationListResponse)
async def list_generations(
    project_id: int,
    confirmed: bool | None = None,
    step_name: str | None = None,
    page: int = 1,
    page_size: int = 20,
    sort_by: str = Query(default="scene_shot", description="created_at | scene | shot | scene_shot"),
    sort_order: str = Query(default="desc", description="asc | desc"),
    db: AsyncSession = Depends(get_db),
):
    """List ComfyUI generation results with filters and sorting."""
    # Get project for relative path computation
    proj_result = await db.execute(select(Project).where(Project.id == project_id))
    project = proj_result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    working_dir = project.working_dir

    query = select(GenerationResult).where(GenerationResult.project_id == project_id)
    if confirmed is not None:
        query = query.where(GenerationResult.confirmed == confirmed)
    if step_name:
        query = query.join(GenerationResult.step).where(GenerationResult.step.has(name=step_name))

    # Total count (including step_name filter)
    count_query = select(func.count()).select_from(GenerationResult).where(GenerationResult.project_id == project_id)
    if confirmed is not None:
        count_query = count_query.where(GenerationResult.confirmed == confirmed)
    if step_name:
        count_query = count_query.join(GenerationResult.step).where(GenerationResult.step.has(name=step_name))
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # Unconfirmed count
    unconfirmed_query = select(func.count()).select_from(GenerationResult).where(
        and_(GenerationResult.project_id == project_id, GenerationResult.confirmed == False)
    )
    u_result = await db.execute(unconfirmed_query)
    unconfirmed_count = u_result.scalar() or 0

    # Fetch all matching (we'll sort and paginate in Python for custom sort fields)
    query = query.options(selectinload(GenerationResult.step)).order_by(GenerationResult.created_at.desc())
    result = await db.execute(query)
    all_generations = result.scalars().all()

    # Build response items with scene/shot extracted
    items: list[GenerationResultResponse] = []
    for g in all_generations:
        storage = g.storage_path or g.file_path
        cancelled = "caches" in storage
        scene_num, shot_num = _extract_scene_shot(g.file_path)
        items.append(GenerationResultResponse(
            id=g.id,
            step_name=g.step.name if g.step else None,
            file_path=g.file_path,
            relative_path=_compute_relative(storage, working_dir),
            storage_path=storage,
            original_relative_path=_compute_relative(g.file_path, working_dir),
            thumbnail_path=g.thumbnail_path,
            prompt_id=g.prompt_id,
            workflow_name=g.workflow_name,
            generation_type=g.generation_type,
            duration_seconds=g.duration_seconds,
            confirmed=g.confirmed,
            cancelled=cancelled,
            error_message=g.error_message,
            created_at=g.created_at,
            scene=scene_num,
            shot=shot_num,
        ))

    # Sort by custom fields
    reverse = sort_order == "desc"
    if sort_by == "scene_shot":
        items.sort(key=lambda x: (
            x.scene is None, x.scene or 0,
            x.shot is None, x.shot or 0,
            _TYPE_ORDER.get(x.generation_type, 99),
            x.id,
        ), reverse=reverse)
    elif sort_by == "scene":
        items.sort(key=lambda x: (x.scene is None, x.scene or 0, x.id), reverse=reverse)
    elif sort_by == "shot":
        items.sort(key=lambda x: (x.shot is None, x.shot or 0, x.id), reverse=reverse)
    else:
        items.sort(key=lambda x: x.created_at, reverse=reverse)

    # Paginate — scene-aware: one scene per page when sorted by scene
    if sort_by in ("scene_shot", "scene"):
        # Group by scene, each page = one complete scene
        scene_groups: list[list[GenerationResultResponse]] = []
        current_scene = None
        for item in items:
            if not scene_groups or item.scene != current_scene:
                scene_groups.append([])
                current_scene = item.scene
            scene_groups[-1].append(item)
        total_pages = len(scene_groups)
        p = max(1, min(page, total_pages)) if total_pages > 0 else 1
        paginated = scene_groups[p - 1] if scene_groups else []
    else:
        total_pages = (total + page_size - 1) // page_size
        start = (page - 1) * page_size
        paginated = items[start:start + page_size]

    return GenerationListResponse(
        generations=paginated, total=total, total_pages=total_pages, unconfirmed_count=unconfirmed_count,
    )


@router.post("/{project_id}/generations/{generation_id}/confirm")
async def confirm_generation(project_id: int, generation_id: int, db: AsyncSession = Depends(get_db)):
    """Confirm a generation result."""
    result = await db.execute(select(GenerationResult).where(GenerationResult.id == generation_id))
    gen = result.scalar_one_or_none()
    if not gen:
        raise HTTPException(status_code=404, detail="Generation result not found")
    gen.confirmed = True
    gen.confirmed_at = datetime.utcnow()
    db.add(OperationLog(
        project_id=project_id,
        user_id=1,
        operation_type="confirm_result",
        target_type="generation_result",
        target_id=generation_id,
        target_name=gen.file_path,
        summary=f"Confirmed generation result: {gen.prompt_id}",
    ))
    await db.commit()
    return {"status": "confirmed"}


@router.post("/{project_id}/generations/{generation_id}/cancel")
async def cancel_generation(project_id: int, generation_id: int, db: AsyncSession = Depends(get_db)):
    """Cancel (move to caches) a generation result. Works for both confirmed and unconfirmed results."""
    result = await db.execute(
        select(GenerationResult).options(selectinload(GenerationResult.project))
        .where(GenerationResult.id == generation_id)
    )
    gen = result.scalar_one_or_none()
    if not gen:
        raise HTTPException(status_code=404, detail="Generation result not found")

    project = gen.project
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Un-confirm if previously confirmed
    was_confirmed = gen.confirmed
    if gen.confirmed:
        gen.confirmed = False
        gen.confirmed_at = None

    current_path = gen.storage_path or gen.file_path
    src = Path(current_path)
    if not src.exists():
        raise HTTPException(status_code=404, detail=f"File not found: {current_path}")

    # Build caches target with hash suffix to avoid overwrites on re-cancel
    dst = _cached_path(gen.file_path, project.working_dir)
    dst.parent.mkdir(parents=True, exist_ok=True)

    # Move file
    shutil.move(str(src), str(dst))

    # Update storage_path to new location
    gen.storage_path = str(dst)

    # Compute readable relative path for log
    try:
        log_rel = str(dst.relative_to(project.working_dir))
    except ValueError:
        log_rel = str(dst)
    summary = f"Cancelled generation result: {gen.prompt_id}, moved to {log_rel}"
    if was_confirmed:
        summary = f"Un-confirmed & cancelled: {gen.prompt_id}, moved to {log_rel}"

    db.add(OperationLog(
        project_id=project_id,
        user_id=1,
        operation_type="cancel_result",
        target_type="generation_result",
        target_id=generation_id,
        target_name=gen.file_path,
        summary=summary,
    ))
    await db.commit()
    return {"status": "cancelled", "cached_path": str(dst), "was_confirmed": was_confirmed}


@router.post("/{project_id}/generations/{generation_id}/recover")
async def recover_generation(project_id: int, generation_id: int, db: AsyncSession = Depends(get_db)):
    """Recover a cancelled generation result — move file back from caches to original location."""
    result = await db.execute(
        select(GenerationResult).options(selectinload(GenerationResult.project))
        .where(GenerationResult.id == generation_id)
    )
    gen = result.scalar_one_or_none()
    if not gen:
        raise HTTPException(status_code=404, detail="Generation result not found")

    project = gen.project
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    src = Path(gen.storage_path)
    dst = Path(gen.file_path)

    if not src.exists():
        raise HTTPException(status_code=404, detail="File not found in caches")

    if not str(src).startswith(str(Path(project.working_dir) / "caches")):
        raise HTTPException(status_code=400, detail="File is not in caches — nothing to recover")

    # Move file back
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(src), str(dst))

    # Reset storage_path to original file_path
    gen.storage_path = gen.file_path

    db.add(OperationLog(
        project_id=project_id,
        user_id=1,
        operation_type="recover_result",
        target_type="generation_result",
        target_id=generation_id,
        target_name=gen.file_path,
        summary=f"Recovered generation result: {gen.prompt_id}, moved back from caches",
    ))
    await db.commit()
    return {"status": "recovered", "file_path": gen.file_path}


@router.post("/{project_id}/generations/{generation_id}/gacha")
async def gacha_generation(
    project_id: int,
    generation_id: int,
    body: GenerationsGachaRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """Re-roll a scene/shot generation result (抽卡).

    1. Cancel (move file to caches)
    2. Set gacha mode in YAML
    3. Run vimax with gacha config
    4. Restore YAML after completion
    """
    # ── Load generation record ──
    result = await db.execute(
        select(GenerationResult).options(
            selectinload(GenerationResult.step),
            selectinload(GenerationResult.project),
        )
        .where(GenerationResult.id == generation_id)
    )
    gen = result.scalar_one_or_none()
    if not gen:
        raise HTTPException(status_code=404, detail="Generation result not found")

    step = gen.step
    project = gen.project
    if not step or not project:
        raise HTTPException(status_code=404, detail="Step or project not found")

    # ── Step 1: Cancel (move file to caches with hash suffix) ──
    current_path = gen.storage_path or gen.file_path
    src = Path(current_path)
    if src.exists():
        dst = _cached_path(gen.file_path, project.working_dir)
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), str(dst))
        gen.storage_path = str(dst)
        await db.commit()

    # ── Step 2: Set gacha mode in YAML ──
    yaml_path = Path(project.working_dir) / "idea2video.yaml"
    if not yaml_path.exists():
        raise HTTPException(status_code=400, detail="idea2video.yaml not found in working_dir")

    # Backup original YAML
    yaml_backup = yaml_path.read_text(encoding="utf-8")
    backup_path = yaml_path.with_suffix(".yaml.gacha_bak")
    backup_path.write_text(yaml_backup, encoding="utf-8")

    # Write gacha config
    ConfigSyncService.write_gacha_config(
        project.working_dir,
        gacha_type=body.gacha_type,
        scene=body.scene,
        shot=body.shot,
    )

    # Sync to VIMAX_ROOT
    ConfigSyncService.sync_project_to_vimax(project.working_dir, settings.VIMAX_ROOT)

    # ── Step 3: Run vimax ──
    if vimax_runner.is_running:
        # Restore backup immediately since we can't run
        backup_path.rename(yaml_path)
        raise HTTPException(status_code=409, detail="Another project is already running")

    try:
        await vimax_runner.start(
            project_id=project.id,
            working_dir=project.working_dir,
            interrupt_step=step.name,
            vimax_root=settings.VIMAX_ROOT,
        )
    except RuntimeError as e:
        backup_path.rename(yaml_path)
        raise HTTPException(status_code=409, detail=str(e))

    # Update project / step status
    project.status = "running"
    project.current_step_name = step.name
    step.status = "running"
    step.started_at = datetime.utcnow()
    step.retry_count = (step.retry_count or 0) + 1

    db.add(OperationLog(
        project_id=project_id,
        user_id=1,
        operation_type="gacha_reroll",
        target_type="generation_result",
        target_id=generation_id,
        target_name=gen.file_path,
        summary=f"Gacha re-roll: type={body.gacha_type} scene={body.scene} shot={body.shot}, step={step.name}",
    ))
    await db.commit()

    # ── Step 4: Background task to restore YAML after completion ──

    async def _gacha_monitor():
        """Wait for gacha subprocess, then restore YAML."""
        if vimax_runner._process:
            try:
                await vimax_runner._process.wait()
            except Exception:
                pass

        # Restore original YAML
        if backup_path.exists():
            try:
                backup_path.rename(yaml_path)
            except Exception:
                pass

        # Flush and close output file
        if vimax_runner._output_file:
            try:
                vimax_runner._output_file.flush()
                vimax_runner._output_file.close()
            except Exception:
                pass
            vimax_runner._output_file = None

        # Parse generations and update DB
        async with async_session_factory() as session:
            from src.services.generation_parser import GenerationParser
            output_path = Path(project.working_dir) / "vimax_output.tmp"
            parsed = GenerationParser.parse_file(str(output_path), project.working_dir)

            # Resolve step
            step_id = None
            if project.current_step_name:
                sr = await session.execute(
                    select(Step).where(
                        Step.project_id == project_id,
                        Step.name == project.current_step_name,
                    )
                )
                sobj = sr.scalar_one_or_none()
                if sobj:
                    step_id = sobj.id

            exit_code = vimax_runner._process.returncode if vimax_runner._process else -1

            for pg in parsed:
                if not step_id or not pg.get("output_path"):
                    continue
                existing = await session.execute(
                    select(GenerationResult).where(
                        GenerationResult.project_id == project_id,
                        GenerationResult.prompt_id == pg["prompt_id"],
                    )
                )
                if existing.scalar_one_or_none():
                    continue
                db_gen = GenerationResult(
                    step_id=step_id,
                    project_id=project_id,
                    user_id=project.user_id,
                    file_path=pg["output_path"],
                    storage_path=pg["output_path"],
                    prompt_id=pg["prompt_id"],
                    workflow_name=pg.get("workflow_name", ""),
                    generation_type=pg["generation_type"],
                    duration_seconds=pg["duration_seconds"],
                )
                session.add(db_gen)

            # Update project / step status
            pr = await session.execute(select(Project).where(Project.id == project_id))
            pobj = pr.scalar_one_or_none()
            if pobj:
                if exit_code != 0:
                    pobj.status = "failed"
                    pobj.completed_at = datetime.utcnow()
                    error_tail = f"Gacha exited with code {exit_code}"
                    try:
                        lines = output_path.read_text(errors="replace").splitlines()
                        tail = lines[-20:]
                        error_tail = "\n".join(tail) if tail else error_tail
                    except Exception:
                        pass
                    pobj.error_message = error_tail
                # Keep as running (between steps) if exit 0 and not last step

            if project.current_step_name:
                sr2 = await session.execute(
                    select(Step).where(
                        Step.project_id == project_id,
                        Step.name == project.current_step_name,
                    )
                )
                sobj2 = sr2.scalar_one_or_none()
                if sobj2:
                    sobj2.status = "fully_complete" if exit_code == 0 else "failed"
                    sobj2.completed_at = datetime.utcnow()
                    if sobj2.started_at:
                        sobj2.duration_seconds = (datetime.utcnow() - sobj2.started_at).total_seconds()

            await session.commit()

        # Clean up runner state
        vimax_runner._process = None
        vimax_runner._current_project_id = None

    background_tasks.add_task(_gacha_monitor)

    return {
        "status": "gacha_started",
        "step_name": step.name,
        "gacha_type": body.gacha_type,
        "scene": body.scene,
        "shot": body.shot,
    }


@router.post("/{project_id}/generations/{generation_id}/retry")
async def retry_generation(
    project_id: int,
    generation_id: int,
    body: GenerationsRetryRequest,
    db: AsyncSession = Depends(get_db),
):
    """Retry generation with modified workflow params (抽卡)."""
    result = await db.execute(select(GenerationResult).where(GenerationResult.id == generation_id))
    gen = result.scalar_one_or_none()
    if not gen:
        raise HTTPException(status_code=404, detail="Generation result not found")

    proj_result = await db.execute(select(Project).where(Project.id == project_id))
    project = proj_result.scalar_one_or_none()

    client = ComfyUIClient(settings.COMFYUI_BASE_URL)
    workflow = client.read_workflow_from_dir(project.working_dir, gen.prompt_id)
    if not workflow:
        raise HTTPException(status_code=400, detail="Workflow not found in working_dir/workflows")

    # Merge modified params
    if body.modified_params:
        workflow.update(body.modified_params)

    try:
        prompt_id = await client.submit_workflow(workflow)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"ComfyUI submit failed: {e}")

    # Create new GenerationResult
    new_gen = GenerationResult(
        step_id=gen.step_id,
        project_id=project_id,
        user_id=1,
        file_path="pending",
        storage_path="pending",
        prompt_id=prompt_id,
        generation_type=gen.generation_type,
        duration_seconds=0,
    )
    db.add(new_gen)
    await db.flush()  # get new_gen.id before creating the log
    db.add(OperationLog(
        project_id=project_id,
        user_id=1,
        operation_type="regenerate_step",
        target_type="generation_result",
        target_id=new_gen.id,
        target_name=gen.file_path,
        summary=f"Retried generation with modified params, new prompt_id: {prompt_id}",
    ))
    await db.commit()
    await db.refresh(new_gen)

    return {"new_generation_id": new_gen.id, "prompt_id": prompt_id}
