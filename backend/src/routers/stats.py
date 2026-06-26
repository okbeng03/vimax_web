"""Statistics API router."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from src.database import get_db
from src.services.statistics import StatisticsService
from src.schemas.statistics import ProjectStatsResponse, GlobalStatsResponse, CorrelationResponse

router = APIRouter(prefix="/api", tags=["statistics"])


@router.get("/statistics/overview", response_model=GlobalStatsResponse)
async def global_overview(db: AsyncSession = Depends(get_db)):
    """Global statistics overview with trend data."""
    return await StatisticsService.global_overview(db)


@router.get("/projects/{project_id}/statistics", response_model=ProjectStatsResponse)
async def project_statistics(project_id: int, db: AsyncSession = Depends(get_db)):
    """Project-level statistics."""
    return await StatisticsService.project_stats(db, project_id)


@router.get("/projects/{project_id}/statistics/correlation", response_model=CorrelationResponse)
async def edit_correlation(project_id: int, db: AsyncSession = Depends(get_db)):
    """FR-026: Edit-success correlation analysis."""
    return await StatisticsService.edit_success_correlation(db, project_id)
