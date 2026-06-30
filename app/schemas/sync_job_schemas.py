"""
Schemas for the date-range bulk sync job endpoints.
"""
from datetime import datetime
from typing import List, Optional

from pydantic import Field, model_validator

from app.schemas.base import BaseSchema
from app.models.sync_job import SyncJob
from app.models.sync_job_log import SyncJobLog


class SyncJobCreateRequest(BaseSchema):
    """Request body to start a date-range bulk sync."""

    from_datetime: datetime = Field(..., description="Start of the sync window (filters AnprDetection.created_at, UTC)")
    to_datetime: datetime = Field(..., description="End of the sync window (UTC)")

    @model_validator(mode="after")
    def _check_range(self) -> "SyncJobCreateRequest":
        if self.from_datetime >= self.to_datetime:
            raise ValueError("from_datetime must be earlier than to_datetime")
        return self


class SyncJobLogResponse(BaseSchema):
    """A single per-detection log entry from a bulk sync job."""

    id: int
    sync_job_id: int
    detection_id: Optional[int] = None
    external_org_id: Optional[str] = None
    organization_name: Optional[str] = None
    camera_id: Optional[str] = None
    external_device_id: Optional[str] = None
    numberplate_text: Optional[str] = None
    is_sent: bool
    log_status: str
    error_message: Optional[str] = None
    external_vehicle_id: Optional[str] = None
    created_at: datetime

    @classmethod
    def from_log(cls, log: SyncJobLog, organization_name: Optional[str] = None) -> "SyncJobLogResponse":
        return cls(
            id=log.id,
            sync_job_id=log.sync_job_id,
            detection_id=log.detection_id,
            external_org_id=log.external_org_id,
            organization_name=organization_name,
            camera_id=log.camera_id,
            external_device_id=log.external_device_id,
            numberplate_text=log.numberplate_text,
            is_sent=log.is_sent,
            log_status=log.log_status,
            error_message=log.error_message,
            external_vehicle_id=log.external_vehicle_id,
            created_at=log.created_at,
        )


class SyncJobLogListResponse(BaseSchema):
    """Paginated list of log entries for a sync job."""

    logs: List[SyncJobLogResponse]
    total: int


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
    has_logs: bool = Field(False, description="True if at least one log entry exists for this job")
    celery_task_id: Optional[str] = None
    error_message: Optional[str] = None
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_job(cls, job: SyncJob, has_logs: bool = False) -> "SyncJobResponse":
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
            has_logs=has_logs,
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
