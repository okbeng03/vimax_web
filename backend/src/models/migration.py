"""启动时幂等迁移 — 为既有表补齐新增列，不重建表、不触碰既有数据。

策略：PRAGMA table_info 检查缺失列 → ALTER TABLE ADD COLUMN（均带默认值）。
重复启动幂等不报错。
"""

import logging
from sqlalchemy import text

logger = logging.getLogger(__name__)

# (表名, [(列名, DDL 片段), ...])
_COLUMN_MIGRATIONS: dict[str, list[str]] = {
    "projects": [
        "ALTER TABLE projects ADD COLUMN schedule_mode BOOLEAN NOT NULL DEFAULT 0",
        "ALTER TABLE projects ADD COLUMN schedule_status VARCHAR(20) NOT NULL DEFAULT 'idle'",
        "ALTER TABLE projects ADD COLUMN schedule_updated_at DATETIME",
    ],
}


async def run_migrations(conn) -> None:
    """Execute idempotent column migrations on an async connection.

    ``conn`` is an ``AsyncConnection`` obtained from ``engine.begin()``.
    """
    for table, ddl_statements in _COLUMN_MIGRATIONS.items():
        try:
            result = await conn.execute(text(f"PRAGMA table_info({table})"))
            rows = result.fetchall()
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("Migration: table '%s' not readable, skip: %s", table, exc)
            continue

        existing = {row[1] for row in rows}
        for ddl in ddl_statements:
            col = ddl.split("ADD COLUMN ", 1)[1].split(" ", 1)[0]
            if col in existing:
                continue
            await conn.execute(text(ddl))
            logger.info("Migration: added column '%s' to table '%s'", col, table)
