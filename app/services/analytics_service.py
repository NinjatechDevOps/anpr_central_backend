"""
Analytics Service - Business logic for analytics operations.
"""
from typing import List, Optional
from datetime import datetime
from sqlalchemy.orm import Session

from app.repositories.anpr_repository import AnprDetectionRepository
from app.models.anpr_detection import ProcessingStatus
from app.schemas.analytics_schemas import (
    HourlyStatsResponse,
    DailyStatsResponse,
    WeeklyStatsResponse,
    MonthlyStatsResponse,
    VehicleTypeStatsResponse,
    CameraPerformanceResponse
)


class AnalyticsService:
    """Service for analytics operations."""

    def __init__(self, db: Session):
        self.db = db
        self.repo = AnprDetectionRepository(db)

    def get_hourly_stats(
        self,
        organization_id: Optional[int] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        camera_id: Optional[str] = None,
        activity_type: Optional[str] = None,
        status: Optional[ProcessingStatus] = None,
        plate: Optional[str] = None
    ) -> List[HourlyStatsResponse]:
        """Get hourly detection statistics."""
        stats = self.repo.get_hourly_stats(
            organization_id=organization_id,
            start_date=start_date,
            end_date=end_date,
            camera_id=camera_id,
            activity_type=activity_type,
            status=status,
            plate=plate
        )
        return [HourlyStatsResponse(**stat) for stat in stats]

    def get_daily_stats(
        self,
        organization_id: Optional[int] = None,
        days: int = 30,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        camera_id: Optional[str] = None,
        activity_type: Optional[str] = None,
        status: Optional[ProcessingStatus] = None,
        plate: Optional[str] = None
    ) -> List[DailyStatsResponse]:
        """Get daily detection statistics."""
        stats = self.repo.get_daily_stats(
            organization_id=organization_id,
            days=days,
            start_date=start_date,
            end_date=end_date,
            camera_id=camera_id,
            activity_type=activity_type,
            status=status,
            plate=plate
        )
        return [DailyStatsResponse(**stat) for stat in stats]

    def get_weekly_stats(
        self,
        organization_id: Optional[int] = None,
        weeks: int = 12,
        camera_id: Optional[str] = None,
        activity_type: Optional[str] = None,
        status: Optional[ProcessingStatus] = None,
        plate: Optional[str] = None
    ) -> List[WeeklyStatsResponse]:
        """Get weekly detection statistics."""
        stats = self.repo.get_weekly_stats(
            organization_id=organization_id,
            weeks=weeks,
            camera_id=camera_id,
            activity_type=activity_type,
            status=status,
            plate=plate
        )
        return [WeeklyStatsResponse(**stat) for stat in stats]

    def get_monthly_stats(
        self,
        organization_id: Optional[int] = None,
        months: int = 12,
        camera_id: Optional[str] = None,
        activity_type: Optional[str] = None,
        status: Optional[ProcessingStatus] = None,
        plate: Optional[str] = None
    ) -> List[MonthlyStatsResponse]:
        """Get monthly detection statistics."""
        stats = self.repo.get_monthly_stats(
            organization_id=organization_id,
            months=months,
            camera_id=camera_id,
            activity_type=activity_type,
            status=status,
            plate=plate
        )
        return [MonthlyStatsResponse(**stat) for stat in stats]

    def get_vehicle_type_stats(
        self,
        organization_id: Optional[int] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        camera_id: Optional[str] = None,
        activity_type: Optional[str] = None,
        status: Optional[ProcessingStatus] = None,
        plate: Optional[str] = None
    ) -> List[VehicleTypeStatsResponse]:
        """Get vehicle type distribution statistics."""
        stats = self.repo.get_vehicle_type_stats(
            organization_id=organization_id,
            start_date=start_date,
            end_date=end_date,
            camera_id=camera_id,
            activity_type=activity_type,
            status=status,
            plate=plate
        )
        return [VehicleTypeStatsResponse(**stat) for stat in stats]

    def get_camera_performance_stats(
        self,
        organization_id: Optional[int] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 10,
        camera_id: Optional[str] = None,
        activity_type: Optional[str] = None,
        status: Optional[ProcessingStatus] = None,
        plate: Optional[str] = None
    ) -> List[CameraPerformanceResponse]:
        """Get camera performance statistics."""
        stats = self.repo.get_camera_performance_stats(
            organization_id=organization_id,
            start_date=start_date,
            end_date=end_date,
            limit=limit,
            camera_id=camera_id,
            activity_type=activity_type,
            status=status,
            plate=plate
        )
        return [CameraPerformanceResponse(**stat) for stat in stats]
