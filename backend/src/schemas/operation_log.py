"""OperationLog Pydantic schemas."""

from datetime import datetime
from src.schemas import AppBaseSchema


class OperationLogResponse(AppBaseSchema):
    id: int
    operation_type: str
    target_type: str
    target_id: int | None = None
    target_name: str
    summary: str
    details: str | None = None
    error_message: str | None = None
    user_name: str | None = None
    created_at: datetime


class OperationLogListResponse(AppBaseSchema):
    operations: list[OperationLogResponse]
    total: int
