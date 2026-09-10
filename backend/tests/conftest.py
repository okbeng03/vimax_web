"""Pytest 全局配置：测试数据库与生产数据库隔离。

重要：本文件必须在任何 `src.database` / `src.config` 被 import 之前执行，
通过设置 VIMAX_DATABASE_URL 环境变量，让全局 engine 指向独立的测试库，
避免测试中的 create_all / drop_all 影响生产库（backend/data/vimax_web.db）。
"""

import os
from pathlib import Path

import pytest

_TEST_DB_DIR = Path(__file__).parent / "data"
_TEST_DB_DIR.mkdir(parents=True, exist_ok=True)
_TEST_DB_PATH = _TEST_DB_DIR / "test_vimax_web.db"

# 必须在 import src.database 之前设置（config.py 使用 env_prefix="VIMAX_"）
os.environ["VIMAX_DATABASE_URL"] = f"sqlite+aiosqlite:///{_TEST_DB_PATH}"


@pytest.fixture(scope="session", autouse=True)
def _ensure_test_db_clean():
    """每个测试会话开始前清空测试库，保证用例互相独立。

    仅影响 backend/tests/data/test_vimax_web.db，绝不触碰生产库。
    """
    if _TEST_DB_PATH.exists():
        _TEST_DB_PATH.unlink()
    yield
