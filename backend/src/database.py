"""Database engine, session factory, and initialization."""

from pathlib import Path
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from src.config import settings


class Base(DeclarativeBase):
    pass


engine = create_async_engine(
    f"sqlite+aiosqlite:///{Path(settings.DATABASE_URL.replace('sqlite+aiosqlite:///', ''))}",
    echo=False,
)

async_session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_db() -> AsyncSession:
    """FastAPI dependency: yield an async DB session."""
    async with async_session_factory() as session:
        try:
            yield session
        finally:
            await session.close()


async def init_db() -> None:
    """Create all tables and seed default data."""
    from src.models import User, Template, Project, Step, GenerationResult, OperationLog  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with async_session_factory() as session:
        from sqlalchemy import select

        # Seed default user "muze"
        result = await session.execute(select(User).where(User.username == "muze"))
        if not result.scalar_one_or_none():
            session.add(User(id=1, username="muze", display_name="Muze"))

        # Seed 3 built-in templates
        templates_data = [
            {"id": 1, "name": "standard", "display_name": "标准视频", "description": "标准视频", "directory_name": "standard"},
            {"id": 2, "name": "hanzi", "display_name": "汉字视频", "description": "汉字视频", "directory_name": "hanzi"},
            # {"id": 2, "name": "fast_preview", "display_name": "快速预览", "description": "低分辨率、少步骤，适合快速验证创意", "directory_name": "fast_preview"},
            # {"id": 3, "name": "high_quality", "display_name": "高质量", "description": "最高分辨率、完整流水线，适合最终输出", "directory_name": "high_quality"},
        ]
        for td in templates_data:
            result = await session.execute(select(Template).where(Template.name == td["name"]))
            if not result.scalar_one_or_none():
                session.add(Template(**td))

        await session.commit()
