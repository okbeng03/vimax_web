"""Step Pydantic schemas."""

from datetime import datetime
from src.schemas import AppBaseSchema


class ComfyuiResultInStep(AppBaseSchema):
    id: int
    file_path: str
    thumbnail_path: str | None = None
    prompt_id: str
    generation_type: str
    duration_seconds: float
    confirmed: bool


class StepResponse(AppBaseSchema):
    id: int
    name: str
    step_order: int
    status: str
    started_at: datetime | None = None
    completed_at: datetime | None = None
    duration_seconds: float | None = None
    output_files: list[str] = []
    retry_count: int = 0
    error_message: str | None = None
    comfyui_results: list[ComfyuiResultInStep] = []


class StepListResponse(AppBaseSchema):
    steps: list[StepResponse]


class StepExecuteRequest(AppBaseSchema):
    action: str  # "start" | "continue" | "retry_step"
    step_name: str | None = None  # required for retry_step


class StepExecuteResponse(AppBaseSchema):
    project_id: int
    status: str
    current_step_name: str
    message: str


class StepKillResponse(AppBaseSchema):
    status: str
    message: str
