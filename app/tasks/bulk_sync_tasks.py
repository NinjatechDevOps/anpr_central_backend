"""
Celery task for UI-triggered, date-range bulk sync of detections to the external
ANPR server.

Mirrors the idempotent logic of scripts/resync_detections.py:
  - one device per org (verify on external, else create)
  - per detection: GET vehicle find-one first
      * found with data  -> skip entirely, leave DB untouched (skipped_count)
      * missing / null    -> (re)create on external, then stamp the local row
                             status=SUCCESS, sync_status="synced" (success_count)
      * error             -> fail_count

Progress is written to the sync_jobs row after every record so the
GET /api/v1/sync-jobs/current endpoint can show it live. Cancellation is
cooperative: the cancel endpoint flips the job to "cancelling" and the task
stops at the next record boundary.
"""
import base64
import os
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.celery_app import celery_app
from app.core.config import settings
from app.core.logging import app_logger as logger
from app.core.exceptions import ExternalSyncException
from app.models.anpr_detection import AnprDetection, ProcessingStatus
from app.models.organization import Organization
from app.repositories.anpr_repository import AnprDetectionRepository
from app.repositories.sync_job_repository import SyncJobRepository
from app.repositories.sync_job_log_repository import SyncJobLogRepository
from app.services.external_sync_service import get_external_sync_service
from app.services.numberplate_provider_factory import get_numberplate_service
from app.tasks.sync_tasks import DatabaseTask


# ---------------------------------------------------------------------------
# Helpers (same logic as scripts/resync_detections.py)
# ---------------------------------------------------------------------------

def _fmt_dt(dt) -> str:
    """Format a datetime as 'YYYY-MM-DDTHH:MM:SS.mmmZ' for the external server."""
    if dt is None:
        return None
    return dt.strftime("%Y-%m-%dT%H:%M:%S.") + f"{dt.microsecond // 1000:03d}Z"


def get_image_b64(image_path: str):
    """Read image from disk and return a base64 data URI, or None if missing."""
    if not image_path:
        return None
    full_path = os.path.join(settings.UPLOAD_DIR, image_path)
    if not os.path.exists(full_path):
        return None
    with open(full_path, "rb") as f:
        raw_b64 = base64.b64encode(f.read()).decode("utf-8")
    ext = os.path.splitext(full_path)[1].lower()
    mime = "image/png" if ext == ".png" else "image/jpeg"
    return f"data:{mime};base64,{raw_b64}"


def get_number_plate(detection: AnprDetection) -> str:
    """Number plate string for the external payload (raw, like resync)."""
    return detection.numberplate_text


def run_numberplate_extraction(detection: AnprDetection, db: Session, det_repo: AnprDetectionRepository) -> str:
    """
    Run numberplate extraction via the configured provider (same factory as the
    automatic upload pipeline). Never raises — any failure is swallowed and
    logged so a sync attempt is never blocked on extraction.
    """
    service = get_numberplate_service()
    if service is None:
        return "extraction skipped (no provider configured)"

    try:
        if not service.validate_image(detection.image_path):
            return "extraction skipped (invalid image)"
        result = service.extract_numberplate(image_path=detection.image_path)
    except Exception as exc:
        return f"extraction failed ({exc})"

    det_repo.update(detection.id, {
        "numberplate_available": result.numberplate_available if result else False,
        "numberplate_text": result.numberplate_text if result and result.numberplate_text else "N/A",
        "numberplate_color": result.numberplate_color if result and result.numberplate_color else "unknown",
        "vehicle_side": result.vehicle_side if result and result.vehicle_side else "unknown",
        "llm_confidence": str(result.confidence_score) if result else "0.0",
        "llm_raw_response": result.reasoning if result and result.reasoning else "N/A",
        "processed_at": datetime.now(timezone.utc),
    })
    db.commit()
    db.refresh(detection)

    plate = result.numberplate_text if result and result.numberplate_available else "none"
    return f"extraction done (plate={plate})"


def _resolve_org_device(sync_service, db: Session, org) -> str:
    """
    Resolve the single external device id for an org.

    Reuse any device id already stored on the org's detections (verified on the
    external server); otherwise return None so the caller creates one lazily.
    """
    existing_device = (
        db.query(AnprDetection.external_device_id)
        .filter(
            AnprDetection.organization_id == org.id,
            AnprDetection.external_device_id.isnot(None),
        )
        .limit(1)
        .scalar()
    )
    if not existing_device:
        return None
    try:
        sync_service.device.find_one(existing_device)
        logger.info(f"[bulk-sync] org={org.id} reusing device {existing_device}")
        return existing_device
    except ExternalSyncException as err:
        logger.warning(
            f"[bulk-sync] org={org.id} device {existing_device} not on external "
            f"({err}); will create a new one."
        )
        return None


@celery_app.task(bind=True, base=DatabaseTask, name="bulk_sync_detections_by_range")
def bulk_sync_detections_by_range(self, job_id: int):
    """Run a date-range bulk sync for the given sync_jobs row."""
    db: Session = self.db
    job_repo = SyncJobRepository(db)
    det_repo = AnprDetectionRepository(db)
    log_repo = SyncJobLogRepository(db)

    job = job_repo.get_by_id(job_id)
    if not job:
        logger.error(f"[bulk-sync] job {job_id} not found")
        return {"status": "error", "message": "job not found"}

    # Mark running. Reset the progress counters too: if this task is a
    # redelivered rerun of the same job_id (e.g. the worker was killed
    # mid-run and Celery's task_acks_late puts the unacked task back on the
    # queue), starting from 0 here prevents the new pass's increments from
    # stacking on top of the previous (partial) pass's counts.
    job.status = "running"
    job.started_at = datetime.now(timezone.utc)
    job.success_count = 0
    job.fail_count = 0
    job.skipped_count = 0
    db.commit()

    try:
        sync_service = get_external_sync_service()
        if not sync_service.is_enabled:
            job.status = "failed"
            job.error_message = "External sync is disabled (EXTERNAL_SYNC_ENABLED=false or no EXTERNAL_SERVER_URL)."
            job.finished_at = datetime.now(timezone.utc)
            db.commit()
            logger.error(f"[bulk-sync] job {job_id} aborted: external sync disabled")
            return {"status": "failed", "job_id": job_id}

        # Eligible orgs: active, not super-admin, synced to external
        orgs = (
            db.query(Organization)
            .filter(
                Organization.is_active == True,  # noqa: E712
                Organization.is_super_admin == False,  # noqa: E712
                Organization.external_org_id.isnot(None),
            )
            .all()
        )
        org_ids = [o.id for o in orgs]

        # Base filter for detections in this job's window across eligible orgs
        def _range_query():
            return (
                db.query(AnprDetection)
                .filter(
                    AnprDetection.organization_id.in_(org_ids),
                    AnprDetection.is_deleted == False,  # noqa: E712
                    AnprDetection.created_at >= job.from_datetime,
                    AnprDetection.created_at <= job.to_datetime,
                )
            )

        total = _range_query().count() if org_ids else 0
        job.total_records = total
        db.commit()
        logger.info(
            f"[bulk-sync] job {job_id}: {total} detection(s) across "
            f"{len(org_ids)} org(s) in [{job.from_datetime} .. {job.to_datetime}]"
        )

        if total == 0:
            job.status = "completed"
            job.finished_at = datetime.now(timezone.utc)
            db.commit()
            return {"status": "completed", "job_id": job_id, "total": 0}

        cancelled = False

        for org in orgs:
            if cancelled:
                break

            detections = (
                _range_query()
                .filter(AnprDetection.organization_id == org.id)
                .all()
            )
            if not detections:
                continue

            org_device_id = _resolve_org_device(sync_service, db, org)

            for detection in detections:
                # ---- cooperative cancel check (once per record) ----
                if job_repo.is_cancel_requested(job_id):
                    cancelled = True
                    break

                # Capture scalar attrs before the try block so they survive a rollback
                det_id = detection.id
                ext_org_id = org.external_org_id
                cam_id = detection.camera_id
                plate = detection.numberplate_text

                try:
                    # Step 1 — already on external? skip entirely, untouched.
                    if detection.external_vehicle_id:
                        try:
                            vehicle_data = sync_service.vehicle.find_one(detection.external_vehicle_id)
                            actual = vehicle_data.get("data", vehicle_data) if isinstance(vehicle_data, dict) else None
                            if actual and actual.get("id"):
                                sync_service.vehicle.update(
                                    detection.external_vehicle_id,
                                    created_at=_fmt_dt(detection.detected_at),
                                    updated_at=_fmt_dt(detection.detected_at),
                                )
                                log_repo.create({
                                    "sync_job_id": job_id,
                                    "detection_id": det_id,
                                    "external_org_id": ext_org_id,
                                    "camera_id": cam_id,
                                    "external_device_id": org_device_id,
                                    "numberplate_text": plate,
                                    "is_sent": False,
                                    "log_status": "skipped",
                                    "error_message": f"Detection already exists on external server (external_vehicle_id={detection.external_vehicle_id})",
                                    "external_vehicle_id": detection.external_vehicle_id,
                                })
                                job.skipped_count = (job.skipped_count or 0) + 1
                                db.commit()
                                continue
                            # 200 but null data -> fall through and recreate
                        except ExternalSyncException:
                            pass  # not found -> recreate

                    # Step 1.5 — extract numberplate if it's missing/N-A (regardless of processed_at,
                    # which can go stale relative to numberplate_text if it was cleared manually)
                    plate_missing = (
                        not detection.numberplate_text
                        or detection.numberplate_text == "N/A"
                    )
                    if plate_missing:
                        note = run_numberplate_extraction(detection, db, det_repo)
                        logger.info(f"[bulk-sync] detection {det_id} {note}")

                    # Step 2 — ensure org device exists (create lazily, once)
                    if not org_device_id:
                        org_device_id = sync_service.device.create(
                            name=org.name,
                            source=None,
                            frame_type=None,
                            status="active",
                            organization_id=org.external_org_id,
                        )
                        logger.info(f"[bulk-sync] org={org.id} created device {org_device_id}")

                    # Step 3 — image + plate
                    vehicle_image_b64 = get_image_b64(detection.image_path)
                    number_plate = get_number_plate(detection)
                    device_name = detection.camera_name or detection.camera_id

                    # Step 4 — create vehicle on external
                    external_vehicle_id = sync_service.vehicle.create(
                        number_plate=number_plate,
                        vehicle_type=detection.vehicle_class,
                        device_name=device_name,
                        report_id=str(detection.id),
                        number_plate_image=vehicle_image_b64,
                        vehicle_image=vehicle_image_b64,
                        device_id=org_device_id,
                        organization_id=org.external_org_id,
                        created_at=_fmt_dt(detection.detected_at),
                        updated_at=_fmt_dt(detection.detected_at),
                    )

                    # Step 5 — stamp local row: success + synced
                    det_repo.update(detection.id, {
                        "external_device_id": org_device_id,
                        "external_vehicle_id": external_vehicle_id,
                        "status": ProcessingStatus.SUCCESS,
                        "sync_status": "synced",
                    })

                    log_repo.create({
                        "sync_job_id": job_id,
                        "detection_id": det_id,
                        "external_org_id": ext_org_id,
                        "camera_id": cam_id,
                        "external_device_id": org_device_id,
                        "numberplate_text": plate,
                        "is_sent": True,
                        "log_status": "sent",
                        "error_message": None,
                        "external_vehicle_id": external_vehicle_id,
                    })

                    job.success_count = (job.success_count or 0) + 1
                    db.commit()

                except Exception as rec_err:
                    db.rollback()
                    # job object was expired by rollback; reload before mutating
                    job = job_repo.get_by_id(job_id)
                    log_repo.create({
                        "sync_job_id": job_id,
                        "detection_id": det_id,
                        "external_org_id": ext_org_id,
                        "camera_id": cam_id,
                        "external_device_id": org_device_id,
                        "numberplate_text": plate,
                        "is_sent": False,
                        "log_status": "failed",
                        "error_message": str(rec_err),
                        "external_vehicle_id": None,
                    })
                    job.fail_count = (job.fail_count or 0) + 1
                    db.commit()
                    logger.error(f"[bulk-sync] job {job_id} detection {det_id} failed: {rec_err}")

                # mirror progress into Celery state (best-effort)
                self.update_state(state="PROGRESS", meta={
                    "total": job.total_records,
                    "success": job.success_count,
                    "fail": job.fail_count,
                    "skipped": job.skipped_count,
                })

        # Finalize
        job = job_repo.get_by_id(job_id)
        if cancelled:
            job.status = "cancelled"
        elif (job.fail_count or 0) > 0:
            job.status = "completed_with_errors"
        else:
            job.status = "completed"
        job.finished_at = datetime.now(timezone.utc)
        db.commit()

        logger.info(
            f"[bulk-sync] job {job_id} {job.status}: "
            f"success={job.success_count} skipped={job.skipped_count} "
            f"fail={job.fail_count} / total={job.total_records}"
        )
        return {
            "status": job.status,
            "job_id": job_id,
            "success": job.success_count,
            "skipped": job.skipped_count,
            "fail": job.fail_count,
            "total": job.total_records,
        }

    except Exception as exc:
        db.rollback()
        try:
            job = job_repo.get_by_id(job_id)
            if job:
                job.status = "failed"
                job.error_message = str(exc)
                job.finished_at = datetime.now(timezone.utc)
                db.commit()
        except Exception:
            db.rollback()
        logger.error(f"[bulk-sync] job {job_id} aborted with fatal error: {exc}")
        return {"status": "failed", "job_id": job_id, "error": str(exc)}
