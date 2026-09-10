"""调度管理 API router — 透传 Vimax Scheduler 接口。

Web API 契约见 specs/002-schedule-mode/contracts/api.yaml "Web API" 部分。
任务与队列执行记录由调度器维护，Web 侧不落本地队列。

改版（2026-08）：项目列表直接透传调度器 GET /api/v1/projects；
项目任务列表优先调用调度器 GET /api/v1/projects/{id}/tasks，
调度器未实现该接口（404）时回退聚合 queue + results。
"""

import logging
from datetime import datetime
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_db
from src.models.project import Project
from src.schemas.schedule import (
    ScheduleProject,
    ScheduleProjectUpdate,
    ScheduleResult,
    ScheduleResultSyncRequest,
    ScheduleResultSyncResponse,
    ScheduleCancelResponse,
    ScheduleHealth,
    ScheduleTask,
)
from src.services.schedule_client import ScheduleClientError, schedule_client

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/schedule", tags=["schedule"])


# ── 调度服务健康检查 ──

@router.get("/health", response_model=ScheduleHealth)
async def schedule_health():
    try:
        await schedule_client.health()
        return ScheduleHealth(status="ok", service_url=schedule_client.base_url)
    except ScheduleClientError as exc:
        return ScheduleHealth(status="unavailable", service_url=schedule_client.base_url)


# ── 调度器控制（透传）──

@router.post("/scheduler/pause")
async def pause_scheduler():
    """透传调度器 POST /api/v1/scheduler/pause — 暂停调度器。"""
    try:
        return await schedule_client.pause_scheduler()
    except ScheduleClientError as exc:
        raise HTTPException(status_code=502, detail=f"调度服务不可用: {exc}")


@router.post("/scheduler/resume")
async def resume_scheduler():
    """透传调度器 POST /api/v1/scheduler/resume — 恢复调度器。"""
    try:
        return await schedule_client.resume_scheduler()
    except ScheduleClientError as exc:
        raise HTTPException(status_code=502, detail=f"调度服务不可用: {exc}")


# ── 调度项目（透传）──

@router.get("/projects", response_model=list[ScheduleProject])
async def list_schedule_projects():
    """透传调度器 GET /api/v1/projects — 全量项目列表。

    调度器 ProjectResponse: {project_id, name, priority, paused, stats{total,pending,success,failed}}。
    """
    try:
        projects = await schedule_client.list_projects()
    except ScheduleClientError as exc:
        raise HTTPException(status_code=502, detail=f"调度服务不可用: {exc}")

    return [
        ScheduleProject(
            project_id=str(p.get("project_id", "")),
            name=str(p.get("name") or ""),
            priority=int(p.get("priority") or 0),
            paused=bool(p.get("paused", False)),
            stats=dict(p.get("stats") or {}),
        )
        for p in projects or []
    ]


@router.get("/projects/{schedule_project_id}/tasks", response_model=list[ScheduleTask])
async def list_schedule_project_tasks(schedule_project_id: str):
    """List tasks for a single scheduler project.

    优先调度器 GET /api/v1/projects/{id}/tasks；接口未实现时回退聚合
    /api/v1/queue（QUEUED）+ /api/v1/results（SUCCESS/FAILED）。
    """
    try:
        try:
            remote = await schedule_client.list_project_tasks(schedule_project_id)
            raw_tasks = _extract_items(remote)
        except ScheduleClientError:
            logger.info(
                "scheduler has no GET /api/v1/projects/%s/tasks, fallback to queue+results aggregation",
                schedule_project_id,
            )
            raw_tasks = await _aggregate_project_tasks(schedule_project_id)
    except ScheduleClientError as exc:
        raise HTTPException(status_code=502, detail=f"调度服务不可用: {exc}")

    return [
        _to_schedule_task(t, schedule_project_id)
        for t in raw_tasks
    ]


@router.get("/projects/{schedule_project_id}", response_model=ScheduleProject)
async def get_schedule_project(schedule_project_id: str):
    """透传调度器 GET /api/v1/projects/{id} — 单项目详情。"""
    try:
        remote = await schedule_client.get_project(schedule_project_id)
    except ScheduleClientError as exc:
        if exc.status_code == 404:
            raise HTTPException(status_code=404, detail="调度项目不存在")
        raise HTTPException(status_code=502, detail=f"调度服务不可用: {exc}")
    if not remote:
        raise HTTPException(status_code=404, detail="调度项目不存在")
    return ScheduleProject(
        project_id=str(remote.get("project_id", schedule_project_id)),
        name=str(remote.get("name") or ""),
        priority=int(remote.get("priority") or 0),
        paused=bool(remote.get("paused", False)),
        stats=dict(remote.get("stats") or {}),
    )


@router.patch("/projects/{schedule_project_id}/priority", response_model=ScheduleProject)
async def set_schedule_project_priority(
    schedule_project_id: str,
    body: ScheduleProjectUpdate,
    db: AsyncSession = Depends(get_db),
):
    try:
        await schedule_client.set_priority(schedule_project_id, body.priority)
        remote = await schedule_client.get_project(schedule_project_id)
    except ScheduleClientError as exc:
        if exc.status_code == 404:
            raise HTTPException(status_code=404, detail="调度项目不存在")
        raise HTTPException(status_code=502, detail=f"调度服务不可用: {exc}")
    await _log_schedule_operation(
        db,
        schedule_project_id,
        "schedule_priority",
        summary=f"调整调度优先级为 {body.priority}",
    )
    return ScheduleProject(
        project_id=schedule_project_id,
        name=str(remote.get("name") or ""),
        priority=int(remote.get("priority") or body.priority),
        paused=bool(remote.get("paused", False)),
        stats=dict(remote.get("stats") or {}),
    )


@router.post("/projects/{schedule_project_id}/cancel", response_model=ScheduleCancelResponse)
async def cancel_schedule_project(
    schedule_project_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Cancel all unfinished tasks of a scheduler project (任务级取消映射为项目级取消)."""
    try:
        result = await schedule_client.cancel_project(schedule_project_id)
    except ScheduleClientError as exc:
        raise HTTPException(status_code=502, detail=f"调度服务不可用: {exc}")
    cancelled = bool((result or {}).get("cancelled", True))
    if cancelled:
        await _log_schedule_operation(
            db,
            schedule_project_id,
            "schedule_cancel",
            summary="取消调度项目全部任务",
        )
    return ScheduleCancelResponse(cancelled=cancelled)


# ── 调度结果回传 ──

@router.get("/results", response_model=list[ScheduleResult])
async def list_schedule_results(synced: bool = False):
    """List results from scheduler (un-synced by default)."""
    try:
        results = await schedule_client.list_results(synced=synced)
    except ScheduleClientError as exc:
        raise HTTPException(status_code=502, detail=f"调度服务不可用: {exc}")
    items = _extract_items(results)
    return [
        ScheduleResult(
            business_task_id=str(r.get("business_task_id") or r.get("task_id") or ""),
            project_id=str(r["project_id"]) if r.get("project_id") is not None else None,
            project_name=r.get("project_name"),
            status=r.get("status"),
            failure_reason=r.get("failure_reason"),
            synced=bool(r.get("synced", False)),
            file_path=r.get("file_path"),
            workflow_name=r.get("workflow_name"),
            result_ready_at=_parse_dt(r.get("result_ready_at")),
            created_at=_parse_dt(r.get("created_at")),
        )
        for r in items
    ]


@router.post("/results/sync", response_model=ScheduleResultSyncResponse)
async def sync_schedule_results(
    body: ScheduleResultSyncRequest,
    background_tasks: BackgroundTasks,
):
    """异步触发调度结果同步（结果回传）。

    前端只负责调用，不等待结果：后台串行执行
    （SUCCESS → 保存输出并落库；FAILED → 标记原因；先落库后标记 sync），
    全程串行避免并发写 SQLite 锁表，完成后输出醒目日志。
    """
    from src.services.schedule_sync import run_sync_background

    background_tasks.add_task(run_sync_background, body.items)
    return ScheduleResultSyncResponse(started=True, count=len(body.items))


# ── helpers ──

def _extract_items(resp: Any) -> list[dict[str, Any]]:
    """兼容 {total, items: [...]} 与裸数组两种响应形态。"""
    if isinstance(resp, dict):
        return resp.get("items") or []
    return resp or []


async def _aggregate_project_tasks(project_id: str) -> list[dict[str, Any]]:
    """回退方案：queue（QUEUED）+ results synced=true/false（SUCCESS/FAILED）按 project_id 聚合。

    注意：RUNNING / CANCELED 任务调度器无枚举接口，聚合结果不包含。
    """
    queue_resp = await schedule_client.list_queue()
    queue_items = _extract_items(queue_resp)

    results: list[dict[str, Any]] = []
    for synced in (False, True):
        resp = await schedule_client.list_results(synced=synced)
        results.extend(_extract_items(resp))

    tasks: list[dict[str, Any]] = []
    for q in queue_items:
        if str(q.get("project_id", "")) == project_id:
            tasks.append({**q, "status": "QUEUED"})
    for r in results:
        if str(r.get("project_id", "")) == project_id:
            tasks.append(r)
    tasks.sort(key=lambda t: t.get("created_at") or "", reverse=True)
    return tasks


def _to_schedule_task(t: dict[str, Any], project_id: str) -> ScheduleTask:
    return ScheduleTask(
        business_task_id=str(t.get("business_task_id", "")),
        project_id=project_id,
        project_name=t.get("project_name"),
        workflow_name=t.get("workflow_name"),
        status=t.get("status", "QUEUED"),
        priority=int(t.get("priority") or t.get("project_priority") or 0),
        type=t.get("type"),
        retry_count=int(t.get("retry_count") or 0),
        failure_reason=t.get("failure_reason"),
        result_ready_at=_parse_dt(t.get("result_ready_at")),
        created_at=_parse_dt(t.get("created_at")),
        updated_at=_parse_dt(t.get("updated_at")),
    )


async def _log_schedule_operation(
    db: AsyncSession,
    schedule_project_id: str,
    operation_type: str,
    summary: str,
) -> None:
    """审计日志（纳入既有操作记录体系，FR-024）。project_id 为本地项目 id 字符串。"""
    try:
        from src.models.operation_log import OperationLog
        pid = int(schedule_project_id)
        pr = await db.execute(select(Project).where(Project.id == pid))
        project = pr.scalar_one_or_none()
        if not project:
            return
        db.add(OperationLog(
            project_id=project.id,
            user_id=project.user_id or 1,
            operation_type=operation_type,
            target_type="schedule_project",
            target_name=str(schedule_project_id),
            summary=summary,
        ))
        await db.commit()
    except (ValueError, Exception):  # noqa: BLE001 — 审计失败不阻断主流程
        logging.getLogger(__name__).warning(
            "schedule audit log skipped for project %s", schedule_project_id
        )


def _parse_dt(value):
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None
