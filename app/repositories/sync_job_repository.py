"""
Repository for SyncJob — bulk date-range sync run tracking.
"""
from typing import List, Optional

from sqlalchemy.orm import Session

from app.models.sync_job import SyncJob
from app.repositories.base_repository import BaseRepository


# Statuses that mean a job is still occupying the single active slot
ACTIVE_STATUSES = ("pending", "running", "cancelling")


class SyncJobRepository(BaseRepository[SyncJob]):
    """Repository for SyncJob model."""

    def __init__(self, db: Session):
        super().__init__(SyncJob, db)

    def get_active_job(self) -> Optional[SyncJob]:
        """Return the currently active job (pending/running/cancelling), if any."""
        return (
            self.db.query(SyncJob)
            .filter(SyncJob.status.in_(ACTIVE_STATUSES))
            .order_by(SyncJob.id.desc())
            .first()
        )

    def get_current(self) -> Optional[SyncJob]:
        """Return the active job if one exists, otherwise the most recent job."""
        active = self.get_active_job()
        if active:
            return active
        return self.db.query(SyncJob).order_by(SyncJob.id.desc()).first()

    def is_cancel_requested(self, job_id: int) -> bool:
        """Lightweight check: has cancellation been requested for this job?"""
        status = (
            self.db.query(SyncJob.status)
            .filter(SyncJob.id == job_id)
            .scalar()
        )
        return status == "cancelling"

    def increment_counts(
        self,
        job_id: int,
        success: int = 0,
        fail: int = 0,
        skipped: int = 0,
    ) -> Optional[SyncJob]:
        """Atomically bump the progress counters on a job row."""
        job = self.get_by_id(job_id)
        if job is None:
            return None
        job.success_count = (job.success_count or 0) + success
        job.fail_count = (job.fail_count or 0) + fail
        job.skipped_count = (job.skipped_count or 0) + skipped
        self.db.commit()
        self.db.refresh(job)
        return job

    def list_recent(self, skip: int = 0, limit: int = 50) -> List[SyncJob]:
        """List recent jobs, newest first."""
        return (
            self.db.query(SyncJob)
            .order_by(SyncJob.id.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )
