"""User Pydantic schemas."""

from src.schemas import AppBaseSchema


class UserResponse(AppBaseSchema):
    id: int
    username: str
    display_name: str
