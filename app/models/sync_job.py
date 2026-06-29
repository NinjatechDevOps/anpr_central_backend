"""
SyncJob model - Tracks date-range bulk sync runs to the external ANPR server.

Each row represents one UI-triggered bulk sync over a [from_datetime, to_datetime]
window. The row is the source of truth for live progress (survives Celery result
expiry) and the audit log (who fired it, via IP).
"""
from sqlalchemy import Column, Integer, String, DateTime, Text

from app.db.session import Base
from app.models.base import BaseModel


# Job status values (plain strings, not an Enum, to match project convention)
#   pending              - row created, task queued, not started yet
#   running              - task is actively syncing
#   cancelling           - cancel requested; task will stop at next record boundary
#   cancelled            - task stopped early on request
#   completed            - finished with no failures
#   completed_with_errors- finished but some records failed
#   failed               - aborted on a fatal error (e.g. external sync disabled)


class SyncJob(Base, BaseModel):
    """
    Bulk date-range sync job record.

    Inherits: id, created_at, updated_at from BaseModel
    """

    __tablename__ = "sync_jobs"

    # Who fired it (X-Forwarded-For first hop, else request.client.host)
    ip = Column(String(64), nullable=True, index=True)

    # Requested sync window (filtered against AnprDetection.created_at)
    from_datetime = Column(DateTime(timezone=True), nullable=False, index=True)
    to_datetime = Column(DateTime(timezone=True), nullable=False, index=True)

    # Job lifecycle status (longest value: "completed_with_errors" = 21 chars)
    status = Column(String(32), default="pending", nullable=False, index=True)

    # Progress counters (success + fail + skipped == processed so far)
    total_records = Column(Integer, default=0, nullable=False)
    success_count = Column(Integer, default=0, nullable=False)   # created/recreated on external
    fail_count = Column(Integer, default=0, nullable=False)      # errored
    skipped_count = Column(Integer, default=0, nullable=False)   # already present on external, untouched

    # Celery linkage (for status cross-check + revoke on cancel)
    celery_task_id = Column(String(100), nullable=True, index=True)

    # Top-level failure message (fatal aborts only)
    error_message = Column(Text, nullable=True)

    # Execution timestamps
    started_at = Column(DateTime(timezone=True), nullable=True)
    finished_at = Column(DateTime(timezone=True), nullable=True)

    def __repr__(self):
        return (
            f"<SyncJob(id={self.id}, status='{self.status}', "
            f"total={self.total_records}, success={self.success_count}, "
            f"skipped={self.skipped_count}, fail={self.fail_count})>"
        )
