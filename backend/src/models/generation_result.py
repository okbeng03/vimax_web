"""GenerationResult model — ComfyUI generation outputs."""

from datetime import datetime
from sqlalchemy import String, Integer, Float, Boolean, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from src.database import Base


class GenerationResult(Base):
    __tablename__ = "generation_results"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    step_id: Mapped[int] = mapped_column(Integer, ForeignKey("steps.id"), nullable=False, index=True)
    project_id: Mapped[int] = mapped_column(Integer, ForeignKey("projects.id"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    storage_path: Mapped[str] = mapped_column(String(500), nullable=False)  # actual file location (may differ after cancel)
    thumbnail_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    prompt_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    workflow_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    generation_type: Mapped[str] = mapped_column(String(20), nullable=False)  # first_frame / last_frame / video
    duration_seconds: Mapped[float] = mapped_column(Float, nullable=False)
    error_message: Mapped[str | None] = mapped_column(String(500), nullable=True)
    confirmed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())

    step = relationship("Step", back_populates="generation_results")
    project = relationship("Project", back_populates="generation_results")
    user = relationship("User")
