"""Statistics Pydantic schemas."""

from src.schemas import AppBaseSchema


class StepStat(AppBaseSchema):
    name: str
    duration: float
    status: str
    error_message: str | None = None
    retry_count: int = 0


class StepOverview(AppBaseSchema):
    total: int
    completed: int
    failed: int
    running: int
    pending: int
    success_rate: float


class GenerationStat(AppBaseSchema):
    total: int
    success: int
    failed: int
    success_rate: float


class TrendPoint(AppBaseSchema):
    date: str
    total: int
    success: int
    failed: int


class GenerationTypeStat(AppBaseSchema):
    type: str
    count: int


class GenerationStepStat(AppBaseSchema):
    step_name: str
    total: int
    success: int
    failed: int


class DurationBucket(AppBaseSchema):
    range: str
    count: int


class AvgDurationByType(AppBaseSchema):
    type: str
    avg_duration: float


class StepLogRetryStat(AppBaseSchema):
    """Log-derived per-step retry & confirm/reject counts.

    Only includes actual Step records (standalone ops like generation
    confirmations are excluded). db_retry_count comes from Step.retry_count
    (cumulative across all runs).
    """
    step_name: str
    db_retry_count: int = 0
    log_retry_count: int = 0
    confirm_count: int = 0
    reject_count: int = 0


class StepLogRetrySummary(AppBaseSchema):
    """Aggregated retry overview (avg / max / totals)."""
    total_log_retries: int = 0
    avg_log_retries_per_step: float = 0.0
    max_log_retries_per_step: int = 0
    max_log_retry_step: str = ""
    total_db_retries: int = 0
    total_confirms: int = 0
    total_rejects: int = 0
    steps_with_retries: int = 0
    total_steps: int = 0


class ProjectStatsResponse(AppBaseSchema):
    scene_count: int
    file_counts: dict[str, int]
    total_file_size_mb: float
    total_duration_seconds: float
    step_overview: StepOverview
    steps: list[StepStat]
    operation_summary: dict[str, int]
    generation_stats: GenerationStat
    generations_by_type: list[GenerationTypeStat] = []
    generations_by_step: list[GenerationStepStat] = []
    duration_buckets: list[DurationBucket] = []
    avg_duration_by_type: list[AvgDurationByType] = []
    step_log_retries: list[StepLogRetryStat] = []
    step_log_retry_summary: StepLogRetrySummary | None = None


class GlobalStatsResponse(AppBaseSchema):
    total_projects: int
    completed_projects: int
    failed_projects: int
    running_projects: int
    success_rate: float
    total_generations: int
    avg_generation_duration: float
    failure_reasons: dict[str, int]
    trend: dict[str, list[TrendPoint]]


class CorrelationResponse(AppBaseSchema):
    project_id: int
    correlations: list
    summary: str
