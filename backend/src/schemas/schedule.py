"""Schedule mode Pydantic schemas — 项目调度模式与调度服务接口契约。"""

from datetime import datetime
from typing import Any

from pydantic import Field

from src.schemas import AppBaseSchema


# ── Web API：项目调度模式 ──

class ProjectScheduleUpdate(AppBaseSchema):
    schedule_mode: bool


class ProjectScheduleResponse(AppBaseSchema):
    project_id: int
    schedule_mode: bool
    schedule_status: str  # idle / syncing / synced / failed
    schedule_updated_at: datetime | None = None


# ── 调度服务（Vimax Scheduler）──

class ScheduleTask(AppBaseSchema):
    business_task_id: str
    project_id: str
    project_name: str | None = None
    workflow_name: str | None = None
    status: str  # QUEUED / RUNNING / SUCCESS / FAILED / CANCELED
    priority: int = 0
    type: str | None = None
    retry_count: int = 0
    failure_reason: str | None = None
    result_ready_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class ScheduleProject(AppBaseSchema):
    """调度器 ProjectResponse 透传：name（非 project_name）、stats 为 total/pending/success/failed。"""

    project_id: str
    name: str = ""
    priority: int = 0
    paused: bool = False
    stats: dict[str, Any] = {}


class ScheduleProjectUpdate(AppBaseSchema):
    priority: int


class ScheduleResult(AppBaseSchema):
    business_task_id: str
    project_id: str | None = None
    project_name: str | None = None
    status: str | None = None
    failure_reason: str | None = None
    synced: bool = False
    file_path: str | None = None
    workflow_name: str | None = None
    result_ready_at: datetime | None = None
    created_at: datetime | None = None


class ScheduleResultSyncItem(AppBaseSchema):
    task_id: str
    project_id: int


class ScheduleResultSyncRequest(AppBaseSchema):
    items: list[ScheduleResultSyncItem]


class ScheduleResultSyncResponse(AppBaseSchema):
    """同步接口响应：异步触发，前端只负责调用不等待结果。

    具体同步统计（synced/failed/skipped）由后台任务完成并输出日志。
    """
    started: bool = True
    count: int = 0


class ScheduleCancelResponse(AppBaseSchema):
    cancelled: bool = False


class ScheduleHealth(AppBaseSchema):
    status: str
    service_url: str
