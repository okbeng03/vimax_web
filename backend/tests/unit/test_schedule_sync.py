"""Unit tests for schedule sync: direct submission to scheduler + result pull-back."""

import json

import pytest

from src.database import Base, engine, async_session_factory
from src.models.project import Project
from src.models.generation_result import GenerationResult
from src.schemas.schedule import ScheduleResultSyncItem
from src.services.schedule_client import ScheduleClientError
from src.services.schedule_sync import (
    _infer_type,
    _read_workflow,
    pull_and_sync_results,
    submit_schedule_event,
)


@pytest.fixture(scope="module", autouse=True)
async def _setup_db():
    # 使用 conftest.py 隔离的测试库（VIMAX_DATABASE_URL 指向 backend/tests/data/）
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


def test_read_workflow(tmp_path):
    wf = tmp_path / "wf.json"
    wf.write_text(json.dumps({"nodes": []}), encoding="utf-8")
    assert _read_workflow(str(wf)) == {"nodes": []}
    assert _read_workflow(str(tmp_path / "missing.json")) is None
    bad = tmp_path / "bad.json"
    bad.write_text("not json", encoding="utf-8")
    assert _read_workflow(str(bad)) is None


# ── 直接提交调度器 ──

class _FakeRegisterClient:
    """Fake schedule client recording register_task calls."""

    def __init__(self, fail: bool = False):
        self.calls: list[dict] = []
        self.fail = fail

    async def register_task(self, **kwargs):
        if self.fail:
            raise ScheduleClientError("scheduler down")
        self.calls.append(kwargs)


async def _make_project(tmp_path, with_step: bool = False) -> int:
    proj = Project(user_id=1, name="schedule-proj", creative_description="d",
                   working_dir=str(tmp_path), schedule_mode=True)
    async with async_session_factory() as session:
        session.add(proj)
        await session.commit()
        await session.refresh(proj)
        pid = proj.id
        if with_step:
            from src.models.step import Step
            session.add(Step(project_id=pid, name="step1", step_order=0))
            await session.commit()
        return pid


async def test_submit_schedule_event_ok(monkeypatch, tmp_path):
    wf = tmp_path / "wf.json"
    wf.write_text(json.dumps({"nodes": []}), encoding="utf-8")
    pid = await _make_project(tmp_path)

    fake = _FakeRegisterClient()
    monkeypatch.setattr("src.services.schedule_sync.schedule_client", fake)

    status = await submit_schedule_event(
        project_id=pid,
        prompt_id="p_300",
        workflow_name="wf.json",
        workflow_path=str(wf),
        output_ids=["n1"],
        generation_type="first_frame",
        file_path="/tmp/out.png",
    )
    assert status == "ok"
    assert len(fake.calls) == 1
    call = fake.calls[0]
    assert call["business_task_id"] == "p_300"
    assert call["project_id"] == str(pid)
    assert call["workflow"] == {"nodes": []}
    assert call["outputs_id"] == "n1"
    assert call["extend_data"] == {
        "step_id": None,
        "user_id": None,
        "prompt_id": "p_300",
        "workflow_name": "wf.json",
        "generation_type": "first_frame",
        "file_path": "/tmp/out.png",
    }

    # 提交成功后项目进入 syncing
    async with async_session_factory() as session:
        proj = (await session.execute(
            __import__("sqlalchemy").select(Project).where(Project.id == pid)
        )).scalar_one()
        assert proj.schedule_status == "syncing"


async def test_submit_schedule_event_invalid_workflow(monkeypatch, tmp_path):
    pid = await _make_project(tmp_path)
    fake = _FakeRegisterClient()
    monkeypatch.setattr("src.services.schedule_sync.schedule_client", fake)

    bad = tmp_path / "bad.json"
    bad.write_text("not json", encoding="utf-8")
    status = await submit_schedule_event(
        project_id=pid,
        prompt_id="p_bad",
        workflow_name="wf.json",
        workflow_path=str(bad),
        output_ids=None,
        generation_type="first_frame",
        file_path=None,
    )
    assert status == "invalid"
    assert fake.calls == []  # 未向调度器注册


async def test_submit_schedule_event_error(monkeypatch, tmp_path):
    pid = await _make_project(tmp_path)
    fake = _FakeRegisterClient(fail=True)
    monkeypatch.setattr("src.services.schedule_sync.schedule_client", fake)

    status = await submit_schedule_event(
        project_id=pid,
        prompt_id="p_err",
        workflow_name="wf.json",
        workflow_path=None,  # 无 workflow → workflow={}
        output_ids=None,
        generation_type="first_frame",
        file_path=None,
    )
    assert status == "error"


# ── US4: 结果回传 ──

def test_infer_type():
    assert _infer_type("/tmp/x/last_frame.png") == "last_frame"
    assert _infer_type("/tmp/x/first_frame.png") == "first_frame"
    assert _infer_type("/tmp/x/video.mp4") == "video"
    assert _infer_type("/tmp/x/audio.wav") == "audio"
    assert _infer_type("/tmp/x/plain.png") == "image"


class _FakeScheduleClient:
    """Fake client for pull_and_sync_results tests (get_result + sync_result)."""

    def __init__(self, results: dict[str, dict]):
        self.results = results
        self.get_calls: list[str] = []
        self.sync_calls: list[str] = []

    async def get_result(self, business_task_id: str, project_id: str):
        self.get_calls.append(business_task_id)
        return self.results.get(business_task_id) or {}

    async def sync_result(self, business_task_id: str, project_id: str):
        self.sync_calls.append(business_task_id)


async def _fake_download(url: str, dst) -> bool:
    """替换真实下载：直接写文件，模拟 ComfyUI view 下载成功。"""
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_bytes(b"PNG")
    return True


async def test_pull_and_sync_results_success(monkeypatch, tmp_path):
    async with async_session_factory() as session:
        await session.execute(__import__("sqlalchemy").delete(GenerationResult))
        await session.commit()

    pid = await _make_project(tmp_path, with_step=True)
    output = tmp_path / "last_frame.png"

    fake = _FakeScheduleClient({
        "p_res_1": {
            "business_task_id": "p_res_1",
            "project_id": str(pid),
            "status": "SUCCESS",
            "result": {
                "outputs": {"n1": {"view": "http://comfy.local/view?filename=last_frame.png"}},
                "extend_data": {
                    "prompt_id": "p_res_1",
                    "file_path": str(output),
                    "workflow_name": "wf.json",
                    "generation_type": "last_frame",
                },
            },
        },
    })
    monkeypatch.setattr("src.services.schedule_sync._download_to", _fake_download)

    items = [ScheduleResultSyncItem(task_id="p_res_1", project_id=pid)]
    async with async_session_factory() as session:
        stats = await pull_and_sync_results(session, items, client=fake)
        assert stats["synced"] == 1
        assert stats["failed"] == 0
        assert stats["skipped"] == 0
        assert output.exists()

        # 落库成功且字段对齐
        gr = (await session.execute(
            __import__("sqlalchemy").select(GenerationResult).where(
                GenerationResult.prompt_id == "p_res_1"
            )
        )).scalar_one()
        assert gr.project_id == pid
        assert gr.file_path == str(output)
        assert gr.generation_type == "last_frame"

    # 落库成功后再标记 sync 状态
    assert fake.sync_calls == ["p_res_1"]

    # 再次同步：目标文件已存在 → 不下载不落库，仅标记 sync
    async with async_session_factory() as session:
        stats2 = await pull_and_sync_results(session, items, client=fake)
        assert stats2["skipped"] == 1
        assert stats2["synced"] == 0
    assert fake.sync_calls == ["p_res_1", "p_res_1"]
    assert output.exists()


async def test_pull_and_sync_results_failed_marks_reason(monkeypatch, tmp_path):
    pid = await _make_project(tmp_path, with_step=True)

    fake = _FakeScheduleClient({
        "p_res_fail": {
            "business_task_id": "p_res_fail",
            "project_id": str(pid),
            "status": "FAILED",
            "failure_reason": "comfyui_unresponsive",
            "result": {
                "outputs": {},
                "extend_data": {
                    "prompt_id": "p_res_fail",
                    "file_path": str(tmp_path / "fail.png"),
                    "workflow_name": "wf.json",
                    "generation_type": "last_frame",
                },
            },
        },
    })

    items = [ScheduleResultSyncItem(task_id="p_res_fail", project_id=pid)]
    async with async_session_factory() as session:
        stats = await pull_and_sync_results(session, items, client=fake)
        assert stats["failed"] == 1

        # FAILED → 创建失败记录（带 error_message），不下载
        gr = (await session.execute(
            __import__("sqlalchemy").select(GenerationResult).where(
                GenerationResult.prompt_id == "p_res_fail"
            )
        )).scalar_one_or_none()
        assert gr is not None
        assert gr.error_message == "comfyui_unresponsive"
        assert gr.generation_type == "last_frame"
        assert not (tmp_path / "fail.png").exists()

        # 失败原因进入操作日志
        from src.models.operation_log import OperationLog
        op = (await session.execute(
            __import__("sqlalchemy").select(OperationLog).where(
                OperationLog.operation_type == "schedule_sync"
            )
        )).scalars().all()
        assert any("调度任务失败" in (o.summary or "") for o in op)

    # FAILED 同样标记 sync 状态，避免调度器积压
    assert fake.sync_calls == ["p_res_fail"]
