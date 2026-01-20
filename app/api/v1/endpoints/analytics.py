"""
Analytics API Endpoints - Time-based analytics and statistics.
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from datetime import datetime, timedelta

from app.db.session import get_db
from app.api.dependencies import verify_super_admin
from app.models.organization import Organization
from app.schemas.analytics_schemas import (
    HourlyStatsResponse,
    DailyStatsResponse,
    WeeklyStatsResponse,
    MonthlyStatsResponse,
    VehicleTypeStatsResponse,
    CameraPerformanceResponse
)
from app.services.analytics_service import AnalyticsService


router = APIRouter()


@router.get(
    "/hourly",
    response_model=List[HourlyStatsResponse],
    summary="Get hourly detection statistics",
    description="Get hourly breakdown of detections. Optionally filter by date range and organization."
)
async def get_hourly_stats(
    start_date: Optional[datetime] = Query(None, description="Start date filter (defaults to today)"),
    end_date: Optional[datetime] = Query(None, description="End date filter"),
    organization_id: Optional[int] = Query(None, description="Filter by organization (super admin only)"),
    organization: Organization = Depends(verify_super_admin),
    db: Session = Depends(get_db)
):
    """
    Get hourly detection statistics.

    Requires:
    - X-API-Token header with super admin token

    Query parameters:
    - start_date: Start date for filtering (defaults to today 00:00)
    - end_date: End date for filtering (defaults to now)
    - organization_id: Filter by specific organization

    Returns hourly breakdown with detection counts, success/failure, and in/out activity.
    """
    # Default to today if not specified
    if not start_date:
        start_date = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    if not end_date:
        end_date = datetime.utcnow()

    service = AnalyticsService(db)
    return service.get_hourly_stats(
        organization_id=organization_id,
        start_date=start_date,
        end_date=end_date
    )


@router.get(
    "/daily",
    response_model=List[DailyStatsResponse],
    summary="Get daily detection statistics",
    description="Get daily detection trends for the last N days."
)
async def get_daily_stats(
    days: int = Query(30, ge=1, le=365, description="Number of days to retrieve (1-365)"),
    organization_id: Optional[int] = Query(None, description="Filter by organization (super admin only)"),
    organization: Organization = Depends(verify_super_admin),
    db: Session = Depends(get_db)
):
    """
    Get daily detection statistics.

    Requires:
    - X-API-Token header with super admin token

    Query parameters:
    - days: Number of days to retrieve (default: 30, max: 365)
    - organization_id: Filter by specific organization

    Returns daily breakdown with detection counts, success rates, and in/out activity.
    """
    service = AnalyticsService(db)
    return service.get_daily_stats(
        organization_id=organization_id,
        days=days
    )


@router.get(
    "/weekly",
    response_model=List[WeeklyStatsResponse],
    summary="Get weekly detection statistics",
    description="Get weekly detection trends for the last N weeks."
)
async def get_weekly_stats(
    weeks: int = Query(12, ge=1, le=52, description="Number of weeks to retrieve (1-52)"),
    organization_id: Optional[int] = Query(None, description="Filter by organization (super admin only)"),
    organization: Organization = Depends(verify_super_admin),
    db: Session = Depends(get_db)
):
    """
    Get weekly detection statistics.

    Requires:
    - X-API-Token header with super admin token

    Query parameters:
    - weeks: Number of weeks to retrieve (default: 12, max: 52)
    - organization_id: Filter by specific organization

    Returns weekly breakdown with detection counts, success rates, and in/out activity.
    """
    service = AnalyticsService(db)
    return service.get_weekly_stats(
        organization_id=organization_id,
        weeks=weeks
    )


@router.get(
    "/monthly",
    response_model=List[MonthlyStatsResponse],
    summary="Get monthly detection statistics",
    description="Get monthly detection trends for the last N months."
)
async def get_monthly_stats(
    months: int = Query(12, ge=1, le=24, description="Number of months to retrieve (1-24)"),
    organization_id: Optional[int] = Query(None, description="Filter by organization (super admin only)"),
    organization: Organization = Depends(verify_super_admin),
    db: Session = Depends(get_db)
):
    """
    Get monthly detection statistics.

    Requires:
    - X-API-Token header with super admin token

    Query parameters:
    - months: Number of months to retrieve (default: 12, max: 24)
    - organization_id: Filter by specific organization

    Returns monthly breakdown with detection counts, success rates, and in/out activity.
    """
    service = AnalyticsService(db)
    return service.get_monthly_stats(
        organization_id=organization_id,
        months=months
    )


@router.get(
    "/vehicle-types",
    response_model=List[VehicleTypeStatsResponse],
    summary="Get vehicle type distribution",
    description="Get distribution of detections by vehicle type."
)
async def get_vehicle_type_stats(
    start_date: Optional[datetime] = Query(None, description="Start date filter"),
    end_date: Optional[datetime] = Query(None, description="End date filter"),
    organization_id: Optional[int] = Query(None, description="Filter by organization (super admin only)"),
    organization: Organization = Depends(verify_super_admin),
    db: Session = Depends(get_db)
):
    """
    Get vehicle type distribution statistics.

    Requires:
    - X-API-Token header with super admin token

    Query parameters:
    - start_date: Start date for filtering (optional)
    - end_date: End date for filtering (optional)
    - organization_id: Filter by specific organization

    Returns distribution of detections by vehicle type (car, truck, bus, motorcycle, etc.).
    """
    # Default to last 30 days if not specified
    if not start_date:
        start_date = datetime.utcnow() - timedelta(days=30)
    if not end_date:
        end_date = datetime.utcnow()

    service = AnalyticsService(db)
    return service.get_vehicle_type_stats(
        organization_id=organization_id,
        start_date=start_date,
        end_date=end_date
    )


@router.get(
    "/camera-performance",
    response_model=List[CameraPerformanceResponse],
    summary="Get camera performance statistics",
    description="Get top performing cameras by detection count."
)
async def get_camera_performance_stats(
    start_date: Optional[datetime] = Query(None, description="Start date filter"),
    end_date: Optional[datetime] = Query(None, description="End date filter"),
    organization_id: Optional[int] = Query(None, description="Filter by organization (super admin only)"),
    limit: int = Query(10, ge=1, le=50, description="Number of cameras to return (1-50)"),
    organization: Organization = Depends(verify_super_admin),
    db: Session = Depends(get_db)
):
    """
    Get camera performance statistics.

    Requires:
    - X-API-Token header with super admin token

    Query parameters:
    - start_date: Start date for filtering (optional)
    - end_date: End date for filtering (optional)
    - organization_id: Filter by specific organization
    - limit: Number of top cameras to return (default: 10, max: 50)

    Returns top performing cameras with detection counts and success rates.
    """
    # Default to last 30 days if not specified
    if not start_date:
        start_date = datetime.utcnow() - timedelta(days=30)
    if not end_date:
        end_date = datetime.utcnow()

    service = AnalyticsService(db)
    return service.get_camera_performance_stats(
        organization_id=organization_id,
        start_date=start_date,
        end_date=end_date,
        limit=limit
    )
