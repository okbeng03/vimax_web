"""Project Pydantic schemas."""

from datetime import datetime
from src.schemas import AppBaseSchema


class ProjectCreate(AppBaseSchema):
    name: str
    creative_description: str
    template_id: int
    working_dir_root: str = "/Users/wangchangbin/ai/vimax_ru"


class ProjectConfigUpdate(AppBaseSchema):
    yaml_content: str
    config_py_content: str


class StepSummary(AppBaseSchema):
    total: int
    completed: int
    failed: int


class ProjectListItem(AppBaseSchema):
    id: int
    name: str
    creative_description: str
    working_dir: str
    status: str
    template_name: str | None = None
    current_step_name: str | None = None
    step_summary: StepSummary | None = None
    created_at: datetime
    updated_at: datetime


class ProjectConfig(AppBaseSchema):
    yaml_content: str
    config_py_content: str


class ProjectResponse(AppBaseSchema):
    id: int
    name: str
    creative_description: str
    working_dir: str
    status: str
    template_id: int | None = None
    current_step_name: str | None = None
    config: ProjectConfig | None = None
    unconfirmed_count: int = 0
    created_at: datetime
    updated_at: datetime


class ProjectListResponse(AppBaseSchema):
    projects: list[ProjectListItem]
    total: int
    page: int
    page_size: int


class ProjectCreateResponse(AppBaseSchema):
    id: int
    name: str
    working_dir: str
    status: str
    created_at: datetime


class ProgressStepSchema(AppBaseSchema):
    """A single progress step (from template's progress.py)."""
    name: str          # internal key, e.g. "story"
    label: str         # human-readable, e.g. "生成故事"
    order: int         # zero-based index
    status: str        # "new" | "running" | "success" | "failed" | "pending"


class ProjectProgressResponse(AppBaseSchema):
    """Full progress enum for a project."""
    steps: list[ProgressStepSchema]
    current_step_order: int | None = None  # currently executing step index
