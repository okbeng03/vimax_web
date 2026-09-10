"""Unit tests for ScheduleClient — mocked httpx transport."""

import json

import httpx
import pytest

from src.services.schedule_client import ScheduleClient, ScheduleClientError


class _CaptureTransport(httpx.AsyncBaseTransport):
    """Fake transport capturing request and returning canned response."""

    def __init__(self, status: int = 200, payload=None):
        self.status = status
        self.payload = payload if payload is not None else {}
        self.captured: dict = {}

    async def handle_async_request(self, request):
        self.captured["method"] = request.method
        self.captured["url"] = str(request.url)
        self.captured["headers"] = dict(request.headers)
        if request.content:
            self.captured["json"] = json.loads(request.content)
        content = self.payload if isinstance(self.payload, bytes) else (
            self.payload.encode() if isinstance(self.payload, str) else json.dumps(self.payload).encode()
        )
        return httpx.Response(self.status, content=content, request=request)


async def test_register_task_payload_and_headers():
    transport = _CaptureTransport(payload={"ok": True})
    client = ScheduleClient(base_url="http://scheduler.test:8001", api_key="secret")

    async with httpx.AsyncClient(transport=transport, base_url=client.base_url) as ac:
        resp = await ac.post(
            "/api/v1/tasks",
            json={
                "business_task_id": "p_1",
                "project_id": "1",
                "workflow": {"nodes": []},
                "project_name": "proj",
                "outputs_id": "n1",
                "type": "comfyui",
            },
            headers=client._headers(),
        )

    assert resp.status_code == 200
    assert resp.json() == {"ok": True}
    assert transport.captured["url"].endswith("/api/v1/tasks")
    assert transport.captured["json"]["business_task_id"] == "p_1"
    assert transport.captured["headers"].get("x-api-key") == "secret"


def test_headers_include_api_key_and_default():
    client = ScheduleClient(base_url="http://x", api_key="abc")
    headers = client._headers()
    assert headers["X-API-Key"] == "abc"

    client2 = ScheduleClient(base_url="http://x", api_key="")
    assert "X-API-Key" not in client2._headers()


def test_schedule_client_error_message():
    err = ScheduleClientError("调度服务返回 500: boom")
    assert "500" in str(err)


async def test_health_success():
    transport = _CaptureTransport(payload={"status": "ok"})
    client = ScheduleClient(base_url="http://scheduler.test:8001")

    async with httpx.AsyncClient(transport=transport, base_url=client.base_url) as ac:
        resp = await ac.get("/api/v1/health", headers=client._headers())

    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


async def test_error_status_surfaces():
    transport = _CaptureTransport(status=500, payload="internal error")
    client = ScheduleClient(base_url="http://scheduler.test:8001")

    async with httpx.AsyncClient(transport=transport, base_url=client.base_url) as ac:
        resp = await ac.post("/api/v1/tasks", json={}, headers=client._headers())

    assert resp.status_code == 500
