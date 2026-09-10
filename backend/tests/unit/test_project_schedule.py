"""Unit tests for project schedule-mode schema and model defaults."""

import pytest
from sqlalchemy import select

from src.database import Base, engine, async_session_factory
from src.models.project import Project
from src.schemas.project import ProjectListItem, ProjectResponse


@pytest.fixture(scope="module", autouse=True)
async def _setup_db():
    # 使用 conftest.py 隔离的测试库（VIMAX_DATABASE_URL 指向 backend/tests/data/）
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def test_project_model_schedule_defaults():
    async with async_session_factory() as session:
        proj = Project(user_id=1, name="schedule-proj", creative_description="desc", working_dir="/tmp/p")
        session.add(proj)
        await session.commit()
        await session.refresh(proj)

        assert proj.schedule_mode is False
        assert proj.schedule_status == "idle"
        assert proj.schedule_updated_at is None


def test_schemas_expose_schedule_fields():
    item = ProjectListItem(
        id=1, name="n", creative_description="d", working_dir="/w",
        status="idle", schedule_mode=True, schedule_status="syncing",
        created_at=__import__("datetime").datetime.utcnow(),
        updated_at=__import__("datetime").datetime.utcnow(),
    )
    assert item.schedule_mode is True
    assert item.schedule_status == "syncing"

    resp = ProjectResponse(
        id=1, name="n", creative_description="d", working_dir="/w",
        status="idle", schedule_mode=False, schedule_status="failed",
        created_at=__import__("datetime").datetime.utcnow(),
        updated_at=__import__("datetime").datetime.utcnow(),
    )
    assert resp.schedule_status == "failed"
