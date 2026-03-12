"""
API routes for dashboard statistics in the sign glove system.
Refactored to use DashboardService.
"""
from fastapi import APIRouter, Query, HTTPException
from services.dashboard.dashboard_service import dashboard_service

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])

@router.get("/")
async def get_dashboard_stats():
    try:
        return await dashboard_service.get_basic_stats()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

@router.get("/monitoring")
async def get_monitoring_dashboard_stats(
    window: str = Query("24h", pattern="^(1h|6h|24h|7d)$"),
):
    try:
        return await dashboard_service.get_monitoring_stats(window)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

@router.get("")
async def get_dashboard_stats_alias():
    return await get_dashboard_stats()
