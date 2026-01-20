"""
Analytics Service - Business logic for analytics operations.
"""
from typing import List, Optional
from datetime import datetime
from sqlalchemy.orm import Session

from app.repositories.anpr_repository import AnprDetectionRepository
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
        end_date: Optional[datetime] = None
    ) -> List[HourlyStatsResponse]:
        """Get hourly detection statistics."""
        stats = self.repo.get_hourly_stats(
            organization_id=organization_id,
            start_date=start_date,
            end_date=end_date
        )
        return [HourlyStatsResponse(**stat) for stat in stats]

    def get_daily_stats(
        self,
        organization_id: Optional[int] = None,
        days: int = 30
    ) -> List[DailyStatsResponse]:
        """Get daily detection statistics."""
        stats = self.repo.get_daily_stats(
            organization_id=organization_id,
            days=days
        )
        return [DailyStatsResponse(**stat) for stat in stats]

    def get_weekly_stats(
        self,
        organization_id: Optional[int] = None,
        weeks: int = 12
    ) -> List[WeeklyStatsResponse]:
        """Get weekly detection statistics."""
        stats = self.repo.get_weekly_stats(
            organization_id=organization_id,
            weeks=weeks
        )
        return [WeeklyStatsResponse(**stat) for stat in stats]

    def get_monthly_stats(
        self,
        organization_id: Optional[int] = None,
        months: int = 12
    ) -> List[MonthlyStatsResponse]:
        """Get monthly detection statistics."""
        stats = self.repo.get_monthly_stats(
            organization_id=organization_id,
            months=months
        )
        return [MonthlyStatsResponse(**stat) for stat in stats]

    def get_vehicle_type_stats(
        self,
        organization_id: Optional[int] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> List[VehicleTypeStatsResponse]:
        """Get vehicle type distribution statistics."""
        stats = self.repo.get_vehicle_type_stats(
            organization_id=organization_id,
            start_date=start_date,
            end_date=end_date
        )
        return [VehicleTypeStatsResponse(**stat) for stat in stats]

    def get_camera_performance_stats(
        self,
        organization_id: Optional[int] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 10
    ) -> List[CameraPerformanceResponse]:
        """Get camera performance statistics."""
        stats = self.repo.get_camera_performance_stats(
            organization_id=organization_id,
            start_date=start_date,
            end_date=end_date,
            limit=limit
        )
        return [CameraPerformanceResponse(**stat) for stat in stats]
