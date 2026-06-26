"""Users API router."""

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.database import get_db
from src.models.user import User
from src.schemas.user import UserResponse

router = APIRouter(prefix="/api/users", tags=["users"])


@router.get("/me", response_model=UserResponse)
async def get_current_user(db: AsyncSession = Depends(get_db)):
    """Return the default user (no auth — single-user mode)."""
    result = await db.execute(
        select(User).where(User.username == settings.DEFAULT_USERNAME)
    )
    user = result.scalar_one_or_none()
    if not user:
        # Fallback: create default user on the fly if missing
        user = User(username=settings.DEFAULT_USERNAME, display_name=settings.DEFAULT_USERNAME.capitalize())
        db.add(user)
        await db.commit()
        await db.refresh(user)
    return UserResponse(
        id=user.id,
        username=user.username,
        display_name=user.display_name,
    )
