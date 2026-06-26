"""Template Pydantic schemas."""

from datetime import datetime
from src.schemas import AppBaseSchema


class TemplateResponse(AppBaseSchema):
    id: int
    name: str
    display_name: str
    description: str
    directory_name: str
    is_builtin: bool
    created_at: datetime


class TemplateListResponse(AppBaseSchema):
    templates: list[TemplateResponse]


class TemplateCreate(AppBaseSchema):
    name: str
    display_name: str
    description: str
    directory_name: str


class TemplateUpdate(AppBaseSchema):
    display_name: str | None = None
    description: str | None = None
    directory_name: str | None = None
