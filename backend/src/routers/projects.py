"""Projects API router — full CRUD with config sync and operation logging."""

import difflib
import json
import os
import shutil
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.config import settings
from src.database import get_db
from src.models.project import Project
from src.models.step import Step
from src.models.template import Template
from src.models.generation_result import GenerationResult
from src.models.operation_log import OperationLog
from src.schemas.project import (
    ProjectCreate,
    ProjectCreateResponse,
    ProjectConfigUpdate,
    ProjectListItem,
    ProjectListResponse,
    ProjectResponse,
    ProjectConfig,
    StepSummary,
    ProgressStepSchema,
    ProjectProgressResponse,
)
from src.services.config_sync import ConfigSyncService
from src.services.vimax_runner import vimax_runner
from src.services.progress_manager import (
    get_template_progress,
    get_active_steps,
    get_next_step_name,
    is_last_step,
)

router = APIRouter(prefix="/api/projects", tags=["projects"])


async def _record_operation(
    db: AsyncSession,
    project_id: int,
    operation_type: str,
    target_type: str,
    target_name: str,
    summary: str,
    target_id: int | None = None,
    details: str | None = None,
):
    """Helper to create an OperationLog record."""
    log = OperationLog(
        project_id=project_id,
        user_id=1,  # default user "muze"
        operation_type=operation_type,
        target_type=target_type,
        target_id=target_id,
        target_name=target_name,
        summary=summary,
        details=details,
    )
    db.add(log)
    await db.commit()


@router.get("/running")
async def get_running_project(db: AsyncSession = Depends(get_db)):
    """Return the currently running project (at most one globally)."""
    if not vimax_runner.is_running or vimax_runner.current_project_id is None:
        return {"is_running": False, "project_id": None, "project_name": None}

    result = await db.execute(
        select(Project).where(Project.id == vimax_runner.current_project_id)
    )
    project = result.scalar_one_or_none()
    return {
        "is_running": True,
        "project_id": vimax_runner.current_project_id,
        "project_name": project.name if project else None,
    }


@router.get("/{project_id}/progress", response_model=ProjectProgressResponse)
async def get_project_progress(project_id: int, db: AsyncSession = Depends(get_db)):
    """Return the template's progress enum with per-step status for this project."""
    # Load project + template
    result = await db.execute(
        select(Project).options(selectinload(Project.template)).where(Project.id == project_id)
    )
    project = result.unique().scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    if not project.template:
        raise HTTPException(status_code=400, detail="Project has no template")

    # Get DB step statuses keyed by name
    steps_result = await db.execute(
        select(Step).where(Step.project_id == project_id)
    )
    db_steps = {s.name: s for s in steps_result.scalars().all()}

    # Build progress list from template enum
    progress_steps = get_template_progress(project.template.directory_name)
    active = get_active_steps(progress_steps)

    current_order: int | None = None
    progress_items: list[ProgressStepSchema] = []

    for ps in active:
        db_step = db_steps.get(ps.name)
        status = "pending"
        if db_step:
            if db_step.status == "fully_complete":
                status = "success"
            elif db_step.status == "failed":
                status = "failed"
            elif db_step.status == "running":
                status = "running"
                current_order = ps.order

        progress_items.append(ProgressStepSchema(
            name=ps.name,
            label=ps.label,
            order=ps.order,
            status=status,
        ))

    return ProjectProgressResponse(steps=progress_items, current_step_order=current_order)


@router.get("", response_model=ProjectListResponse)
async def list_projects(
    status: str | None = None,
    search: str | None = None,
    page: int = 1,
    page_size: int = 20,
    db: AsyncSession = Depends(get_db),
):
    """List projects with filters, search, and pagination."""
    query = select(Project).options(selectinload(Project.template), selectinload(Project.steps))

    if status:
        query = query.where(Project.status == status)
    if search:
        query = query.where(
            Project.name.contains(search) | Project.creative_description.contains(search)
        )

    # Count total
    count_query = select(func.count()).select_from(Project)
    if status:
        count_query = count_query.where(Project.status == status)
    if search:
        count_query = count_query.where(
            Project.name.contains(search) | Project.creative_description.contains(search)
        )
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # Paginate
    query = query.order_by(Project.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    projects = result.unique().scalars().all()

    items = []
    for p in projects:
        steps = p.steps or []
        completed = sum(1 for s in steps if s.status == "fully_complete")
        failed = sum(1 for s in steps if s.status == "failed")
        items.append(
            ProjectListItem(
                id=p.id,
                name=p.name,
                creative_description=p.creative_description,
                working_dir=p.working_dir,
                status=p.status,
                template_name=p.template.display_name if p.template else None,
                current_step_name=p.current_step_name,
                step_summary=StepSummary(total=len(steps), completed=completed, failed=failed),
                created_at=p.created_at,
                updated_at=p.updated_at,
            )
        )

    return ProjectListResponse(projects=items, total=total, page=page, page_size=page_size)


@router.post("", response_model=ProjectCreateResponse, status_code=201)
async def create_project(body: ProjectCreate, db: AsyncSession = Depends(get_db)):
    """Create a new project from a template.

    Steps:
    1. Sync VIMAX_ROOT/configs/ to its configured working_dir if applicable.
    2. Use ``working_dir_root`` directly as the project working_dir (no UUID subdir).
    3. Copy template files → working_dir.
    4. Replace ``idea`` and ``working_dir`` placeholders with user input.
    """
    # Get template
    template_result = await db.execute(select(Template).where(Template.id == body.template_id))
    template = template_result.scalar_one_or_none()
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    # --- Step 1: sync VIMAX_ROOT/configs/ to its configured working_dir ---
    ConfigSyncService.sync_vimax_configs(settings.VIMAX_ROOT)

    # --- Step 2: working_dir_root IS the project working_dir ---
    working_dir = body.working_dir_root

    # --- Step 3: copy template files ---
    template_path = Path(__file__).parent.parent / "templates" / template.directory_name
    ConfigSyncService.copy_template(str(template_path), working_dir)

    # --- Step 4: replace idea / working_dir variables ---
    ConfigSyncService.replace_variables(
        working_dir,
        idea=body.creative_description,
        working_dir_value=working_dir,
    )

    # Create project
    project = Project(
        user_id=1,
        name=body.name,
        creative_description=body.creative_description,
        working_dir=working_dir,
        template_id=template.id,
    )
    db.add(project)
    await db.flush()

    # Create steps from template progress.py enum
    progress_steps = get_template_progress(template.directory_name)
    active = get_active_steps(progress_steps)
    for i, ps in enumerate(active):
        step = Step(project_id=project.id, name=ps.name, step_order=i)
        db.add(step)

    await db.commit()
    await db.refresh(project)

    return ProjectCreateResponse(
        id=project.id,
        name=project.name,
        working_dir=project.working_dir,
        status=project.status,
        created_at=project.created_at,
    )


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(project_id: int, db: AsyncSession = Depends(get_db)):
    """Get project detail with config and steps."""
    result = await db.execute(
        select(Project)
        .options(selectinload(Project.template), selectinload(Project.steps))
        .where(Project.id == project_id)
    )
    project = result.unique().scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Count unconfirmed generations
    unconfirmed_result = await db.execute(
        select(func.count()).select_from(GenerationResult).where(
            and_(GenerationResult.project_id == project_id, GenerationResult.confirmed == False)
        )
    )
    unconfirmed_count = unconfirmed_result.scalar() or 0

    # Load config from filesystem
    config = ProjectConfig(
        yaml_content=ConfigSyncService.read_yaml(project.working_dir) or "",
        config_py_content=ConfigSyncService.read_config_py(project.working_dir) or "",
    )

    return ProjectResponse(
        id=project.id,
        name=project.name,
        creative_description=project.creative_description,
        working_dir=project.working_dir,
        status=project.status,
        template_id=project.template_id,
        current_step_name=project.current_step_name,
        config=config,
        unconfirmed_count=unconfirmed_count,
        created_at=project.created_at,
        updated_at=project.updated_at,
    )


def _compute_diff(original: str, modified: str, filename: str) -> str:
    """Generate unified diff (git style)."""
    return "".join(difflib.unified_diff(
        original.splitlines(keepends=True),
        modified.splitlines(keepends=True),
        fromfile=f"a/{filename}",
        tofile=f"b/{filename}",
    ))


@router.put("/{project_id}/config")
async def update_project_config(
    project_id: int,
    body: ProjectConfigUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Update project YAML + config.py with bidirectional sync to working_dir."""
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Read originals BEFORE writing
    original_yaml = ConfigSyncService.read_yaml(project.working_dir) or ""
    original_config = ConfigSyncService.read_config_py(project.working_dir) or ""

    # Write to filesystem
    ConfigSyncService.write_yaml(project.working_dir, body.yaml_content)
    ConfigSyncService.write_config_py(project.working_dir, body.config_py_content)

    # Update project updated_at
    project.updated_at = datetime.utcnow()
    await db.commit()

    # Compute diffs
    yaml_diff = _compute_diff(original_yaml, body.yaml_content, "idea2video.yaml")
    config_diff = _compute_diff(original_config, body.config_py_content, "config.py")

    changes = []
    if yaml_diff:
        changes.append({
            "file": "idea2video.yaml",
            "diff": yaml_diff,
            "original": original_yaml,
        })
    if config_diff:
        changes.append({
            "file": "config.py",
            "diff": config_diff,
            "original": original_config,
        })

    details = json.dumps({"changes": changes}, ensure_ascii=False) if changes else None

    # Record operation
    await _record_operation(
        db,
        project_id=project.id,
        operation_type="edit_file",
        target_type="file",
        target_name="idea2video.yaml / config.py",
        summary="Updated project configuration",
        details=details,
    )

    return {"status": "synced"}


@router.delete("/{project_id}", status_code=204)
async def delete_project(project_id: int, db: AsyncSession = Depends(get_db)):
    """Delete project and its working_dir."""
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    working_dir = project.working_dir

    await db.delete(project)
    await db.commit()

    # Remove working_dir from filesystem
    if os.path.exists(working_dir):
        shutil.rmtree(working_dir, ignore_errors=True)


@router.get("/{project_id}/stdout")
async def get_project_stdout(project_id: int, db: AsyncSession = Depends(get_db)):
    """Read cached stdout content from vimax_output.tmp for a non-running project."""
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    working_dir = project.working_dir
    output_path = os.path.join(working_dir, "vimax_output.tmp")

    if not os.path.exists(output_path):
        # Also check with pathlib for comparison
        pp = Path(working_dir) / "vimax_output.tmp"
        return {"content": ""}

    try:
        with open(output_path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
        return {"content": content}
    except Exception as e:
        return {"content": ""}
