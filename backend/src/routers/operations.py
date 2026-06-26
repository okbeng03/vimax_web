"""Operations API router — view operation logs."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.database import get_db
from src.models.project import Project
from src.models.operation_log import OperationLog
from src.schemas.operation_log import OperationLogResponse, OperationLogListResponse

router = APIRouter(prefix="/api/projects", tags=["operations"])


@router.get("/{project_id}/operations", response_model=OperationLogListResponse)
async def list_operations(
    project_id: int,
    type: str | None = None,
    page: int = 1,
    page_size: int = 50,
    db: AsyncSession = Depends(get_db),
):
    """List operation logs for a project."""
    proj_result = await db.execute(select(Project).where(Project.id == project_id))
    if not proj_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Project not found")

    query = select(OperationLog).options(selectinload(OperationLog.user)).where(OperationLog.project_id == project_id)
    if type:
        query = query.where(OperationLog.operation_type == type)

    count_query = select(func.count()).select_from(OperationLog).where(OperationLog.project_id == project_id)
    if type:
        count_query = count_query.where(OperationLog.operation_type == type)
    total = (await db.execute(count_query)).scalar() or 0

    query = query.order_by(OperationLog.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    logs = result.unique().scalars().all()

    return OperationLogListResponse(
        operations=[
            OperationLogResponse(
                id=log.id,
                operation_type=log.operation_type,
                target_type=log.target_type,
                target_id=log.target_id,
                target_name=log.target_name,
                summary=log.summary,
                details=log.details,
                error_message=log.error_message,
                user_name=log.user.display_name if log.user else None,
                created_at=log.created_at,
            )
            for log in logs
        ],
        total=total,
    )
