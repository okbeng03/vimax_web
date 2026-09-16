"""Vimax Scheduler HTTP 客户端 — 任务注册 / 查询 / 取消 / 结果回传。

契约见 specs/002-schedule-mode/contracts/api.yaml 的 "调度服务" 部分。
"""

import logging
from typing import Any

import httpx

from src.config import settings

logger = logging.getLogger(__name__)

_REGISTER_TIMEOUT = 30.0  # 注册需同步上传 workflow 文件，放宽超时


class ScheduleClientError(Exception):
    """调度服务不可用或返回错误。"""

    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class ScheduleClient:
    """Thin async client for the Vimax Scheduler service (127.0.0.1:8001)."""

    def __init__(self, base_url: str | None = None, api_key: str | None = None) -> None:
        self.base_url = (base_url or settings.SCHEDULE_SERVICE_URL).rstrip("/")
        self.api_key = api_key if api_key is not None else settings.SCHEDULE_API_KEY

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["X-API-Key"] = self.api_key
        return headers

    async def _request(self, method: str, path: str, *, timeout: float = 10.0, **kwargs) -> Any:
        url = f"{self.base_url}{path}"
        msg = f"[ScheduleClient] {method} {url} params={kwargs.get('params')} body={kwargs.get('json')}"
        print(msg, flush=True)
        logger.info(msg)
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                resp = await client.request(method, url, headers=self._headers(), **kwargs)
        except httpx.HTTPError as exc:
            raise ScheduleClientError(f"调度服务请求失败: {exc}") from exc

        if resp.status_code >= 400:
            raise ScheduleClientError(
                f"调度服务返回 {resp.status_code}: {resp.text[:200]}",
                status_code=resp.status_code,
            )
        if not resp.content:
            return None
        try:
            msg = f"[ScheduleClient] {method} {url} result={resp.json()}"
            print(msg, flush=True)
            logger.info(msg)
            return resp.json()
        except ValueError:
            return resp.text

    async def health(self) -> dict[str, Any]:
        return await self._request("GET", "/api/v1/health", timeout=5.0)

    async def get_scheduler_status(self) -> dict[str, Any]:
        """GET /api/v1/scheduler/status — 获取调度器状态（{"status": "paused", "enabled": true}）。"""
        return await self._request("GET", "/api/v1/scheduler/status")

    async def pause_scheduler(self) -> dict[str, Any]:
        """POST /api/v1/scheduler/pause — 暂停调度器（不再派发新任务）。"""
        return await self._request("POST", "/api/v1/scheduler/pause")

    async def resume_scheduler(self) -> dict[str, Any]:
        """POST /api/v1/scheduler/resume — 恢复调度器。"""
        return await self._request("POST", "/api/v1/scheduler/resume")

    async def register_task(self, *, business_task_id: str, project_id: str,
                            workflow: dict[str, Any], project_name: str,
                            outputs_id: str,
                            extend_data: dict[str, Any] | None = None) -> dict[str, Any]:
        payload = {
            "business_task_id": business_task_id,
            "project_id": project_id,
            "workflow": workflow,
            "project_name": project_name,
            "outputs_id": outputs_id,
            "type": "comfyui",
            "extend_data": extend_data or {},
        }
        return await self._request(
            "POST", "/api/v1/tasks", timeout=_REGISTER_TIMEOUT, json=payload
        )

    async def query_task(self, business_task_id: str, project_id: str) -> dict[str, Any]:
        return await self._request(
            "GET", f"/api/v1/tasks/{business_task_id}", params={"project_id": project_id}
        )

    async def retry_task(self, business_task_id: str, project_id: str) -> dict[str, Any]:
        return await self._request(
            "POST", f"/api/v1/tasks/{business_task_id}/retry", params={"project_id": project_id}
        )

    async def list_projects(self) -> list[dict[str, Any]]:
        """GET /api/v1/projects — 全量项目列表（ProjectResponse[]）。"""
        return await self._request("GET", "/api/v1/projects")

    async def list_project_tasks(self, project_id: str) -> dict[str, Any]:
        """GET /api/v1/projects/{project_id}/tasks — 按项目查任务列表。

        调度器部署版 >= 0.x（含该接口）返回 {total, items: TaskResponse[]}。
        若调度器未实现该接口（404），将抛出 ScheduleClientError，调用方应回退聚合。
        """
        return await self._request("GET", f"/api/v1/projects/{project_id}/tasks")

    async def list_queue(self) -> dict[str, Any]:
        # {total, items: QueueItem[]}，QueueItem 仅含 QUEUED 任务
        return await self._request("GET", "/api/v1/queue")

    async def get_project(self, project_id: str) -> dict[str, Any]:
        return await self._request("GET", f"/api/v1/projects/{project_id}")

    async def set_priority(self, project_id: str, priority: int) -> dict[str, Any]:
        return await self._request(
            "PATCH", f"/api/v1/projects/{project_id}/priority", json={"priority": priority}
        )

    async def cancel_project(self, project_id: str) -> dict[str, Any]:
        return await self._request("POST", f"/api/v1/projects/{project_id}/cancel")

    async def list_results(self, synced: bool = False) -> dict[str, Any]:
        # {total, items: UnsyncedResultItem[]}，仅 SUCCESS / FAILED 任务
        return await self._request("GET", "/api/v1/results", params={"synced": str(synced).lower()})

    async def get_result(self, business_task_id: str, project_id: str) -> dict[str, Any]:
        return await self._request(
            "GET", f"/api/v1/results/{business_task_id}", params={"project_id": project_id}
        )

    async def sync_result(self, business_task_id: str, project_id: str) -> dict[str, Any]:
        """POST /api/v1/results/{business_task_id}/sync — 标记结果已同步（与查询同样传 project_id）。

        必须在本地文件落库/确认之后调用，确保不丢失生成的文件。
        """
        return await self._request(
            "POST", f"/api/v1/results/{business_task_id}/sync", params={"project_id": project_id}
        )


schedule_client = ScheduleClient()
