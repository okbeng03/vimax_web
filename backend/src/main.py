"""FastAPI application entry point."""

import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select, update

from src.config import settings
from src.database import init_db, async_session_factory, engine
from src.models.operation_log import OperationLog
from src.models.project import Project
from src.models.step import Step
from src.routers import templates, projects, steps, ws, files, generations, operations, stats, users
from src.services.vimax_runner import vimax_runner

# ── Ensure critical-path logs survive uvicorn reloads (file-based) ──
from pathlib import Path as _Path
_log_dir = _Path("data")
_log_dir.mkdir(exist_ok=True)
_fh = logging.FileHandler(_log_dir / "app.log", encoding="utf-8")
_fh.setLevel(logging.INFO)
_fh.setFormatter(logging.Formatter("%(asctime)s [%(name)s] %(levelname)s: %(message)s"))
_fh.stream.reconfigure(line_buffering=True)  # ensure immediate flush

for _name in ("src.services.vimax_runner", "src.routers.steps", "src.main"):
    _l = logging.getLogger(_name)
    _l.setLevel(logging.INFO)
    _l.addHandler(_fh)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: initialize DB, recover zombie running states, seed data.
    Shutdown: kill running ViMax process, record failure, dispose engine."""
    await init_db()
    await _startup_recovery()
    yield
    await _shutdown_handler()


async def _startup_recovery() -> None:
    """Startup recovery: fix dirty data + mark zombie running states as failed.

    1. Clean empty-string datetime columns (SQLite doesn't enforce types, and
       SQLAlchemy's datetime processor chokes on '').
    2. Mark any project stuck in 'running' as failed (covers crash / force-kill /
       restart scenarios where BackgroundTasks were lost).
    3. Reset vimax_runner singleton state.
    """
    err_msg = "Server restarted — execution interrupted"

    async with async_session_factory() as session:
        # ── Step 1: clean ALL empty-string datetime columns (SQLite type laxity) ──
        try:
            from sqlalchemy import text
            for table, cols in [
                ("steps", ["started_at", "completed_at"]),
                ("projects", ["completed_at", "updated_at", "created_at"]),
            ]:
                for col in cols:
                    await session.execute(
                        text(f"UPDATE {table} SET {col} = NULL WHERE {col} = ''")
                    )
            await session.commit()
        except Exception:
            logger.exception("Startup recovery: failed to clean empty datetime columns")
            await session.rollback()

        # ── Step 2: find true zombie projects (project + current step both "running") ──
        # A project with a "fully_complete" step is just waiting for user to click "continue"
        from sqlalchemy import text
        zombie_result = await session.execute(
            text("""
                SELECT p.id, p.current_step_name, p.name, p.user_id
                FROM projects p
                JOIN steps s ON s.project_id = p.id AND s.name = p.current_step_name
                WHERE p.status = 'running' AND s.status = 'running'
            """)
        )
        zombie_rows = zombie_result.all()

        if not zombie_rows:
            logger.info("Startup recovery: no zombie projects found")
            _reset_runner()
            return

        logger.warning(
            "Startup recovery: found %d zombie project(s) in 'running' state, marking as failed",
            len(zombie_rows),
        )

        # ── Step 3: mark zombie projects + their current steps as failed ──
        now = datetime.utcnow()
        for row in zombie_rows:
            pid, step_name, proj_name, uid = row

            await session.execute(
                update(Project)
                .where(Project.id == pid)
                .values(status="failed", completed_at=now, error_message=err_msg)
            )

            if step_name:
                await session.execute(
                    update(Step)
                    .where(
                        Step.project_id == pid,
                        Step.name == step_name,
                        Step.status == "running",
                    )
                    .values(status="failed", completed_at=now, error_message=err_msg)
                )

            session.add(OperationLog(
                project_id=pid,
                user_id=uid,
                operation_type="shutdown",
                target_type="project",
                target_name=proj_name,
                summary=err_msg,
                error_message=err_msg,
            ))
            logger.info(
                "Startup recovery: project_id=%s '%s' marked as failed",
                pid, proj_name,
            )

        await session.commit()

    # Reset runner singleton (fresh in-memory state after restart)
    _reset_runner()


def _reset_runner() -> None:
    vimax_runner._process = None
    vimax_runner._current_project_id = None
    vimax_runner._output_file = None
    vimax_runner._monitor_task = None


async def _shutdown_handler() -> None:
    """Graceful shutdown: kill any running subprocess, update DB, dispose engine.

    ── Race-condition note ──
    After kill(), the monitor_completion background task (launched in steps.py)
    may still be running.  It will see the process die (exit_code != 0) and try to
    mark project/step as "failed" concurrently with this handler.

    We give monitor_completion a brief window to finish, then do a catch-up
    update for any project that is still in "running" state.
    """

    # 1. Capture project id BEFORE kill (kill() clears _current_project_id)
    project_id: int | None = vimax_runner.current_project_id

    # 2. Kill the running ViMax subprocess
    if vimax_runner.is_running or project_id is not None:
        logger.info("Shutdown: killing ViMax process for project_id=%s", project_id)
        await vimax_runner.kill()

    # 3. Give monitor_completion a moment to finish its DB update
    if project_id is not None:
        await asyncio.sleep(0.3)

    # 4. Catch-up: mark any still-running project as failed
    if project_id is not None:
        err_msg = "Server shutdown — execution interrupted"
        try:
            async with async_session_factory() as session:
                result = await session.execute(
                    select(Project.id, Project.status, Project.current_step_name,
                           Project.name, Project.user_id)
                    .where(Project.id == project_id)
                )
                row = result.one_or_none()
                if row is None:
                    logger.warning("Shutdown: project_id=%s not found in DB", project_id)
                    return

                proj_status = row.status
                step_name = row.current_step_name

                if proj_status in ("failed", "completed"):
                    logger.info(
                        "Shutdown: project_id=%s already in terminal state '%s', skip",
                        project_id, proj_status,
                    )
                    return

                if proj_status == "running":
                    logger.info("Shutdown: marking project_id=%s as failed", project_id)
                    now = datetime.utcnow()
                    await session.execute(
                        update(Project)
                        .where(Project.id == project_id)
                        .values(status="failed", completed_at=now, error_message=err_msg)
                    )

                    if step_name:
                        await session.execute(
                            update(Step)
                            .where(
                                Step.project_id == project_id,
                                Step.name == step_name,
                                Step.status == "running",
                            )
                            .values(status="failed", completed_at=now, error_message=err_msg)
                        )

                    session.add(OperationLog(
                        project_id=project_id,
                        user_id=row.user_id,
                        operation_type="shutdown",
                        target_type="project",
                        target_name=row.name,
                        summary=err_msg,
                        error_message=err_msg,
                    ))
                    await session.commit()
                    logger.info("Shutdown: project_id=%s marked as failed", project_id)
        except Exception:
            logger.exception(
                "Shutdown: failed to update project_id=%s to failed — "
                "project may remain stuck in 'running' state", project_id
            )

    # 5. Dispose database engine
    await engine.dispose()


app = FastAPI(
    title="ViMax Web API",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(templates.router)
app.include_router(projects.router)
app.include_router(steps.router)
app.include_router(ws.router)
app.include_router(files.router)
app.include_router(generations.router)
app.include_router(operations.router)
app.include_router(stats.router)
app.include_router(users.router)


@app.get("/api/health")
async def health_check():
    return {"status": "ok"}
