"""
Repository for ANPR Detection data access.
"""
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import desc, func, and_

from app.models.anpr_detection import AnprDetection, ProcessingStatus
from app.repositories.base_repository import BaseRepository


class AnprDetectionRepository(BaseRepository[AnprDetection]):
    """Repository for ANPR Detection database operations."""

    def __init__(self, db: Session):
        super().__init__(AnprDetection, db)

    def get_by_organization(
        self,
        organization_id: int,
        skip: int = 0,
        limit: int = 100,
        status: Optional[ProcessingStatus] = None
    ) -> List[AnprDetection]:
        """Get detections for a specific organization."""
        query = self.db.query(self.model).filter(
            self.model.organization_id == organization_id
        )

        if status:
            query = query.filter(self.model.status == status)

        return query.order_by(desc(self.model.created_at)).offset(skip).limit(limit).all()

    def get_external_device_id(
        self,
        organization_id: int,
        camera_id: str
    ) -> Optional[str]:
        """Get existing external_device_id for a camera in an organization."""
        result = (
            self.db.query(self.model.external_device_id)
            .filter(
                self.model.organization_id == organization_id,
                self.model.camera_id == camera_id,
                self.model.external_device_id.isnot(None)
            )
            .limit(1)
            .scalar()
        )
        return result

    def get_by_client_detection_id(
        self,
        organization_id: int,
        client_detection_id: str
    ) -> Optional[AnprDetection]:
        """Get detection by client's tracking ID."""
        return (
            self.db.query(self.model)
            .filter(
                self.model.organization_id == organization_id,
                self.model.client_detection_id == client_detection_id
            )
            .first()
        )

    def get_by_camera(
        self,
        organization_id: int,
        camera_id: str,
        skip: int = 0,
        limit: int = 100,
        status: Optional[ProcessingStatus] = None
    ) -> List[AnprDetection]:
        """Get detections for a specific camera."""
        query = self.db.query(self.model).filter(
            self.model.organization_id == organization_id,
            self.model.camera_id == camera_id
        )

        if status:
            query = query.filter(self.model.status == status)

        return query.order_by(desc(self.model.created_at)).offset(skip).limit(limit).all()

    def get_by_status(
        self,
        status: ProcessingStatus,
        skip: int = 0,
        limit: int = 100
    ) -> List[AnprDetection]:
        """Get detections by processing status."""
        return (
            self.db.query(self.model)
            .filter(self.model.status == status)
            .order_by(desc(self.model.created_at))
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_pending_for_retry(self, max_retries: int = 3) -> List[AnprDetection]:
        """Get failed detections that haven't exceeded max retries."""
        return (
            self.db.query(self.model)
            .filter(
                self.model.status.in_([ProcessingStatus.FAILED, ProcessingStatus.RETRYING]),
                self.model.retry_count < max_retries
            )
            .order_by(desc(self.model.created_at))
            .all()
        )

    def get_stats_by_organization(self, organization_id: int) -> Dict[str, Any]:
        """Get processing statistics for an organization."""
        total = self.db.query(func.count(self.model.id)).filter(
            self.model.organization_id == organization_id
        ).scalar()

        success = self.db.query(func.count(self.model.id)).filter(
            self.model.organization_id == organization_id,
            self.model.status == ProcessingStatus.SUCCESS
        ).scalar()

        failed = self.db.query(func.count(self.model.id)).filter(
            self.model.organization_id == organization_id,
            self.model.status == ProcessingStatus.FAILED
        ).scalar()

        pending = self.db.query(func.count(self.model.id)).filter(
            self.model.organization_id == organization_id,
            self.model.status == ProcessingStatus.PENDING
        ).scalar()

        processing = self.db.query(func.count(self.model.id)).filter(
            self.model.organization_id == organization_id,
            self.model.status == ProcessingStatus.PROCESSING
        ).scalar()

        return {
            "total": total or 0,
            "success": success or 0,
            "failed": failed or 0,
            "pending": pending or 0,
            "processing": processing or 0,
            "success_rate": round((success / total * 100), 2) if total > 0 else 0
        }

    def search_by_numberplate(
        self,
        numberplate: str,
        organization_id: Optional[int] = None,
        skip: int = 0,
        limit: int = 100
    ) -> List[AnprDetection]:
        """Search detections by numberplate text."""
        query = self.db.query(self.model).filter(
            self.model.numberplate_text.ilike(f"%{numberplate}%")
        )

        if organization_id:
            query = query.filter(self.model.organization_id == organization_id)

        return query.order_by(desc(self.model.created_at)).offset(skip).limit(limit).all()

    def get_recent(
        self,
        limit: int = 10,
        organization_id: Optional[int] = None
    ) -> List[AnprDetection]:
        """Get most recent detections."""
        query = self.db.query(self.model)

        if organization_id:
            query = query.filter(self.model.organization_id == organization_id)

        return query.order_by(desc(self.model.created_at)).limit(limit).all()

    def _build_filter_query(
        self,
        organization_id: Optional[int] = None,
        status: Optional[ProcessingStatus] = None,
        camera_id: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        activity_type: Optional[str] = None,
        plate: Optional[str] = None
    ):
        """Build a base query with common filters."""
        query = self.db.query(self.model)

        if organization_id is not None:
            query = query.filter(self.model.organization_id == organization_id)

        if status:
            query = query.filter(self.model.status == status)

        if camera_id:
            query = query.filter(self.model.camera_id == camera_id)

        if start_date:
            query = query.filter(self.model.created_at >= start_date)

        if end_date:
            query = query.filter(self.model.created_at <= end_date)

        if activity_type:
            query = query.filter(self.model.activity_type == activity_type.lower())

        if plate:
            query = query.filter(self.model.numberplate_text.ilike(f"%{plate}%"))

        return query

    def get_all_with_filters(
        self,
        skip: int = 0,
        limit: int = 100,
        status: Optional[ProcessingStatus] = None,
        camera_id: Optional[str] = None,
        organization_id: Optional[int] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        activity_type: Optional[str] = None,
        plate: Optional[str] = None
    ) -> List[AnprDetection]:
        """Get all detections with optional filters."""
        query = self._build_filter_query(
            organization_id=organization_id,
            status=status,
            camera_id=camera_id,
            start_date=start_date,
            end_date=end_date,
            activity_type=activity_type,
            plate=plate
        )
        return query.order_by(desc(self.model.created_at)).offset(skip).limit(limit).all()

    def count_with_filters(
        self,
        organization_id: Optional[int] = None,
        status: Optional[ProcessingStatus] = None,
        camera_id: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        activity_type: Optional[str] = None,
        plate: Optional[str] = None
    ) -> int:
        """Count detections with optional filters."""
        query = self._build_filter_query(
            organization_id=organization_id,
            status=status,
            camera_id=camera_id,
            start_date=start_date,
            end_date=end_date,
            activity_type=activity_type,
            plate=plate
        )
        return query.count()

    def get_filtered_for_report(
        self,
        organization_id: Optional[int] = None,
        camera_id: Optional[str] = None,
        activity_type: Optional[str] = None,
        date_filter: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        status: Optional[ProcessingStatus] = None,
        plate: Optional[str] = None
    ) -> List[AnprDetection]:
        """Get filtered detections for reports with date range support."""
        query = self.db.query(self.model).join(self.model.organization)

        # Organization filter
        if organization_id:
            query = query.filter(self.model.organization_id == organization_id)

        # Camera filter
        if camera_id:
            query = query.filter(self.model.camera_id == camera_id)

        # Activity type filter
        if activity_type:
            query = query.filter(self.model.activity_type == activity_type.lower())

        # Status filter
        if status:
            query = query.filter(self.model.status == status)

        # Plate search filter
        if plate:
            query = query.filter(self.model.numberplate_text.ilike(f"%{plate}%"))

        # Date filtering
        now = datetime.utcnow()
        if date_filter == "today":
            start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
            query = query.filter(self.model.created_at >= start_of_day)
        elif date_filter == "yesterday":
            start_of_yesterday = (now - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
            start_of_today = now.replace(hour=0, minute=0, second=0, microsecond=0)
            query = query.filter(
                and_(
                    self.model.created_at >= start_of_yesterday,
                    self.model.created_at < start_of_today
                )
            )
        elif date_filter == "this_week":
            start_of_week = now - timedelta(days=now.weekday())
            start_of_week = start_of_week.replace(hour=0, minute=0, second=0, microsecond=0)
            query = query.filter(self.model.created_at >= start_of_week)
        elif date_filter == "this_month":
            start_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            query = query.filter(self.model.created_at >= start_of_month)
        elif date_filter == "custom":
            if start_date:
                query = query.filter(self.model.created_at >= start_date)
            if end_date:
                query = query.filter(self.model.created_at <= end_date)

        return query.order_by(desc(self.model.created_at)).all()

    def get_distinct_cameras(
        self,
        organization_id: Optional[int] = None,
        skip: int = 0,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Get distinct cameras with detection counts."""
        query = self.db.query(
            self.model.camera_id,
            self.model.camera_name,
            self.model.organization_id,
            func.count(self.model.id).label('detection_count'),
            func.max(self.model.created_at).label('last_detection'),
            func.min(self.model.created_at).label('first_detection')
        )

        if organization_id:
            query = query.filter(self.model.organization_id == organization_id)

        result = query.group_by(
            self.model.camera_id,
            self.model.camera_name,
            self.model.organization_id
        ).order_by(desc('detection_count')).offset(skip).limit(limit).all()

        return [
            {
                'camera_id': row.camera_id,
                'camera_name': row.camera_name or row.camera_id,
                'organization_id': row.organization_id,
                'detection_count': row.detection_count or 0,
                'last_detection': row.last_detection,
                'first_detection': row.first_detection
            }
            for row in result
        ]

    def count_distinct_cameras(
        self,
        organization_id: Optional[int] = None
    ) -> int:
        """Count distinct cameras."""
        query = self.db.query(
            self.model.camera_id,
            self.model.organization_id
        )

        if organization_id:
            query = query.filter(self.model.organization_id == organization_id)

        return query.group_by(
            self.model.camera_id,
            self.model.organization_id
        ).count()

    def _apply_common_filters(
        self,
        query,
        organization_id: Optional[int] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        camera_id: Optional[str] = None,
        activity_type: Optional[str] = None,
        status: Optional[ProcessingStatus] = None,
        plate: Optional[str] = None
    ):
        """Apply common filters to any query (works for aggregate queries too)."""
        if organization_id:
            query = query.filter(self.model.organization_id == organization_id)
        if start_date:
            query = query.filter(self.model.created_at >= start_date)
        if end_date:
            query = query.filter(self.model.created_at <= end_date)
        if camera_id:
            query = query.filter(self.model.camera_id == camera_id)
        if activity_type:
            query = query.filter(self.model.activity_type == activity_type.lower())
        if status:
            query = query.filter(self.model.status == status)
        if plate:
            query = query.filter(self.model.numberplate_text.ilike(f"%{plate}%"))
        return query

    def get_hourly_stats(
        self,
        organization_id: Optional[int] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        camera_id: Optional[str] = None,
        activity_type: Optional[str] = None,
        status: Optional[ProcessingStatus] = None,
        plate: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get hourly detection statistics."""
        from sqlalchemy import extract, case

        query = self.db.query(
            extract('hour', self.model.created_at).label('hour'),
            func.count(self.model.id).label('total'),
            func.sum(case((self.model.status == ProcessingStatus.SUCCESS, 1), else_=0)).label('success'),
            func.sum(case((self.model.status == ProcessingStatus.FAILED, 1), else_=0)).label('failed'),
            func.sum(case((self.model.activity_type == 'in', 1), else_=0)).label('in_count'),
            func.sum(case((self.model.activity_type == 'out', 1), else_=0)).label('out_count')
        )

        query = self._apply_common_filters(query, organization_id, start_date, end_date, camera_id, activity_type, status, plate)

        result = query.group_by(extract('hour', self.model.created_at)).order_by('hour').all()

        return [
            {
                'hour': int(row.hour) if row.hour is not None else 0,
                'total': row.total or 0,
                'success': row.success or 0,
                'failed': row.failed or 0,
                'in_count': row.in_count or 0,
                'out_count': row.out_count or 0
            }
            for row in result
        ]

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
    ) -> List[Dict[str, Any]]:
        """Get daily detection statistics for the last N days or a custom date range."""
        from sqlalchemy import cast, Date, case

        # Use custom date range if provided, otherwise fall back to days
        if not start_date:
            start_date = datetime.utcnow() - timedelta(days=days)

        query = self.db.query(
            cast(self.model.created_at, Date).label('date'),
            func.count(self.model.id).label('total'),
            func.sum(case((self.model.status == ProcessingStatus.SUCCESS, 1), else_=0)).label('success'),
            func.sum(case((self.model.status == ProcessingStatus.FAILED, 1), else_=0)).label('failed'),
            func.sum(case((self.model.activity_type == 'in', 1), else_=0)).label('in_count'),
            func.sum(case((self.model.activity_type == 'out', 1), else_=0)).label('out_count')
        ).filter(self.model.created_at >= start_date)

        query = self._apply_common_filters(query, organization_id, None, end_date, camera_id, activity_type, status, plate)

        result = query.group_by(cast(self.model.created_at, Date)).order_by('date').all()

        return [
            {
                'date': row.date.strftime('%Y-%m-%d') if row.date else None,
                'total': row.total or 0,
                'success': row.success or 0,
                'failed': row.failed or 0,
                'in_count': row.in_count or 0,
                'out_count': row.out_count or 0,
                'success_rate': round((row.success / row.total * 100), 2) if row.total > 0 else 0
            }
            for row in result
        ]

    def get_weekly_stats(
        self,
        organization_id: Optional[int] = None,
        weeks: int = 12,
        camera_id: Optional[str] = None,
        activity_type: Optional[str] = None,
        status: Optional[ProcessingStatus] = None,
        plate: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get weekly detection statistics for the last N weeks."""
        from sqlalchemy import extract, case

        start_date = datetime.utcnow() - timedelta(weeks=weeks)

        query = self.db.query(
            extract('year', self.model.created_at).label('year'),
            extract('week', self.model.created_at).label('week'),
            func.count(self.model.id).label('total'),
            func.sum(case((self.model.status == ProcessingStatus.SUCCESS, 1), else_=0)).label('success'),
            func.sum(case((self.model.status == ProcessingStatus.FAILED, 1), else_=0)).label('failed'),
            func.sum(case((self.model.activity_type == 'in', 1), else_=0)).label('in_count'),
            func.sum(case((self.model.activity_type == 'out', 1), else_=0)).label('out_count')
        ).filter(self.model.created_at >= start_date)

        query = self._apply_common_filters(query, organization_id, None, None, camera_id, activity_type, status, plate)

        result = query.group_by(
            extract('year', self.model.created_at),
            extract('week', self.model.created_at)
        ).order_by('year', 'week').all()

        return [
            {
                'year': int(row.year) if row.year else 0,
                'week': int(row.week) if row.week else 0,
                'total': row.total or 0,
                'success': row.success or 0,
                'failed': row.failed or 0,
                'in_count': row.in_count or 0,
                'out_count': row.out_count or 0,
                'success_rate': round((row.success / row.total * 100), 2) if row.total > 0 else 0
            }
            for row in result
        ]

    def get_monthly_stats(
        self,
        organization_id: Optional[int] = None,
        months: int = 12,
        camera_id: Optional[str] = None,
        activity_type: Optional[str] = None,
        status: Optional[ProcessingStatus] = None,
        plate: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get monthly detection statistics for the last N months."""
        from sqlalchemy import extract, case

        start_date = datetime.utcnow() - timedelta(days=months * 30)

        query = self.db.query(
            extract('year', self.model.created_at).label('year'),
            extract('month', self.model.created_at).label('month'),
            func.count(self.model.id).label('total'),
            func.sum(case((self.model.status == ProcessingStatus.SUCCESS, 1), else_=0)).label('success'),
            func.sum(case((self.model.status == ProcessingStatus.FAILED, 1), else_=0)).label('failed'),
            func.sum(case((self.model.activity_type == 'in', 1), else_=0)).label('in_count'),
            func.sum(case((self.model.activity_type == 'out', 1), else_=0)).label('out_count')
        ).filter(self.model.created_at >= start_date)

        query = self._apply_common_filters(query, organization_id, None, None, camera_id, activity_type, status, plate)

        result = query.group_by(
            extract('year', self.model.created_at),
            extract('month', self.model.created_at)
        ).order_by('year', 'month').all()

        return [
            {
                'year': int(row.year) if row.year else 0,
                'month': int(row.month) if row.month else 0,
                'total': row.total or 0,
                'success': row.success or 0,
                'failed': row.failed or 0,
                'in_count': row.in_count or 0,
                'out_count': row.out_count or 0,
                'success_rate': round((row.success / row.total * 100), 2) if row.total > 0 else 0
            }
            for row in result
        ]

    def get_vehicle_type_stats(
        self,
        organization_id: Optional[int] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        camera_id: Optional[str] = None,
        activity_type: Optional[str] = None,
        status: Optional[ProcessingStatus] = None,
        plate: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get vehicle type distribution statistics."""
        query = self.db.query(
            self.model.vehicle_class.label('vehicle_type'),
            func.count(self.model.id).label('count')
        ).filter(self.model.vehicle_class.isnot(None))

        query = self._apply_common_filters(query, organization_id, start_date, end_date, camera_id, activity_type, status, plate)

        result = query.group_by(self.model.vehicle_class).order_by(desc('count')).all()

        return [
            {
                'vehicle_type': row.vehicle_type or 'unknown',
                'count': row.count or 0
            }
            for row in result
        ]

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
    ) -> List[Dict[str, Any]]:
        """Get top performing cameras by detection count."""
        from sqlalchemy import case

        query = self.db.query(
            self.model.camera_id,
            self.model.camera_name,
            func.count(self.model.id).label('total'),
            func.sum(case((self.model.status == ProcessingStatus.SUCCESS, 1), else_=0)).label('success'),
            func.sum(case((self.model.status == ProcessingStatus.FAILED, 1), else_=0)).label('failed')
        )

        query = self._apply_common_filters(query, organization_id, start_date, end_date, camera_id, activity_type, status, plate)

        result = query.group_by(
            self.model.camera_id,
            self.model.camera_name
        ).order_by(desc('total')).limit(limit).all()

        return [
            {
                'camera_id': row.camera_id,
                'camera_name': row.camera_name or row.camera_id,
                'total': row.total or 0,
                'success': row.success or 0,
                'failed': row.failed or 0,
                'success_rate': round((row.success / row.total * 100), 2) if row.total > 0 else 0
            }
            for row in result
        ]
