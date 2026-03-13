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
from app.models.anpr_detection import ProcessingStatus
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
    camera_id: Optional[str] = Query(None, description="Filter by camera ID"),
    activity_type: Optional[str] = Query(None, description="Filter by activity type (in/out)"),
    status_filter: Optional[ProcessingStatus] = Query(None, description="Filter by processing status"),
    plate: Optional[str] = Query(None, description="Search by numberplate text (partial match)"),
    organization: Organization = Depends(verify_super_admin),
    db: Session = Depends(get_db)
):
    # Default to today if not specified
    if not start_date:
        start_date = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    if not end_date:
        end_date = datetime.utcnow()

    service = AnalyticsService(db)
    return service.get_hourly_stats(
        organization_id=organization_id,
        start_date=start_date,
        end_date=end_date,
        camera_id=camera_id,
        activity_type=activity_type,
        status=status_filter,
        plate=plate
    )


@router.get(
    "/daily",
    response_model=List[DailyStatsResponse],
    summary="Get daily detection statistics",
    description="Get daily detection trends for the last N days."
)
async def get_daily_stats(
    days: int = Query(30, ge=1, le=365, description="Number of days to retrieve (1-365)"),
    start_date: Optional[datetime] = Query(None, description="Start date for custom range"),
    end_date: Optional[datetime] = Query(None, description="End date for custom range"),
    organization_id: Optional[int] = Query(None, description="Filter by organization (super admin only)"),
    camera_id: Optional[str] = Query(None, description="Filter by camera ID"),
    activity_type: Optional[str] = Query(None, description="Filter by activity type (in/out)"),
    status_filter: Optional[ProcessingStatus] = Query(None, description="Filter by processing status"),
    plate: Optional[str] = Query(None, description="Search by numberplate text (partial match)"),
    organization: Organization = Depends(verify_super_admin),
    db: Session = Depends(get_db)
):
    service = AnalyticsService(db)
    return service.get_daily_stats(
        organization_id=organization_id,
        days=days,
        start_date=start_date,
        end_date=end_date,
        camera_id=camera_id,
        activity_type=activity_type,
        status=status_filter,
        plate=plate
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
    camera_id: Optional[str] = Query(None, description="Filter by camera ID"),
    activity_type: Optional[str] = Query(None, description="Filter by activity type (in/out)"),
    status_filter: Optional[ProcessingStatus] = Query(None, description="Filter by processing status"),
    plate: Optional[str] = Query(None, description="Search by numberplate text (partial match)"),
    organization: Organization = Depends(verify_super_admin),
    db: Session = Depends(get_db)
):
    service = AnalyticsService(db)
    return service.get_weekly_stats(
        organization_id=organization_id,
        weeks=weeks,
        camera_id=camera_id,
        activity_type=activity_type,
        status=status_filter,
        plate=plate
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
    camera_id: Optional[str] = Query(None, description="Filter by camera ID"),
    activity_type: Optional[str] = Query(None, description="Filter by activity type (in/out)"),
    status_filter: Optional[ProcessingStatus] = Query(None, description="Filter by processing status"),
    plate: Optional[str] = Query(None, description="Search by numberplate text (partial match)"),
    organization: Organization = Depends(verify_super_admin),
    db: Session = Depends(get_db)
):
    service = AnalyticsService(db)
    return service.get_monthly_stats(
        organization_id=organization_id,
        months=months,
        camera_id=camera_id,
        activity_type=activity_type,
        status=status_filter,
        plate=plate
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
    camera_id: Optional[str] = Query(None, description="Filter by camera ID"),
    activity_type: Optional[str] = Query(None, description="Filter by activity type (in/out)"),
    status_filter: Optional[ProcessingStatus] = Query(None, description="Filter by processing status"),
    plate: Optional[str] = Query(None, description="Search by numberplate text (partial match)"),
    organization: Organization = Depends(verify_super_admin),
    db: Session = Depends(get_db)
):
    # Default to last 30 days if not specified
    if not start_date:
        start_date = datetime.utcnow() - timedelta(days=30)
    if not end_date:
        end_date = datetime.utcnow()

    service = AnalyticsService(db)
    return service.get_vehicle_type_stats(
        organization_id=organization_id,
        start_date=start_date,
        end_date=end_date,
        camera_id=camera_id,
        activity_type=activity_type,
        status=status_filter,
        plate=plate
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
    camera_id: Optional[str] = Query(None, description="Filter by camera ID"),
    activity_type: Optional[str] = Query(None, description="Filter by activity type (in/out)"),
    status_filter: Optional[ProcessingStatus] = Query(None, description="Filter by processing status"),
    plate: Optional[str] = Query(None, description="Search by numberplate text (partial match)"),
    organization: Organization = Depends(verify_super_admin),
    db: Session = Depends(get_db)
):
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
        limit=limit,
        camera_id=camera_id,
        activity_type=activity_type,
        status=status_filter,
        plate=plate
    )
