"""ViMax subprocess manager — singleton controlling pipeline execution."""

import asyncio
import os
import time
from datetime import datetime
from pathlib import Path

from src.services.config_sync import ConfigSyncService


class VimaxRunner:
    """Global singleton for managing a single ViMax subprocess. Enforces FR-011 (max 1 running)."""

    _instance: "VimaxRunner | None" = None
    _process: asyncio.subprocess.Process | None = None
    _current_project_id: int | None = None
    _output_file = None
    _monitor_task: asyncio.Task | None = None
    _on_complete_callback = None

    def __new__(cls) -> "VimaxRunner":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    @property
    def is_running(self) -> bool:
        return self._process is not None and self._process.returncode is None

    @property
    def current_project_id(self) -> int | None:
        return self._current_project_id

    @property
    def exit_code(self) -> int | None:
        """Return subprocess exit code, or None if still running / not started."""
        if self._process:
            return self._process.returncode
        return None

    async def start(
        self,
        project_id: int,
        working_dir: str,
        interrupt_step: str,
        vimax_root: str,
    ) -> None:
        """Launch ViMax subprocess. Raises RuntimeError if another project is running."""
        if self.is_running:
            raise RuntimeError(f"Another project (id={self._current_project_id}) is already running")

        # Update interrupt_step in project's working_dir YAML
        ConfigSyncService.write_interrupt_step(working_dir, interrupt_step)
        # Sync updated YAML to VIMAX_ROOT/configs/ so the script (run from VIMAX_ROOT) picks it up
        ConfigSyncService.sync_project_to_vimax(working_dir, vimax_root)

        output_path = Path(working_dir) / "vimax_output.tmp"

        self._output_file = open(output_path, "w")

        venv_python = str(Path(vimax_root) / ".venv" / "bin" / "python")
        args = [venv_python, "main_idea2video.py"]
        if interrupt_step:
            args.extend(["--interrupt-step", interrupt_step])
        self._process = await asyncio.create_subprocess_exec(
            *args,
            cwd=vimax_root,
            stdout=self._output_file,
            stderr=self._output_file,
            env={**os.environ, "PYTHONUNBUFFERED": "1"},
        )
        self._current_project_id = project_id

    async def monitor_completion(
        self,
        project_id: int,
        session_factory,
    ) -> None:
        """Background task: wait for subprocess exit, update DB, clean up.
        Must be called after start().  session_factory is an async context manager
        factory (e.g. lambda: async_session_factory())."""
        import logging
        _log = logging.getLogger(__name__)

        if not self._process:
            _log.warning("monitor_completion: no process to wait for (pid=%s)", project_id)
            return

        _log.info("monitor_completion: waiting for process exit (pid=%s, subprocess_pid=%s)",
                  project_id, self._process.pid)
        try:
            await self._process.wait()
        except Exception:
            _log.exception("monitor_completion: process.wait() raised")

        exit_code = self._process.returncode
        _log.info("monitor_completion: process exited (pid=%s, exit_code=%s)", project_id, exit_code)

        # Flush and close file handle so WS sees all content
        if self._output_file:
            self._output_file.flush()
            self._output_file.close()
            self._output_file = None

        # ── Parse ComfyUI generations + update DB after subprocess exit ──
        from src.models.project import Project
        from src.models.step import Step
        from src.models.template import Template
        from src.models.generation_result import GenerationResult
        from src.services.generation_parser import GenerationParser
        from src.services.progress_manager import get_template_progress, is_last_step
        from sqlalchemy import select, update as sqla_update

        _log.info("monitor_completion: entering DB update section (pid=%s, exit_code=%s)", project_id, exit_code)
        async with session_factory() as session:
            try:
                # ── Load project metadata (avoid full object → datetime parse risk) ──
                proj_row = (
                    await session.execute(
                        select(
                            Project.id, Project.status, Project.current_step_name,
                            Project.template_id, Project.user_id, Project.working_dir,
                        ).where(Project.id == project_id)
                    )
                ).one_or_none()
                if not proj_row:
                    _log.warning("monitor_completion: project %s not found", project_id)
                    return

                _pid, proj_status, step_name, tmpl_id, uid, working_dir = proj_row
                output_path = Path(working_dir) / "vimax_output.tmp"

                # ── Try to parse generations (best-effort; don't block status update) ──
                parsed_generations: list[dict] = []
                try:
                    parsed_generations = GenerationParser.parse_file(
                        str(output_path), working_dir
                    )
                except Exception:
                    _log.exception("Failed to parse generation output for project %s", project_id)

                # Resolve step id (only need the PK)
                current_step_id: int | None = None
                if step_name:
                    sid_row = (
                        await session.execute(
                            select(Step.id).where(
                                Step.project_id == project_id,
                                Step.name == step_name,
                            )
                        )
                    ).scalar_one_or_none()
                    current_step_id = sid_row

                # Persist each new generation (skip if no step or duplicate prompt_id)
                for gen in parsed_generations:
                    if current_step_id is None:
                        continue
                    if not gen.get("output_path"):
                        continue
                    try:
                        existing = await session.execute(
                            select(GenerationResult).where(
                                GenerationResult.project_id == project_id,
                                GenerationResult.prompt_id == gen["prompt_id"],
                            )
                        )
                        if existing.scalar_one_or_none():
                            continue

                        db_gen = GenerationResult(
                            step_id=current_step_id,
                            project_id=project_id,
                            user_id=uid,
                            file_path=gen["output_path"],
                            storage_path=gen["output_path"],
                            prompt_id=gen["prompt_id"],
                            workflow_name=gen.get("workflow_name", ""),
                            generation_type=gen["generation_type"],
                            duration_seconds=gen["duration_seconds"],
                        )
                        session.add(db_gen)
                    except Exception:
                        _log.exception("Failed to persist generation for project %s", project_id)

                # ── Extract error tail from output file on failure ──
                error_tail: str | None = None
                if exit_code != 0:
                    try:
                        lines = output_path.read_text(errors="replace").splitlines()
                        tail = lines[-20:]
                        error_tail = "\n".join(tail) if tail else f"Process exited with code {exit_code}"
                    except Exception:
                        error_tail = f"Process exited with code {exit_code}"

                # ── Update project / step status (use update() to avoid datetime parse risk) ──
                now = datetime.utcnow()
                step_new_status = "fully_complete" if exit_code == 0 else "failed"

                if exit_code != 0:
                    await session.execute(
                        sqla_update(Project)
                        .where(Project.id == project_id)
                        .values(status="failed", completed_at=now,
                                error_message=error_tail or f"Process exited with code {exit_code}")
                    )

                if step_name:
                    # Compute duration from started_at if available
                    duration: float | None = None
                    try:
                        started = (
                            await session.execute(
                                select(Step.started_at).where(
                                    Step.project_id == project_id,
                                    Step.name == step_name,
                                )
                            )
                        ).scalar_one_or_none()
                        if started:
                            duration = (now - started).total_seconds()
                    except Exception:
                        pass  # best-effort; started_at may be dirty

                    await session.execute(
                        sqla_update(Step)
                        .where(
                            Step.project_id == project_id,
                            Step.name == step_name,
                        )
                        .values(
                            status=step_new_status,
                            completed_at=now,
                            duration_seconds=duration,
                            error_message=(error_tail if exit_code != 0 else None),
                        )
                    )
                    _log.info(
                        "monitor_completion: project=%s exit_code=%s step=%s step_status=%s",
                        project_id, exit_code, step_name, step_new_status,
                    )

                # ── Auto-complete project when last step finishes successfully ──
                if exit_code == 0 and step_name and tmpl_id:
                    try:
                        tmpl_result = await session.execute(
                            select(Template).where(Template.id == tmpl_id)
                        )
                        template = tmpl_result.scalar_one_or_none()
                        if template:
                            progress_steps = get_template_progress(template.directory_name)
                            if is_last_step(progress_steps, step_name):
                                await session.execute(
                                    sqla_update(Project)
                                    .where(Project.id == project_id)
                                    .values(status="completed", completed_at=now)
                                )
                                _log.info(
                                    "Project %s auto-completed (last step '%s' finished successfully)",
                                    project_id, step_name,
                                )
                    except Exception:
                        _log.exception("Failed to check last-step for project %s", project_id)

                _log.info("monitor_completion: committing DB (pid=%s)", project_id)
                await session.commit()
                _log.info("monitor_completion: DB committed successfully (pid=%s, step=%s, step_status=%s)",
                          project_id, step_name, step_new_status)

            except Exception:
                _log.exception("monitor_completion failed for project %s", project_id)
                try:
                    await session.rollback()
                except Exception:
                    pass

        self._process = None
        self._current_project_id = None

    async def kill(self) -> None:
        """Force kill the running ViMax process."""
        if self._monitor_task and not self._monitor_task.done():
            self._monitor_task.cancel()
            self._monitor_task = None

        if self._process and self._process.returncode is None:
            self._process.kill()
            try:
                await asyncio.wait_for(self._process.wait(), timeout=10)
            except asyncio.TimeoutError:
                pass

        # Clean up file handle
        if self._output_file:
            self._output_file.flush()
            self._output_file.close()
            self._output_file = None

        self._process = None
        self._current_project_id = None

    async def wait(self) -> int | None:
        """Wait for process completion, return exit code."""
        if self._process:
            return await self._process.wait()
        return None

    def get_current_project_id(self) -> int | None:
        return self._current_project_id


# Global singleton instance
vimax_runner = VimaxRunner()
