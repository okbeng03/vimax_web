"""Project model."""

from datetime import datetime
from sqlalchemy import String, Integer, DateTime, Text, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from src.database import Base


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    creative_description: Mapped[str] = mapped_column(Text, nullable=False)
    working_dir: Mapped[str] = mapped_column(String(500), unique=True, nullable=False)
    template_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("templates.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="idle")
    current_step_name: Mapped[str | None] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    user = relationship("User")
    template = relationship("Template")
    steps = relationship("Step", back_populates="project", order_by="Step.step_order", cascade="all, delete-orphan")
    generation_results = relationship("GenerationResult", back_populates="project", cascade="all, delete-orphan")
    operation_logs = relationship("OperationLog", back_populates="project", cascade="all, delete-orphan")
