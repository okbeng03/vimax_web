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

    # ── Initial parse on start (catch results already in log) ──
    if output_path.exists():
        await _parse_and_persist(output_path, project_id, working_dir, known_ids, cached_step)

    # ── Poll loop ──
    while not stop_event.is_set():
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=0.5)
            break  # event was set during wait
        except asyncio.TimeoutError:
            pass  # timeout → time to poll

        if output_path.exists():
            await _parse_and_persist(output_path, project_id, working_dir, known_ids, cached_step)

    # ── Final sweep after stop (belt-and-suspenders) ──
    if output_path.exists():
        await _parse_and_persist(output_path, project_id, working_dir, known_ids, cached_step)
