"""GenerationResult Pydantic schemas."""

from datetime import datetime
from pydantic import Field
from src.schemas import AppBaseSchema


class GenerationResultResponse(AppBaseSchema):
    id: int
    step_name: str | None = None
    workflow_name: str | None = None
    file_path: str
    relative_path: str = ""  # file_path relative to working_dir
    storage_path: str = ""   # actual file location (may differ after cancel)
    thumbnail_path: str | None = None
    prompt_id: str
    generation_type: str
    duration_seconds: float
    confirmed: bool
    cancelled: bool = False  # True when file moved to caches
    error_message: str | None = None
    created_at: datetime
    scene: int | None = None   # extracted from file_path
    shot: int | None = None    # extracted from file_path


class GenerationListResponse(AppBaseSchema):
    generations: list[GenerationResultResponse]
    total: int
    total_pages: int = 1
    unconfirmed_count: int


class GenerationsRetryRequest(AppBaseSchema):
    modified_params: dict = {}


class GenerationsGachaRequest(AppBaseSchema):
    """Gacha retry — scene/shot re-roll."""
    gacha_type: str = Field(default="last_frame", description="last_frame | first_frame | video")
    scene: int = 1
    shot: int = 2
