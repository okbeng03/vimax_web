"""Operations API router — view operation logs, batch video processing, doubao collection."""

import json
import logging
import re
import shutil
import subprocess
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.database import get_db
from src.models.project import Project
from src.models.operation_log import OperationLog
from src.schemas.operation_log import OperationLogResponse, OperationLogListResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/projects", tags=["operations"])


def _process_videos(working_dir: str, project_id: int) -> None:
    """Background task: traverse scene_N/shots/N/, process videos.

    For each numbered shot dir containing doubao.mp4 + video_temp.mp4:
    1. ffmpeg resize video_temp.mp4 → video.mp4
    2. ffprobe get video duration
    3. Update shot_duration in shot_description.json / ltx_prompt.json
    4. Delete video_temp.mp4

    All progress is logged; no result aggregation is returned to the frontend.
    """
    base = Path(working_dir)
    scene_pattern = re.compile(r"^scene[_\s]*(\d+)$", re.IGNORECASE)
    processed = 0
    errors = 0

    for scene_entry in sorted(base.iterdir()):
        if not scene_entry.is_dir():
            continue
        sm = scene_pattern.match(scene_entry.name)
        if not sm:
            continue
        scene_num = int(sm.group(1))

        shots_dir = scene_entry / "shots"
        if not shots_dir.is_dir():
            continue

        for shot_entry in sorted(shots_dir.iterdir()):
            if not shot_entry.is_dir():
                continue
            try:
                shot_num = int(shot_entry.name)
            except ValueError:
                continue

            doubao_path = shot_entry / "doubao.mp4"
            temp_path = shot_entry / "video_temp.mp4"
            video_path = shot_entry / "video.mp4"

            if not doubao_path.exists() or not temp_path.exists():
                continue

            try:
                # Step 1: ffmpeg resize
                cmd = [
                    "ffmpeg", "-y", "-i", str(temp_path),
                    "-vf", "scale=1680:960:force_original_aspect_ratio=decrease,pad=1690:960:(ow-iw)/2:(oh-ih)/2",
                    "-c:v", "libx264", "-preset", "medium", "-crf", "23",
                    str(video_path),
                ]
                logger.info("scene_%d shot_%d: running ffmpeg", scene_num, shot_num)
                proc = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
                if proc.returncode != 0:
                    logger.error("scene_%d shot_%d: ffmpeg failed: %s", scene_num, shot_num, proc.stderr[-300:])
                    errors += 1
                    continue

                # Step 2: ffprobe get duration
                probe_cmd = [
                    "ffprobe", "-v", "error", "-show_entries", "format=duration",
                    "-of", "default=noprint_wrappers=1:nokey=1", str(video_path),
                ]
                probe_proc = subprocess.run(probe_cmd, capture_output=True, text=True, timeout=30)
                if probe_proc.returncode != 0:
                    logger.error("scene_%d shot_%d: ffprobe failed: %s", scene_num, shot_num, probe_proc.stderr[-200:])
                    errors += 1
                    continue

                video_duration = float(probe_proc.stdout.strip())
                logger.info("scene_%d shot_%d: video duration = %.2fs", scene_num, shot_num, video_duration)

                # Step 3: Update JSON files
                for jf_name in ("shot_description.json", "ltx_prompt.json"):
                    jf_path = shot_entry / jf_name
                    if not jf_path.exists():
                        logger.warning("scene_%d shot_%d: %s not found, skipping", scene_num, shot_num, jf_name)
                        continue
                    try:
                        data = json.loads(jf_path.read_text(encoding="utf-8"))
                        data["shot_duration"] = video_duration
                        jf_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
                        logger.info("scene_%d shot_%d: updated %s shot_duration=%.2f", scene_num, shot_num, jf_name, video_duration)
                    except (json.JSONDecodeError, OSError) as e:
                        logger.error("scene_%d shot_%d: failed to update %s: %s", scene_num, shot_num, jf_name, e)

                # Step 4: Delete video_temp.mp4
                try:
                    temp_path.unlink()
                    logger.info("scene_%d shot_%d: deleted video_temp.mp4", scene_num, shot_num)
                except OSError as e:
                    logger.error("scene_%d shot_%d: failed to delete video_temp.mp4: %s", scene_num, shot_num, e)

                processed += 1

            except subprocess.TimeoutExpired:
                logger.error("scene_%d shot_%d: ffmpeg timeout (10min)", scene_num, shot_num)
                errors += 1

    logger.info(
        "Batch video processing for project_id=%s finished: processed=%d errors=%d",
        project_id, processed, errors,
    )


def _collect_doubao(working_dir: str, project_id: int) -> None:
    """Background task: collect doubao.mp4 and flac files from scene_N/shots/N/.

    1. Create doubao/ directory under working_dir
    2. Scan scene_N/shots/N/ directories
    3. Copy doubao.mp4 → doubao/{scene_idx}_{shot_idx}.mp4
    4. Copy digit-starting *.flac → doubao/{scene_idx}_{shot_idx}_{idx}.flac
    """
    base = Path(working_dir)
    doubao_dir = base / "doubao"
    doubao_dir.mkdir(parents=True, exist_ok=True)

    scene_pattern = re.compile(r"^scene[_\s]*(\d+)$", re.IGNORECASE)
    collected_mp4 = 0
    collected_flac = 0
    errors = 0

    for scene_entry in sorted(base.iterdir()):
        if not scene_entry.is_dir():
            continue
        sm = scene_pattern.match(scene_entry.name)
        if not sm:
            continue
        scene_idx = int(sm.group(1))

        shots_dir = scene_entry / "shots"
        if not shots_dir.is_dir():
            continue

        for shot_entry in sorted(shots_dir.iterdir()):
            if not shot_entry.is_dir():
                continue
            try:
                shot_idx = int(shot_entry.name)
            except ValueError:
                continue

            # ── 3. Copy doubao.mp4 + digit-starting flac files ──
            doubao_path = shot_entry / "doubao.mp4"
            if doubao_path.exists():
                dest_name = f"{scene_idx}_{shot_idx}.mp4"
                dest_path = doubao_dir / dest_name
                try:
                    shutil.copy2(doubao_path, dest_path)
                    logger.info(
                        "scene_%d shot_%d: copied doubao.mp4 → %s",
                        scene_idx, shot_idx, dest_name,
                    )
                    collected_mp4 += 1
                except OSError as e:
                    logger.error(
                        "scene_%d shot_%d: failed to copy doubao.mp4: %s",
                        scene_idx, shot_idx, e,
                    )
                    errors += 1

                # ── 4. Only collect flac when doubao.mp4 exists ──
                flac_files = sorted(
                    f for f in shot_entry.glob("*.flac")
                    if re.match(r"^\d", f.name)
                )
                for idx, flac_path in enumerate(flac_files, start=1):
                    dest_name = f"{scene_idx}_{shot_idx}_{idx}.flac"
                    dest_path = doubao_dir / dest_name
                    try:
                        shutil.copy2(flac_path, dest_path)
                        logger.info(
                            "scene_%d shot_%d: copied %s → %s",
                            scene_idx, shot_idx, flac_path.name, dest_name,
                        )
                        collected_flac += 1
                    except OSError as e:
                        logger.error(
                            "scene_%d shot_%d: failed to copy %s: %s",
                            scene_idx, shot_idx, flac_path.name, e,
                        )
                        errors += 1

    logger.info(
        "Doubao collection for project_id=%s finished: mp4=%d flac=%d errors=%d → %s",
        project_id, collected_mp4, collected_flac, errors, str(doubao_dir),
    )


@router.get("/{project_id}/operations", response_model=OperationLogListResponse)
async def list_operations(
    project_id: int,
    type: str | None = None,
    page: int = 1,
    page_size: int = 50,
    db: AsyncSession = Depends(get_db),
):
    """List operation logs for a project."""
    proj_result = await db.execute(select(Project).where(Project.id == project_id))
    if not proj_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Project not found")

    query = select(OperationLog).options(selectinload(OperationLog.user)).where(OperationLog.project_id == project_id)
    if type:
        query = query.where(OperationLog.operation_type == type)

    count_query = select(func.count()).select_from(OperationLog).where(OperationLog.project_id == project_id)
    if type:
        count_query = count_query.where(OperationLog.operation_type == type)
    total = (await db.execute(count_query)).scalar() or 0

    query = query.order_by(OperationLog.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    logs = result.unique().scalars().all()

    return OperationLogListResponse(
        operations=[
            OperationLogResponse(
                id=log.id,
                operation_type=log.operation_type,
                target_type=log.target_type,
                target_id=log.target_id,
                target_name=log.target_name,
                summary=log.summary,
                details=log.details,
                error_message=log.error_message,
                user_name=log.user.display_name if log.user else None,
                created_at=log.created_at,
            )
            for log in logs
        ],
        total=total,
    )


@router.post("/{project_id}/batch-process-video")
async def batch_process_video(
    project_id: int,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """Launch batch video processing as a background task.

    Processing runs asynchronously — the endpoint returns immediately.
    Check server logs for per-shot progress and results.
    """
    proj_result = await db.execute(select(Project).where(Project.id == project_id))
    project = proj_result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    working_dir = project.working_dir
    if not working_dir or not Path(working_dir).exists():
        raise HTTPException(status_code=400, detail="Working directory not found")

    logger.info("Starting batch video processing for project_id=%s", project_id)
    background_tasks.add_task(_process_videos, working_dir, project_id)

    return {"message": "批量处理已启动，请查看服务端日志了解进度"}


@router.post("/{project_id}/collect-doubao")
async def collect_doubao(
    project_id: int,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """收集豆包素材：扫描 scene_N/shots/N/ 中的 doubao.mp4 和 .flac 文件，
    复制到 working_dir/doubao/ 目录下统一管理。
    """
    proj_result = await db.execute(select(Project).where(Project.id == project_id))
    project = proj_result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    working_dir = project.working_dir
    if not working_dir or not Path(working_dir).exists():
        raise HTTPException(status_code=400, detail="Working directory not found")

    logger.info("Starting doubao collection for project_id=%s", project_id)
    background_tasks.add_task(_collect_doubao, working_dir, project_id)

    return {"message": "豆包素材收集已启动，素材将保存至 working_dir/doubao/ 目录"}
