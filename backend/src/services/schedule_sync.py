"""调度同步服务 — 将日志解析出的调度事件直接提交到 Vimax Scheduler。

流程：
1. 监听到 [COMFYUI SCHEDULE] 事件后，立即调用调度器 register_task 注册任务。
2. 任务与队列执行记录由调度器自行维护（Web 通过调度器 API 查询）。
3. 结果回传：pull_and_sync_results 从调度器拉取结果并落本地 GenerationResult。
"""

import json
import logging
import re
from pathlib import Path
from typing import Any
from urllib.parse import urlparse, urlunsplit

import httpx

from src.config import settings

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import async_session_factory
from src.models.generation_result import GenerationResult
from src.models.operation_log import OperationLog
from src.models.project import Project
from src.models.step import Step
from src.schemas.schedule import ScheduleResultSyncItem
from src.services.schedule_client import ScheduleClient, ScheduleClientError, schedule_client

logger = logging.getLogger(__name__)


def _build_business_task_id(project_id: int, file_path: str | None, prompt_id: str) -> str:
    """按规则构建业务任务 ID。

    1. 分镜生成:  file_path=/…/scene_0/shots/4/video.mp4       → 1_0_4_video
    2. 环境图片:  file_path=/…/scene_0/environments/xx.png     → 1_0_enviroment_xx
                  （目录为复数 environments，task_id 固定用单数 enviroment）
    3. 字形过渡:  file_path=/…/hanzi/evolution/字形演变.mp4    → 1_hanzi_evolution_字形演变
                  （文件名可含中文）
    解析失败或缺少 file_path 时回退为 prompt_id。
    """
    if file_path:
        # 2. 环境图片
        m = re.search(r"/scene_(\d+)/environments/([^/]+?)(?:\.[^/.]+)?$", file_path)
        if m:
            return f"{project_id}_{m.group(1)}_enviroment_{m.group(2)}"
        # 3. 字形过渡视频
        m = re.search(r"/hanzi/evolution/([^/]+?)(?:\.[^/.]+)?$", file_path)
        if m:
            return f"{project_id}_hanzi_evolution_{m.group(1)}"
        # 1. 分镜生成
        m = re.search(r"/scene_(\d+)/shots/(\d+)/([^/]+?)(?:\.[^/.]+)?$", file_path)
        if m:
            scene_idx, shot_idx, file_stem = m.groups()
            return f"{project_id}_{scene_idx}_{shot_idx}_{file_stem}"
    return prompt_id


async def submit_schedule_event(
    *,
    project_id: int,
    prompt_id: str,
    workflow_name: str,
    workflow_path: str | None,
    output_ids: list[str] | None,
    generation_type: str,
    file_path: str | None,
    project_name: str | None = None,
    user_id: int | None = None,
    step_id: int | None = None,
) -> str:
    """将调度事件直接提交到调度服务（调度器自行记录任务与队列状态）。

    project_name / user_id / step_id 由调用方（generation_monitor）解析后传入，
    用于调度器结果回传时对齐本地 GenerationResult。

    返回状态：
    - "ok"      已成功注册到调度器（同时将项目 schedule_status 置为 syncing）。
    - "invalid" workflow 缺失/损坏，无法提交（调用方应放弃重试）。
    - "error"   调度服务不可用或注册失败（调用方可稍后重试）。
    """
    workflow = _read_workflow(workflow_path)
    if workflow is None and workflow_path:
        logger.warning("ScheduleSync: skip submit for %s, workflow unreadable", prompt_id)
        return "invalid"

    business_task_id = _build_business_task_id(project_id, file_path, prompt_id)
    try:
        await schedule_client.register_task(
            business_task_id=business_task_id,
            project_id=str(project_id),
            workflow=workflow or {"missing": True},
            project_name=project_name,
            outputs_id=(output_ids[0] if output_ids else ""),
            extend_data={
                "step_id": step_id,
                "user_id": user_id,
                "prompt_id": prompt_id,
                "workflow_name": workflow_name,
                "generation_type": generation_type,
                "file_path": file_path,
            },
        )
    except ScheduleClientError as exc:
        logger.warning("ScheduleSync: submit failed for %s: %s", prompt_id, exc)
        return "error"

    # 提交成功 → 项目进入"调度中"状态
    try:
        async with async_session_factory() as session:
            result = await session.execute(select(Project).where(Project.id == project_id))
            proj = result.scalar_one_or_none()
            if proj:
                from datetime import datetime
                proj.schedule_status = "syncing"
                proj.schedule_updated_at = datetime.utcnow()
                await session.commit()
    except Exception:
        logger.exception("ScheduleSync: failed to mark project %s as syncing", project_id)
    return "ok"


def _read_workflow(workflow_path: str | None) -> dict[str, Any] | None:
    """读取 workflow JSON 文件；失败返回 None（调用方决定是否重试）。"""
    if not workflow_path:
        return None
    try:
        with open(workflow_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else None
    except (OSError, json.JSONDecodeError):
        logger.warning("ScheduleSync: cannot read workflow file %s", workflow_path)
        return None


# ── US4: 结果回传（调度结果 → 本地 GenerationResult）──

def _infer_type(file_path: str) -> str:
    name = Path(file_path).name.lower()
    if "last_frame" in name:
        return "last_frame"
    if "first_frame" in name:
        return "first_frame"
    if name.endswith((".mp4", ".mov", ".avi", ".webm", ".mkv")):
        return "video"
    if name.endswith((".flac", ".wav", ".mp3", ".ogg", ".aac", ".m4a")):
        return "audio"
    return "image"


def _pick_result_view(outputs: Any) -> str:
    """从调度器结果 outputs 中提取 result_view（ComfyUI view URL）。

    复刻调度器 _pick_view 的兜底分支：outputs 为 {node_id: {..., "view": url}} 分桶结构，
    取第一个含 view 的桶路径。
    """
    if not isinstance(outputs, dict):
        return ""
    for bucket in outputs.values():
        if isinstance(bucket, dict) and bucket.get("view"):
            return str(bucket["view"])
    return ""


def _normalize_view_url(url: str) -> str:
    """归一化调度器返回的 view URL host。

    调度器（192.168.3.4）返回的 view 为 http://127.0.0.1:8188/...（其本机视角），
    web 后端无法访问该地址；改为用 COMFYUI_BASE_URL 的 host 替换。
    """
    try:
        parsed = urlparse(url)
        base = urlparse(settings.COMFYUI_BASE_URL)
        if parsed.hostname in ("127.0.0.1", "localhost", "0.0.0.0") and base.hostname:
            scheme = parsed.scheme or base.scheme or "http"
            return urlunsplit((scheme, base.netloc, parsed.path, parsed.query, parsed.fragment))
    except Exception:
        pass
    return url


def _view_filename(url: str) -> str:
    """从 ComfyUI view URL 提取 filename 参数。"""
    q = urlparse(url).query
    return dict(kv.split("=", 1) for kv in q.split("&") if "=" in kv).get("filename", "")


def _derive_rel_path(project_id: int, result_id: str) -> str | None:
    """从 business_task_id 反向推导相对路径（与 _build_business_task_id 对称）。

    例: "1_0_3_video"           → "scene_0/shots/3/video"
         "1_0_enviroment_xx"     → "scene_0/enviroments/xx"
         "1_hanzi_evolution_字形" → "hanzi/evolution/字形"
    格式不符时返回 None（用于历史任务 extend_data 缺 file_path 的兜底）。
    """
    m = re.match(rf"^{project_id}_(\d+)_enviroment_(.+)$", result_id)
    if m:
        return f"scene_{m.group(1)}/environments/{m.group(2)}"
    m = re.match(rf"^{project_id}_hanzi_evolution_(.+)$", result_id)
    if m:
        return f"hanzi/evolution/{m.group(1)}"
    m = re.match(rf"^{project_id}_(\d+)_(\d+)_(.+)$", result_id)
    if not m:
        return None
    scene_idx, shot_idx, file_name = m.groups()
    return f"scene_{scene_idx}/shots/{shot_idx}/{file_name}"


async def _download_to(url: str, dst: Path) -> bool:
    """下载远程文件（ComfyUI view URL）到本地目标路径。"""
    try:
        async with httpx.AsyncClient(timeout=120.0, follow_redirects=True) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_bytes(resp.content)
            return True
    except Exception as exc:
        logger.warning("ScheduleSync: download %s -> %s failed: %s", url, dst, exc)
        return False


async def _sync_one_item(
    client: ScheduleClient,
    result_id: str,
    project_id: int,
    proj_cache: dict[int, str | None],
    stats: dict[str, Any],
) -> dict[str, Any] | None:
    """同步单个调度任务（纯网络 IO，不触碰 DB，可在并发阶段安全调用）。

    返回落库所需数据；跳过/无法下载已在 stats 计数，返回 None。
    FAILED 任务返回 {"_failed": True, ...}，由调用方串行创建失败记录并标记 sync。
    """
    try:
        remote = await client.get_result(result_id, project_id=str(project_id))
    except ScheduleClientError as exc:
        logger.warning("Sync result %s failed: %s", result_id, exc)
        stats["failed"] += 1
        stats["failed_ids"].append(result_id)
        return None

    status = (remote or {}).get("status", "").lower()

    # ── 解析调度器返回结构 ──
    # ResultResponse{status, result{outputs, view_urls, extend_data, has_sync}, failure_reason}
    result_data = (remote or {}).get("result") or {}
    extend = result_data.get("extend_data") or {}

    # 落库统一用 extend_data 里的 prompt_id（真实 prompt_id）；
    # 历史任务 extend_data 缺失该字段时回退 business_task_id（result_id）
    sync_prompt_id = (extend.get("prompt_id") or "").strip() or result_id

    # 源文件：result_view（ComfyUI view URL）→ 下载到本地目标路径
    result_view = _pick_result_view(result_data.get("outputs"))
    if result_view:
        result_view = _normalize_view_url(result_view)

    # 目标路径：extend_data.file_path → task_id 推导 → view filename 兜底
    target_path = extend.get("file_path")
    if not target_path:
        rel = _derive_rel_path(project_id, result_id)
        if rel and proj_cache.get(project_id):
            target_path = str(Path(proj_cache[project_id]) / rel)
    if not target_path and result_view:
        # 兜底：无法解析业务路径（如提交时无 file_path 且 task_id 非规则格式）时，
        # 用 view filename 落到 {working_dir}/outputs/，保证结果仍可下载同步。
        fname = _view_filename(result_view)
        if fname and proj_cache.get(project_id):
            target_path = str(Path(proj_cache[project_id]) / "outputs" / fname)

    # FAILED → 不下载；落库失败记录（带 error_message）+ 调 sync 状态接口，
    # 由调用方串行落库，避免调度器积压未同步任务。
    # 注意：FAILED 即使无法解析目标路径也照常标记，路径仅作记录占位。
    if status in ("failed", "error", "cancelled"):
        stats["failed"] += 1
        stats["failed_ids"].append(result_id)
        return {
            "_failed": True,
            "result_id": result_id,
            "project_id": project_id,
            "status": status,
            "remote": remote,
            "extend": extend,
            "sync_prompt_id": sync_prompt_id,
            "dst": Path(target_path) if target_path else None,
        }

    # SUCCESS 分支：目标路径必须可解析，否则本地无处落文件（保留未同步状态以便重试）
    if not target_path:
        logger.warning("Sync result %s: cannot resolve target path, skip", result_id)
        stats["skipped"] += 1
        stats["skipped_ids"].append(result_id)
        return None
    dst = Path(target_path)

    # 推导路径无扩展名时，从 view URL 的 filename 参数补后缀（video → video.mp4）
    if not dst.suffix and result_view:
        fname = _view_filename(result_view)
        if Path(fname).suffix:
            dst = dst.with_name(dst.name + Path(fname).suffix)

    # SUCCESS 且目标文件已存在：不下载、不重复落库，仅标记同步状态
    if dst.exists():
        logger.info("Sync result %s: %s already exists, skip", result_id, dst)
        stats["skipped"] += 1
        stats["skipped_ids"].append(result_id)
        return {
            "_failed": False,
            "_exists": True,
            "result_id": result_id,
            "project_id": project_id,
        }

    if not result_view:
        # 文件不存在且无 result_view → 无源可下载；不落库不标记，保留重试
        logger.warning("Sync result %s: no result_view and %s missing", result_id, dst)
        stats["failed"] += 1
        stats["failed_ids"].append(result_id)
        return None

    ok = await _download_to(result_view, dst)
    if not ok:
        stats["failed"] += 1
        stats["failed_ids"].append(result_id)
        return None

    stats["synced"] += 1
    return {
        "_failed": False,
        "result_id": result_id,
        "project_id": project_id,
        "dst": dst,
        "extend": extend,
        "sync_prompt_id": sync_prompt_id,
    }


async def pull_and_sync_results(
    db: AsyncSession,
    items: list[ScheduleResultSyncItem],
    *,
    client: ScheduleClient | None = None,
) -> dict[str, Any]:
    """    Pull scheduler results into local GenerationResult records (结果回传).

    对每个 business_task_id：查询调度服务 → 若本地不存在则复制文件并落库。
    SUCCESS → 保存输出并生成 GenerationResult；FAILED → 记录失败原因不落成功结果。

    返回 stats 含 synced/failed/skipped 计数及 failed_ids/skipped_ids 具体 task_id。

    性能：全程串行（一个任务完整处理完再处理下一个），避免并发请求
    调度器/并发写 SQLite 触发锁表。先落库后标记 sync，确保不丢失文件。
    """
    client = client or schedule_client
    stats: dict[str, Any] = {
        "synced": 0,
        "failed": 0,
        "skipped": 0,
        "failed_ids": [],
        "skipped_ids": [],
    }

    proj_cache = await _load_proj_cache(db, {i.project_id for i in items})

    for item in items:
        result_id = item.task_id
        project_id = item.project_id

        # 1) 拉取调度结果 + 下载输出文件（纯网络 IO）
        synced = await _sync_one_item(client, result_id, project_id, proj_cache, stats)
        if not synced:
            continue

        # 2) 串行落库（成功 / 失败记录 / 已存在仅确认）
        should_mark = await _persist_one(db, synced, stats)
        if not should_mark:
            continue

        # 3) 落库成功 → 提交 + 标记调度器 sync 状态（先落库后标记，确保不丢失文件）
        await db.commit()
        try:
            await client.sync_result(result_id, project_id=str(project_id))
        except ScheduleClientError as exc:
            logger.warning("Sync mark %s failed: %s", result_id, exc)

    await db.commit()  # 兜底（正常流程已逐条提交）
    return stats


async def _load_proj_cache(db: AsyncSession, project_ids: set[int]) -> dict[int, str | None]:
    """预加载项目 working_dir 缓存（同步全程只读复用，避免重复查询）。"""
    proj_cache: dict[int, str | None] = {}
    if project_ids:
        pr = await db.execute(select(Project).where(Project.id.in_(project_ids)))
        for p in pr.scalars():
            proj_cache[p.id] = p.working_dir
        for pid in project_ids:
            proj_cache.setdefault(pid, None)
    return proj_cache


async def _persist_one(db: AsyncSession, synced: dict[str, Any], stats: dict[str, Any]) -> bool:
    """串行落库单条同步结果。

    - FAILED → 创建失败记录（error_message）+ 审计，返回 True（需标记 sync）
    - 目标文件已存在 → 不重复落库，返回 True（需标记 sync）
    - 正常 → 创建 GenerationResult + 审计，返回 True
    无法落库（step 无法对齐等）→ 返回 False（不标记 sync，保留重试）
    """
    result_id = synced["result_id"]
    project_id = synced["project_id"]

    if synced["_failed"]:
        # FAILED → 创建失败记录（error_message）+ 审计，随后标记 sync，避免调度器积压
        from src.models.operation_log import OperationLog as OpLog
        remote = synced["remote"]
        dst = synced.get("dst")
        extend = synced["extend"]
        step_id, user_id = await _resolve_step_user(db, project_id, extend)
        if step_id is None:
            stats["failed"] += 1
            stats["failed_ids"].append(result_id)
            return False
        # 无真实文件：file_path 用可解析目标路径（或 task_id）占位，仅作失败留痕
        placeholder = str(dst) if dst else result_id
        db.add(GenerationResult(
            step_id=step_id,
            project_id=project_id,
            user_id=user_id or 1,
            file_path=placeholder,
            storage_path=placeholder,
            prompt_id=synced["sync_prompt_id"],
            workflow_name=extend.get("workflow_name") or "",
            generation_type=extend.get("generation_type") or "image",
            duration_seconds=0,
            error_message=str(
                remote.get("failure_reason")
                or remote.get("error")
                or remote.get("message")
                or ""
            ),
        ))
        db.add(OpLog(
            project_id=project_id,
            user_id=user_id or 1,
            operation_type="schedule_sync",
            target_type="generation_result",
            target_name=result_id,
            summary=f"调度任务失败: {synced['status']}",
            error_message=str(
                remote.get("failure_reason")
                or remote.get("error")
                or remote.get("message")
                or ""
            ),
        ))
        return True

    if synced.get("_exists"):
        # SUCCESS 且目标文件已存在：不下载、不重复落库，仅标记同步状态
        return True

    dst = synced["dst"]
    extend = synced["extend"]

    # ── 落库 GenerationResult（对齐提交时 extend_data 的 step_id/user_id） ──
    step_id, user_id = await _resolve_step_user(db, project_id, extend)
    if step_id is None:
        # 文件已下载但无法对齐 step → 不标记 sync，保留未同步状态以便重试
        stats["failed"] += 1
        stats["failed_ids"].append(result_id)
        return False

    db.add(GenerationResult(
        step_id=step_id,
        project_id=project_id,
        user_id=user_id or 1,
        file_path=str(dst),
        storage_path=str(dst),
        prompt_id=synced["sync_prompt_id"],
        workflow_name=extend.get("workflow_name") or "",
        # 文件名推断优先（first_frame/last_frame/video 等规范值），
        # 避免调度日志 type（如 image）覆盖导致前端 Prompt 按钮不显示
        generation_type=_infer_type(str(dst)) or extend.get("generation_type") or "image",
        duration_seconds=0,
    ))
    db.add(OperationLog(
        project_id=project_id,
        user_id=user_id or 1,
        operation_type="schedule_sync",
        target_type="generation_result",
        target_name=str(dst),
        summary=f"调度结果回传: {result_id}",
    ))
    return True


async def run_sync_background(items: list[ScheduleResultSyncItem]) -> None:
    """后台串行同步调度结果（Web 路由异步触发，前端不等待结果）。

    独立 session 执行，串行逐条处理避免 SQLite 锁表；完成后打印醒目日志。
    """
    try:
        async with async_session_factory() as session:
            stats = await pull_and_sync_results(session, items)
    except Exception:
        logger.exception("ScheduleSync: background sync crashed")
        return

    msg = (
        "================== [ScheduleSync] 调度结果同步完成 ==================\n"
        f"================== synced={stats['synced']}  "
        f"failed={stats['failed']}  skipped={stats['skipped']}\n"
        f"================== failed_ids={stats['failed_ids']}\n"
        f"================== skipped_ids={stats['skipped_ids']}\n"
        "================== =================================================="
    )
    print(msg, flush=True)
    logger.info(msg)


async def _resolve_step_user(
    db: AsyncSession,
    project_id: int,
    extend: dict[str, Any],
) -> tuple[int | None, int | None]:
    """从 extend_data 或本地项目解析 step_id / user_id（落库必填字段）。"""
    step_id = extend.get("step_id")
    user_id = extend.get("user_id")
    if step_id is not None and user_id is not None:
        return step_id, user_id
    pr = await db.execute(select(Project).where(Project.id == project_id))
    local_project = pr.scalar_one_or_none()
    if local_project:
        user_id = local_project.user_id or 1
        if step_id is None:
            from src.models.step import Step
            sr = await db.execute(
                select(Step).where(
                    Step.project_id == project_id,
                    Step.name == local_project.current_step_name,
                )
            )
            step = sr.scalar_one_or_none()
            if step is None:
                sr2 = await db.execute(
                    select(Step).where(Step.project_id == project_id)
                    .order_by(Step.step_order)
                )
                step = sr2.scalars().first()
            step_id = step.id if step else None
    return step_id, user_id
