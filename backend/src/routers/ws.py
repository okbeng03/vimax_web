"""WebSocket endpoint for real-time ViMax output streaming.

Generation result detection is handled independently by
src.services.generation_monitor (background task launched in steps.py).
"""

import asyncio
from pathlib import Path

import aiofiles
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy import select

from src.database import async_session_factory
from src.models.project import Project
from src.models.step import Step

router = APIRouter()


async def _tail_stream(websocket: WebSocket, file_path: Path, last_pos: int) -> int:
    """Read new content from file since last_pos, send via WS as 'output'.
    Returns updated last_pos.  If file was truncated, resets to 0 and sends clear signal."""
    if file_path.exists():
        file_size = file_path.stat().st_size
        # Detect truncation (new step started → file truncated with "w")
        if file_size < last_pos:
            await websocket.send_json({"type": "clear"})
            last_pos = 0

        async with aiofiles.open(file_path, "r") as f:
            await f.seek(last_pos)
            new_content = await f.read()
            if new_content:
                await websocket.send_json({
                    "type": "output",
                    "content": new_content,
                })
                last_pos = await f.tell()
    return last_pos


@router.websocket("/ws/projects/{project_id}/stdout")
async def stdout_websocket(websocket: WebSocket, project_id: int):
    """Stream ViMax output from temp file to client via WebSocket.
    Detects step completion (send step_ready) and process final result."""
    await websocket.accept()

    async with async_session_factory() as session:
        result = await session.execute(select(Project).where(Project.id == project_id))
        project = result.scalar_one_or_none()
        if not project:
            await websocket.send_json({"type": "error", "message": "Project not found"})
            await websocket.close()
            return

        working_dir = project.working_dir
        output_path = Path(working_dir) / "vimax_output.tmp"

    last_pos = 0
    prev_step_status = None
    final_sent = False

    # ── Send initial state on connect (handles late WS connection after step already completed) ──
    async with async_session_factory() as session:
        result = await session.execute(select(Project).where(Project.id == project_id))
        project = result.scalar_one_or_none()
        if not project:
            await websocket.close()
            return

        # Terminal state → send final status and disconnect
        if project.status in ("completed", "failed"):
            await _tail_stream(websocket, output_path, 0)
            await websocket.send_json({
                "type": "status",
                "project_status": project.status,
                "step_name": project.current_step_name,
                "error_message": project.error_message,
            })
            await websocket.close()
            return

        # Step already fully_complete (subprocess exited, client connecting late) → send step_ready
        # Frontend will disconnect WS upon receipt, then poll /progress
        if project.current_step_name:
            step_result = await session.execute(
                select(Step).where(
                    Step.project_id == project_id,
                    Step.name == project.current_step_name,
                )
            )
            step = step_result.scalar_one_or_none()
            if step and step.status == "fully_complete":
                await websocket.send_json({
                    "type": "step_ready",
                    "step_name": step.name,
                    "step_status": step.status,
                })
                prev_step_status = step.status

    try:
        while True:
            # Stream merged output
            last_pos = await _tail_stream(websocket, output_path, last_pos)

            # Check project + step status
            async with async_session_factory() as session:
                result = await session.execute(select(Project).where(Project.id == project_id))
                project = result.scalar_one_or_none()

                if not project:
                    break

                # Check if project reached terminal state
                if project.status in ("completed", "failed") and not final_sent:
                    last_pos = await _tail_stream(websocket, output_path, last_pos)
                    await websocket.send_json({
                        "type": "status",
                        "project_status": project.status,
                        "step_name": project.current_step_name,
                        "error_message": project.error_message,
                    })
                    final_sent = True
                    await websocket.close()
                    return

                # Detect step completion (still running, but step status changed)
                if project.current_step_name:
                    step_result = await session.execute(
                        select(Step).where(
                            Step.project_id == project_id,
                            Step.name == project.current_step_name,
                        )
                    )
                    step = step_result.scalar_one_or_none()
                    if step and step.status != prev_step_status:
                        prev_step_status = step.status
                        if step.status == "fully_complete":
                            await websocket.send_json({
                                "type": "step_ready",
                                "step_name": step.name,
                                "step_status": step.status,
                            })
                        elif step.status == "failed":
                            await websocket.send_json({
                                "type": "status",
                                "project_status": "failed",
                                "step_name": step.name,
                                "error_message": step.error_message or project.error_message,
                            })
                            final_sent = True
                            await websocket.close()
                            return

            await asyncio.sleep(0.5)
    except WebSocketDisconnect:
        pass
    except Exception:
        await websocket.close()
