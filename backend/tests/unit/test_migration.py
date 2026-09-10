"""Unit tests for idempotent column migrations (run_migrations)."""

import pytest
from sqlalchemy import text

from src.database import engine
from src.models.migration import _COLUMN_MIGRATIONS, run_migrations


@pytest.fixture(scope="module", autouse=True)
async def _ensure_tables():
    # projects 表由 create_all 创建（含新列）。迁移应跳过已存在列。
    from src.database import Base
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield


async def test_run_migrations_is_idempotent():
    async with engine.begin() as conn:
        # 第一次执行：不应报错
        await run_migrations(conn)
        # 第二次执行：依然幂等不报错
        await run_migrations(conn)

        result = await conn.execute(text("PRAGMA table_info(projects)"))
        cols = {row[1] for row in result.fetchall()}
        assert "schedule_mode" in cols
        assert "schedule_status" in cols
        assert "schedule_updated_at" in cols


def test_migration_manifest_matches_model():
    # projects 的迁移清单必须包含三个调度扩展列
    assert "schedule_mode" in " ".join(_COLUMN_MIGRATIONS["projects"])
    assert "schedule_status" in " ".join(_COLUMN_MIGRATIONS["projects"])
    assert "schedule_updated_at" in " ".join(_COLUMN_MIGRATIONS["projects"])
