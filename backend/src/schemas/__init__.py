"""Shared base Pydantic schema."""

from pydantic import BaseModel, ConfigDict


class AppBaseSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)
