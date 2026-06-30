"""
SyncJobLog model - Per-record audit log for bulk sync jobs.

Every detection processed by bulk_sync_detections_by_range gets exactly one row:
  log_status = "sent"    → is_sent=True,  external_vehicle_id set
  log_status = "skipped" → is_sent=False, detection was already on external
  log_status = "failed"  → is_sent=False, error_message contains the exception
"""
from sqlalchemy import Column, String, Boolean, Text, ForeignKey

from app.db.session import Base
from app.models.base import BaseModel


class SyncJobLog(Base, BaseModel):
    """Per-detection record written during a bulk sync job."""

    __tablename__ = "sync_job_logs"

    # Parent job
    sync_job_id = Column(
        ForeignKey("sync_jobs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Detection reference (SET NULL so logs survive detection deletion)
    detection_id = Column(
        ForeignKey("anpr_detections.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Denormalised org/camera info (for display without extra joins)
    external_org_id = Column(String(100), nullable=True, index=True)
    camera_id = Column(String(100), nullable=True)
    external_device_id = Column(String(100), nullable=True)
    numberplate_text = Column(String(20), nullable=True)

    # Outcome
    is_sent = Column(Boolean, nullable=False, default=False)
    log_status = Column(String(20), nullable=False, index=True)  # sent | failed | skipped
    error_message = Column(Text, nullable=True)
    external_vehicle_id = Column(String(100), nullable=True)

    def __repr__(self):
        return (
            f"<SyncJobLog(id={self.id}, job={self.sync_job_id}, "
            f"det={self.detection_id}, status='{self.log_status}')>"
        )
