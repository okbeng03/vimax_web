"""调度模式服务 — 开启/关闭调度模式、切换约束判定。

约束（data-model.md / spec.md）：
- 开启：仅修改字段，无前置条件。
- 关闭：调度服务 stats.pending > 0 → 拒绝（任务与队列执行记录由调度器维护）。
"""

import logging
from datetime import datetime

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.project import Project
from src.services.config_sync import ConfigSyncService
from src.services.schedule_client import ScheduleClientError, schedule_client

logger = logging.getLogger(__name__)


async def assert_can_disable(db: AsyncSession, project: Project) -> None:
    """Raise HTTPException(409) if scheduler still has pending tasks for the project."""
    try:
        remote = await schedule_client.get_project(str(project.id))
    except ScheduleClientError as exc:
        if exc.status_code == 404:
            # 调度器中无该项目（尚未同步过任务）→ 无 pending 任务，允许关闭
            return
        raise HTTPException(status_code=503, detail=f"调度服务不可用: {exc}")

    pending = int((remote.get("stats") or {}).get("pending", 0) or 0)
    if pending > 0:
        raise HTTPException(
            status_code=409,
            detail=f"调度服务中仍有 {pending} 个待执行任务，无法关闭调度模式。",
        )


async def set_schedule_mode(
    db: AsyncSession,
    project: Project,
    schedule_mode: bool,
    *,
    record_operation=None,
) -> Project:
    """Toggle schedule mode with constraint checks. Returns updated project."""
    if schedule_mode == project.schedule_mode:
        await db.refresh(project)
        return project

    if not schedule_mode:
        await assert_can_disable(db, project)

    project.schedule_mode = schedule_mode
    project.schedule_updated_at = datetime.utcnow()
    if schedule_mode:
        project.schedule_status = "idle"
    await db.commit()

    # 联动 config.py 的执行模式：调度模式 → mode="schedule"，关闭 → mode="run"
    # （vimax_main 读取该字段决定本地执行还是输出调度日志；执行时自动同步 VIMAX_ROOT）
    try:
        if project.working_dir:
            ConfigSyncService.set_mode(
                project.working_dir,
                "schedule" if schedule_mode else "run",
            )
    except Exception as exc:  # noqa: BLE001 — 配置文件修改失败不阻断模式切换
        logger.warning("failed to update config.py mode for project %s: %s", project.id, exc)

    if record_operation is not None:
        await record_operation(
            db,
            project_id=project.id,
            operation_type="schedule_mode",
            target_type="project",
            target_name=project.name,
            summary="已开启调度模式" if schedule_mode else "已关闭调度模式",
        )

    await db.refresh(project)
    return project
