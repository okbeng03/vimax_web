"""Statistics computation service."""

from datetime import datetime, timedelta
from sqlalchemy import select, func, and_, or_, case
from sqlalchemy.ext.asyncio import AsyncSession
from src.models.project import Project
from src.models.step import Step
from src.models.generation_result import GenerationResult
from src.models.operation_log import OperationLog


def _categorize_error(msg: str | None) -> str:
    """Categorize step error messages into human-readable groups."""
    if not msg:
        return "未知错误"
    lower = msg.lower()
    if "timeout" in lower:
        return "超时"
    if "connection" in lower or "connect" in lower or "refused" in lower:
        return "连接失败"
    if "kill" in lower or "terminated" in lower or "killed" in lower:
        return "手动终止"
    if "api" in lower and ("error" in lower or "fail" in lower):
        return "API 错误"
    if "validation" in lower or "invalid" in lower:
        return "数据校验失败"
    if "not found" in lower or "missing" in lower:
        return "文件缺失"
    # Shorten long messages
    return msg[:40] + ("..." if len(msg) > 40 else "")


# ── Config file patterns to filter out (noise in operation log stats) ──
_CONFIG_FILE_SUFFIXES = (".yaml", ".yml", ".py")


def _is_config_edit(target_name: str | None) -> bool:
    """Check if an edit target is a config/yaml/python file (boilerplate edits on every run)."""
    if not target_name:
        return False
    return target_name.endswith(_CONFIG_FILE_SUFFIXES)


class StatisticsService:
    """Compute project and global statistics via SQL aggregation."""

    @staticmethod
    async def project_stats(db: AsyncSession, project_id: int) -> dict:
        """Project-level statistics."""
        # Step durations + status + error
        step_result = await db.execute(
            select(
                Step.name,
                Step.status,
                Step.duration_seconds,
                Step.error_message,
                Step.retry_count,
                Step.step_order,
            ).where(Step.project_id == project_id).order_by(Step.step_order)
        )
        steps_data = [
            {
                "name": r.name,
                "duration": r.duration_seconds or 0,
                "status": r.status,
                "error_message": r.error_message,
                "retry_count": r.retry_count,
            }
            for r in step_result
        ]

        # Operation log summary (recent activity count by type) — exclude config file edits
        op_result = await db.execute(
            select(
                OperationLog.operation_type,
                func.count(OperationLog.id).label("cnt"),
            )
            .where(OperationLog.project_id == project_id)
            .group_by(OperationLog.operation_type)
        )
        operation_summary = {r.operation_type: r.cnt for r in op_result}

        # ── T093: Subtract config(yaml/py) edit counts from edit_file total ──
        config_edit_count = await db.scalar(
            select(func.count(OperationLog.id))
            .where(
                and_(
                    OperationLog.project_id == project_id,
                    OperationLog.operation_type == "edit_file",
                    or_(
                        OperationLog.target_name.like("%.yaml"),
                        OperationLog.target_name.like("%.yml"),
                        OperationLog.target_name.like("%.py"),
                    ),
                )
            )
        ) or 0
        if "edit_file" in operation_summary and config_edit_count > 0:
            operation_summary["edit_file"] = max(0, operation_summary["edit_file"] - config_edit_count)
            operation_summary["edit_file_config"] = config_edit_count  # separate counter for transparency

        # Step status breakdown
        status_counts = {"pending": 0, "running": 0, "fully_complete": 0, "partially_complete": 0, "failed": 0}
        for s in steps_data:
            st = s["status"]
            if st in status_counts:
                status_counts[st] += 1

        total_steps = len(steps_data)
        completed_steps = status_counts["fully_complete"] + status_counts["partially_complete"]
        failed_steps = status_counts["failed"]

        # ── ComfyUI generation stats ──
        gen_total = await db.scalar(
            select(func.count()).select_from(GenerationResult).where(GenerationResult.project_id == project_id)
        ) or 0
        gen_success = await db.scalar(
            select(func.count()).select_from(GenerationResult).where(
                and_(GenerationResult.project_id == project_id, GenerationResult.error_message.is_(None))
            )
        ) or 0
        gen_failed = gen_total - gen_success

        # Generations by type (first_frame / last_frame / video / image / audio)
        gen_type_rows = await db.execute(
            select(
                GenerationResult.generation_type,
                func.count(GenerationResult.id).label("cnt"),
            )
            .where(GenerationResult.project_id == project_id)
            .group_by(GenerationResult.generation_type)
        )
        generations_by_type = [
            {"type": r.generation_type, "count": r.cnt}
            for r in gen_type_rows
        ]

        # Generations by step (join via step_id)
        gen_step_rows = await db.execute(
            select(
                Step.name,
                func.count(GenerationResult.id).label("total"),
                func.sum(case((GenerationResult.error_message.is_(None), 1), else_=0)).label("success"),
            )
            .join(GenerationResult, GenerationResult.step_id == Step.id)
            .where(GenerationResult.project_id == project_id)
            .group_by(Step.name)
            .order_by(Step.step_order)
        )
        generations_by_step = [
            {"step_name": r.name, "total": r.total, "success": r.success or 0, "failed": r.total - (r.success or 0)}
            for r in gen_step_rows
        ]

        # Duration distribution — buckets: 0-10s, 10-30s, 30-60s, 60-120s, 120s+
        dur_rows = await db.execute(
            select(
                func.sum(case((GenerationResult.duration_seconds <= 10, 1), else_=0)).label("_0_10"),
                func.sum(case((and_(GenerationResult.duration_seconds > 10, GenerationResult.duration_seconds <= 30), 1), else_=0)).label("_10_30"),
                func.sum(case((and_(GenerationResult.duration_seconds > 30, GenerationResult.duration_seconds <= 60), 1), else_=0)).label("_30_60"),
                func.sum(case((and_(GenerationResult.duration_seconds > 60, GenerationResult.duration_seconds <= 120), 1), else_=0)).label("_60_120"),
                func.sum(case((GenerationResult.duration_seconds > 120, 1), else_=0)).label("_120_plus"),
            )
            .where(and_(
                GenerationResult.project_id == project_id,
                GenerationResult.duration_seconds > 0,
            ))
        )
        dur_row = dur_rows.one_or_none()
        duration_buckets = [
            {"range": "0-10s", "count": dur_row._0_10 or 0 if dur_row else 0},
            {"range": "10-30s", "count": dur_row._10_30 or 0 if dur_row else 0},
            {"range": "30-60s", "count": dur_row._30_60 or 0 if dur_row else 0},
            {"range": "60-120s", "count": dur_row._60_120 or 0 if dur_row else 0},
            {"range": "120s+", "count": dur_row._120_plus or 0 if dur_row else 0},
        ]

        # Average duration by generation type
        gen_dur_rows = await db.execute(
            select(
                GenerationResult.generation_type,
                func.avg(GenerationResult.duration_seconds).label("avg_dur"),
            )
            .where(and_(
                GenerationResult.project_id == project_id,
                GenerationResult.duration_seconds > 0,
            ))
            .group_by(GenerationResult.generation_type)
        )
        avg_duration_by_type = [
            {"type": r.generation_type, "avg_duration": round(float(r.avg_dur), 1)}
            for r in gen_dur_rows
        ]

        total_duration_seconds = await db.scalar(
            select(func.sum(GenerationResult.duration_seconds))
            .where(GenerationResult.project_id == project_id)
        ) or 0

        # ── Log-based step retry analysis (linked to actual steps) ──
        log_analysis = await StatisticsService._step_log_analysis(db, project_id)

        return {
            "scene_count": 0,  # Requires filesystem scan — deferred
            "file_counts": {},
            "total_file_size_mb": 0,
            "total_duration_seconds": float(total_duration_seconds),
            "step_overview": {
                "total": total_steps,
                "completed": completed_steps,
                "failed": failed_steps,
                "running": status_counts["running"],
                "pending": status_counts["pending"],
                "success_rate": completed_steps / total_steps if total_steps else 0,
            },
            "steps": steps_data,
            "operation_summary": operation_summary,
            "generation_stats": {
                "total": gen_total,
                "success": gen_success,
                "failed": gen_failed,
                "success_rate": gen_success / gen_total if gen_total else 0,
            },
            "generations_by_type": generations_by_type,
            "generations_by_step": generations_by_step,
            "duration_buckets": duration_buckets,
            "avg_duration_by_type": avg_duration_by_type,
            "step_log_retries": log_analysis["steps"],
            "step_log_retry_summary": log_analysis["summary"],
        }

    @staticmethod
    async def _step_log_analysis(db: AsyncSession, project_id: int) -> dict:
        """Analyse operation_log to derive per-step retry/confirm/reject counts,
        linked to actual Step records (skip standalone operations like generation
        confirmations that don't map to a step).

        Returns {"steps": [...], "summary": {...}}.
        """
        # Step 1: Get actual step names for this project
        step_name_rows = await db.execute(
            select(Step.name, Step.retry_count)
            .where(Step.project_id == project_id)
            .order_by(Step.step_order)
        )
        step_names = [(r.name, r.retry_count or 0) for r in step_name_rows]
        if not step_names:
            return {"steps": [], "summary": None}

        # Step 2: Query operation logs, mapping to step names.
        # Two sources for regenerate_step:
        #   a) steps.py writes target_type="step", target_name=step_name (e.g. "video")
        #   b) generations.py writes target_type="generation_result", target_name=file_path
        # For (a) we use target_name directly; for (b) we join via target_id.
        # Use outerjoin + coalesce to handle both cases.

        _step_name_expr = func.coalesce(Step.name, OperationLog.target_name)

        # regenerate_step
        regenerate_rows = await db.execute(
            select(
                _step_name_expr.label("name"),
                func.count(OperationLog.id).label("cnt"),
            )
            .select_from(OperationLog)
            .outerjoin(GenerationResult, OperationLog.target_id == GenerationResult.id)
            .outerjoin(Step, GenerationResult.step_id == Step.id)
            .where(
                and_(
                    OperationLog.project_id == project_id,
                    OperationLog.operation_type == "regenerate_step",
                )
            )
            .group_by(_step_name_expr)
        )
        log_retry_map: dict[str, int] = {r.name: r.cnt for r in regenerate_rows if r.name}

        # confirm_result
        confirm_rows = await db.execute(
            select(
                _step_name_expr.label("name"),
                func.count(OperationLog.id).label("cnt"),
            )
            .select_from(OperationLog)
            .outerjoin(GenerationResult, OperationLog.target_id == GenerationResult.id)
            .outerjoin(Step, GenerationResult.step_id == Step.id)
            .where(
                and_(
                    OperationLog.project_id == project_id,
                    OperationLog.operation_type == "confirm_result",
                )
            )
            .group_by(_step_name_expr)
        )
        confirm_map: dict[str, int] = {r.name: r.cnt for r in confirm_rows if r.name}

        # cancel_result (treated as "reject" in the frontend distribution chart)
        cancel_rows = await db.execute(
            select(
                _step_name_expr.label("name"),
                func.count(OperationLog.id).label("cnt"),
            )
            .select_from(OperationLog)
            .outerjoin(GenerationResult, OperationLog.target_id == GenerationResult.id)
            .outerjoin(Step, GenerationResult.step_id == Step.id)
            .where(
                and_(
                    OperationLog.project_id == project_id,
                    OperationLog.operation_type == "cancel_result",
                )
            )
            .group_by(_step_name_expr)
        )
        cancel_map: dict[str, int] = {r.name: r.cnt for r in cancel_rows if r.name}

        # Step 3: Build per-step list
        steps: list[dict] = []
        total_log_retries = 0
        max_log_retries = 0
        max_log_retry_step = ""
        total_db_retries = 0
        total_confirms = 0
        total_rejects = 0
        steps_with_retries = 0

        for name, db_rc in step_names:
            log_rc = log_retry_map.get(name, 0)
            step_data = {
                "step_name": name,
                "db_retry_count": db_rc,
                "log_retry_count": log_rc,
                "confirm_count": confirm_map.get(name, 0),
                "reject_count": cancel_map.get(name, 0),
            }
            steps.append(step_data)

            if log_rc > 0:
                steps_with_retries += 1
            total_log_retries += log_rc
            total_db_retries += db_rc
            total_confirms += step_data["confirm_count"]
            total_rejects += step_data["reject_count"]
            if log_rc > max_log_retries:
                max_log_retries = log_rc
                max_log_retry_step = name

        # Step 4: Summary
        avg_log_retries = round(total_log_retries / len(steps), 1) if steps else 0.0

        summary = {
            "total_log_retries": total_log_retries,
            "avg_log_retries_per_step": avg_log_retries,
            "max_log_retries_per_step": max_log_retries,
            "max_log_retry_step": max_log_retry_step,
            "total_db_retries": total_db_retries,
            "total_confirms": total_confirms,
            "total_rejects": total_rejects,
            "steps_with_retries": steps_with_retries,
            "total_steps": len(steps),
        }

        return {"steps": steps, "summary": summary}

    @staticmethod
    async def global_overview(db: AsyncSession) -> dict:
        """Global statistics overview with trend and failure breakdown."""
        total_projects = await db.scalar(select(func.count()).select_from(Project)) or 0
        completed = await db.scalar(
            select(func.count()).select_from(Project).where(Project.status == "completed")
        ) or 0
        failed = await db.scalar(
            select(func.count()).select_from(Project).where(Project.status == "failed")
        ) or 0
        running = await db.scalar(
            select(func.count()).select_from(Project).where(Project.status == "running")
        ) or 0

        total_gens = await db.scalar(select(func.count()).select_from(GenerationResult)) or 0
        avg_dur = await db.scalar(select(func.avg(GenerationResult.duration_seconds))) or 0

        # ---------- failure_reasons: aggregate from Step.error_message ----------
        fail_result = await db.execute(
            select(Step.error_message, func.count(Step.id))
            .where(and_(Step.status == "failed", Step.error_message.isnot(None)))
            .group_by(Step.error_message)
            .order_by(func.count(Step.id).desc())
            .limit(20)
        )
        failure_map: dict[str, int] = {}
        for error_msg, cnt in fail_result:
            category = _categorize_error(error_msg)
            failure_map[category] = failure_map.get(category, 0) + cnt

        # ---------- trend: daily & weekly project completion counts ----------
        # Daily trend — last 30 days
        thirty_days_ago = datetime.utcnow() - timedelta(days=30)
        daily_result = await db.execute(
            select(
                func.date(Project.created_at).label("day"),
                func.count(Project.id).label("total"),
                func.sum(case((Project.status == "completed", 1), else_=0)).label("success"),
                func.sum(case((Project.status == "failed", 1), else_=0)).label("failed"),
            )
            .where(Project.created_at >= thirty_days_ago)
            .group_by("day")
            .order_by("day")
        )
        daily = [
            {"date": r.day, "total": r.total, "success": r.success or 0, "failed": r.failed or 0}
            for r in daily_result
        ]

        # Weekly trend — last 12 weeks
        twelve_weeks_ago = datetime.utcnow() - timedelta(weeks=12)
        weekly_result = await db.execute(
            select(
                func.strftime("%Y-W%W", Project.created_at).label("week"),
                func.count(Project.id).label("total"),
                func.sum(case((Project.status == "completed", 1), else_=0)).label("success"),
                func.sum(case((Project.status == "failed", 1), else_=0)).label("failed"),
            )
            .where(Project.created_at >= twelve_weeks_ago)
            .group_by("week")
            .order_by("week")
        )
        weekly = [
            {"date": r.week, "total": r.total, "success": r.success or 0, "failed": r.failed or 0}
            for r in weekly_result
        ]

        return {
            "total_projects": total_projects,
            "completed_projects": completed,
            "failed_projects": failed,
            "running_projects": running,
            "success_rate": completed / total_projects if total_projects else 0,
            "total_generations": total_gens,
            "avg_generation_duration": round(float(avg_dur), 1),
            "failure_reasons": failure_map,
            "trend": {"daily": daily, "weekly": weekly},
        }

    @staticmethod
    async def edit_success_correlation(db: AsyncSession, project_id: int) -> dict:
        """FR-026: Correlate file edits with subsequent generation success rates.

        T093: Skip config file edits (.yaml/.yml/.py) — they dominate the log
        and skew correlation analysis since they're modified on every run.
        """
        # Query operation_logs of type edit_file for this project
        edit_logs = await db.execute(
            select(OperationLog)
            .where(
                and_(
                    OperationLog.project_id == project_id,
                    OperationLog.operation_type == "edit_file",
                )
            )
            .order_by(OperationLog.created_at)
        )
        all_edits = edit_logs.scalars().all()

        # T093: Filter out config file edits
        edits = [e for e in all_edits if not _is_config_edit(e.target_name)]

        if not edits:
            return {
                "project_id": project_id,
                "correlations": [],
                "summary": "暂无编辑操作记录，无法分析相关性",
            }

        correlations = []
        for edit in edits:
            # Find generation results created AFTER this edit within the same project
            gen_after = await db.execute(
                select(
                    func.count(GenerationResult.id).label("total"),
                    func.sum(case((GenerationResult.error_message.is_(None), 1), else_=0)).label("success"),
                )
                .where(
                    and_(
                        GenerationResult.project_id == project_id,
                        GenerationResult.created_at >= edit.created_at,
                    )
                )
            )
            row = gen_after.one_or_none()
            total = row.total if row else 0
            success = row.success or 0 if row else 0
            correlations.append({
                "edit_time": edit.created_at.isoformat() if edit.created_at else "",
                "target_name": edit.target_name,
                "summary": edit.summary,
                "generations_after": total,
                "success_after": success,
                "success_rate_after": success / total if total else 0,
            })

        # Overall: success rate before vs after edits
        all_gen = await db.execute(
            select(
                GenerationResult.created_at,
                GenerationResult.error_message,
            ).where(GenerationResult.project_id == project_id)
        )
        gen_rows = all_gen.all()
        if not edits or not gen_rows:
            return {"project_id": project_id, "correlations": correlations, "summary": "数据不足"}

        first_edit_time = edits[0].created_at
        before_success = sum(1 for g in gen_rows if g.created_at < first_edit_time and g.error_message is None)
        before_total = sum(1 for g in gen_rows if g.created_at < first_edit_time)
        after_success = sum(1 for g in gen_rows if g.created_at >= first_edit_time and g.error_message is None)
        after_total = sum(1 for g in gen_rows if g.created_at >= first_edit_time)

        before_rate = before_success / before_total if before_total else 0
        after_rate = after_success / after_total if after_total else 0
        delta = after_rate - before_rate

        return {
            "project_id": project_id,
            "correlations": correlations,
            "summary": (
                f"编辑前生成成功率: {before_rate:.1%} ({before_success}/{before_total}), "
                f"编辑后: {after_rate:.1%} ({after_success}/{after_total}), "
                f"变化: {delta:+.1%}"
            ),
        }
