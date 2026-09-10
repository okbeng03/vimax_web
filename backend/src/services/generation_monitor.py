"""Real-time generation result detection — polls vimax_output.tmp during execution.

Launched as a background task alongside VimaxRunner.monitor_completion.
Controlled by an asyncio.Event — monitor_completion sets it when the process exits,
which stops this monitor cleanly.
"""

import asyncio
from pathlib import Path

from sqlalchemy import select

from src.database import async_session_factory
from src.models.project import Project
from src.models.step import Step
from src.models.generation_result import GenerationResult
from src.services.generation_parser import GenerationParser
from src.services.schedule_log_parser import ScheduleLogParser
from src.services.schedule_sync import submit_schedule_event


async def _parse_and_persist_schedule(
    output_path: Path,
    project_id: int,
    schedule_parser: ScheduleLogParser,
    known_ids: set[str],
    cached_step: list[int | None],
) -> int:
    """Parse schedule events ([COMFYUI SCHEDULE]) and submit directly to the scheduler.

    Returns count of newly submitted schedule events. Each new event is submitted
    to the scheduler service immediately — the scheduler records task & queue state
    itself. Process-level dedup via known_ids; "invalid" events (unreadable workflow)
    are dropped after logging to avoid infinite retries, while transient scheduler
    errors are retried on the next poll.
    """
    events = schedule_parser.parse_file(str(output_path))
    if not events:
        return 0

    new_events = [e for e in events if e.prompt_id not in known_ids]
    if not new_events:
        return 0

    # ── 解析项目元信息（name / user_id / step_id），供调度器结果回传对齐 ──
    project_name: str | None = None
    user_id: int | None = None
    step_id = cached_step[0]
    async with async_session_factory() as session:
        proj_r = await session.execute(select(Project).where(Project.id == project_id))
        proj = proj_r.scalar_one_or_none()
        if proj:
            project_name = proj.name
            user_id = proj.user_id
            if step_id is None and proj.current_step_name:
                step_r = await session.execute(
                    select(Step).where(
                        Step.project_id == project_id,
                        Step.name == proj.current_step_name,
                    )
                )
                step_obj = step_r.scalar_one_or_none()
                if step_obj:
                    step_id = step_obj.id
                    cached_step[0] = step_id

    submitted = 0
    for evt in new_events:
        try:
            status = await submit_schedule_event(
                project_id=project_id,
                prompt_id=evt.prompt_id,
                workflow_name=evt.workflow_name,
                workflow_path=evt.workflow_path,
                output_ids=evt.output_ids,
                generation_type=evt.generation_type,
                file_path=evt.file_path,
                project_name=project_name,
                user_id=user_id,
                step_id=step_id,
            )
        except Exception:
            # 提交失败不应阻断常规生成结果解析
            print(f"[GenerationMonitor] submit_schedule_event failed for {evt.prompt_id}:", exc_info=True, flush=True)
            continue
        if status == "ok":
            known_ids.add(evt.prompt_id)
            submitted += 1
        elif status == "invalid":
            # workflow 缺失/损坏无法提交：标记已处理，避免无限重试
            known_ids.add(evt.prompt_id)
    return submitted


async def _parse_and_persist(
    output_path: Path,
    project_id: int,
    working_dir: str,
    known_ids: set[str],
    cached_step: list[int | None],
) -> int:
    """Parse full output file for new completed generations, persist to DB.
    Uses known_ids set for dedup (prompt_id).  Returns count of new records."""
    parsed = GenerationParser.parse_file(str(output_path), working_dir)
    if not parsed:
        return 0

    # Only insert complete results (has output file + finish time) that we haven't seen
    new_gens = [
        g for g in parsed
        if g.get("prompt_id") and g.get("output_path") and g.get("end_time")
        and g["prompt_id"] not in known_ids
    ]
    if not new_gens:
        return 0

    inserted = 0
    async with async_session_factory() as session:
        # ── Resolve step_id (cached across cycles) ──
        step_id = cached_step[0]
        if step_id is None:
            proj_r = await session.execute(select(Project).where(Project.id == project_id))
            proj = proj_r.scalar_one_or_none()
            if proj and proj.current_step_name:
                step_r = await session.execute(
                    select(Step).where(
                        Step.project_id == project_id,
                        Step.name == proj.current_step_name,
                    )
                )
                step_obj = step_r.scalar_one_or_none()
                if step_obj:
                    step_id = step_obj.id
                    cached_step[0] = step_id

        for gen in new_gens:
            pid = gen["prompt_id"]
            # DB-level dedup (belt-and-suspenders)
            exist_r = await session.execute(
                select(GenerationResult).where(
                    GenerationResult.project_id == project_id,
                    GenerationResult.prompt_id == pid,
                )
            )
            if exist_r.scalar_one_or_none():
                known_ids.add(pid)
                continue

            if step_id is None:
                known_ids.add(pid)
                continue

            session.add(GenerationResult(
                step_id=step_id,
                project_id=project_id,
                user_id=1,
                file_path=gen["output_path"],
                storage_path=gen["output_path"],
                prompt_id=pid,
                workflow_name=gen.get("workflow_name", ""),
                generation_type=gen["generation_type"],
                duration_seconds=gen["duration_seconds"],
            ))
            known_ids.add(pid)
            inserted += 1

        if inserted > 0:
            await session.commit()

    return inserted


async def monitor_generations_realtime(
    project_id: int,
    working_dir: str,
    stop_event: asyncio.Event,
) -> None:
    """Poll vimax_output.tmp every 0.5s, parse and persist new generation results.

    Stops when stop_event is set — this is signalled by monitor_completion
    after the subprocess exits (including on kill / error).
    """
    output_path = Path(working_dir) / "vimax_output.tmp"
    known_ids: set[str] = set()
    cached_step: list[int | None] = [None]
    schedule_parser = ScheduleLogParser()
    known_schedule_ids: set[str] = set()

    # ── Initial parse on start (catch results already in log) ──
    if output_path.exists():
        await _parse_and_persist(output_path, project_id, working_dir, known_ids, cached_step)
        await _parse_and_persist_schedule(output_path, project_id, schedule_parser, known_schedule_ids, cached_step)

    # ── Poll loop ──
    while not stop_event.is_set():
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=0.5)
            break  # event was set during wait
        except asyncio.TimeoutError:
            pass  # timeout → time to poll

        if output_path.exists():
            await _parse_and_persist(output_path, project_id, working_dir, known_ids, cached_step)
            await _parse_and_persist_schedule(output_path, project_id, schedule_parser, known_schedule_ids, cached_step)

    # ── Final sweep after stop (belt-and-suspenders) ──
    if output_path.exists():
        await _parse_and_persist(output_path, project_id, working_dir, known_ids, cached_step)
        await _parse_and_persist_schedule(output_path, project_id, schedule_parser, known_schedule_ids, cached_step)
