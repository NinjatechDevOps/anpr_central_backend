"""
Schemas for the date-range bulk sync job endpoints.
"""
from datetime import datetime
from typing import List, Optional

from pydantic import Field, model_validator

from app.schemas.base import BaseSchema
from app.models.sync_job import SyncJob


class SyncJobCreateRequest(BaseSchema):
    """Request body to start a date-range bulk sync."""

    from_datetime: datetime = Field(..., description="Start of the sync window (filters AnprDetection.created_at, UTC)")
    to_datetime: datetime = Field(..., description="End of the sync window (UTC)")

    @model_validator(mode="after")
    def _check_range(self) -> "SyncJobCreateRequest":
        if self.from_datetime >= self.to_datetime:
            raise ValueError("from_datetime must be earlier than to_datetime")
        return self


class SyncJobResponse(BaseSchema):
    """A sync job row plus derived progress."""

    id: int
    ip: Optional[str] = None
    from_datetime: datetime
    to_datetime: datetime
    status: str
    total_records: int
    success_count: int
    fail_count: int
    skipped_count: int
    progress_percent: float = Field(..., description="(success+fail+skipped)/total * 100")
    celery_task_id: Optional[str] = None
    error_message: Optional[str] = None
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_job(cls, job: SyncJob) -> "SyncJobResponse":
        """Build a response from an ORM SyncJob, computing progress_percent."""
        total = job.total_records or 0
        processed = (job.success_count or 0) + (job.fail_count or 0) + (job.skipped_count or 0)
        progress = round((processed / total * 100), 2) if total > 0 else 0.0
        return cls(
            id=job.id,
            ip=job.ip,
            from_datetime=job.from_datetime,
            to_datetime=job.to_datetime,
            status=job.status,
            total_records=total,
            success_count=job.success_count or 0,
            fail_count=job.fail_count or 0,
            skipped_count=job.skipped_count or 0,
            progress_percent=progress,
            celery_task_id=job.celery_task_id,
            error_message=job.error_message,
            started_at=job.started_at,
            finished_at=job.finished_at,
            created_at=job.created_at,
            updated_at=job.updated_at,
        )


class SyncJobListResponse(BaseSchema):
    """Paginated list of recent sync jobs."""

    jobs: List[SyncJobResponse]
    total: int
