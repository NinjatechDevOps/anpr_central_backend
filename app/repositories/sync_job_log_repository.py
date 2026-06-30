"""
Repository for SyncJobLog - per-detection audit entries written by the bulk sync task.
"""
from typing import Dict, List, Set, Tuple

from sqlalchemy.orm import Session

from app.models.organization import Organization
from app.models.sync_job_log import SyncJobLog
from app.repositories.base_repository import BaseRepository


class SyncJobLogRepository(BaseRepository[SyncJobLog]):
    """Repository for SyncJobLog model."""

    def __init__(self, db: Session):
        super().__init__(SyncJobLog, db)

    def get_by_job(self, job_id: int, skip: int = 0, limit: int = 100) -> List[Tuple[SyncJobLog, str]]:
        """
        Return log entries for a single job with the org name, newest first.
        Each item is a (SyncJobLog, organization_name) tuple.
        Organization name is looked up by matching external_org_id on the
        local organizations table.
        """
        return (
            self.db.query(SyncJobLog, Organization.name)
            .outerjoin(
                Organization,
                Organization.external_org_id == SyncJobLog.external_org_id,
            )
            .filter(SyncJobLog.sync_job_id == job_id)
            .order_by(SyncJobLog.id.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    def count_by_job(self, job_id: int) -> int:
        """Total log entries for a job."""
        return (
            self.db.query(SyncJobLog)
            .filter(SyncJobLog.sync_job_id == job_id)
            .count()
        )

    def has_logs_for_job(self, job_id: int) -> bool:
        """True if at least one log entry exists for this job."""
        return (
            self.db.query(SyncJobLog.id)
            .filter(SyncJobLog.sync_job_id == job_id)
            .first()
        ) is not None

    def get_job_ids_with_logs(self, job_ids: List[int]) -> Set[int]:
        """
        Return the subset of job_ids that have at least one log entry.
        Single query — used by the listing endpoint to populate has_logs for each job.
        """
        if not job_ids:
            return set()
        rows = (
            self.db.query(SyncJobLog.sync_job_id)
            .filter(SyncJobLog.sync_job_id.in_(job_ids))
            .distinct()
            .all()
        )
        return {row[0] for row in rows}
