"""
Celery tasks for syncing data to external ANPR server.
All external API calls go through these async tasks with 3 retries.
"""
import base64
import os


def _fmt_dt(dt) -> str:
    """Format a datetime as 'YYYY-MM-DDTHH:MM:SS.mmmZ' for the external server."""
    if dt is None:
        return None
    return dt.strftime("%Y-%m-%dT%H:%M:%S.") + f"{dt.microsecond // 1000:03d}Z"

from celery import Task
from sqlalchemy.orm import Session

from app.core.celery_app import celery_app
from app.core.config import settings
from app.core.logging import app_logger as logger
from app.db.session import SessionLocal
from app.services.external_sync_service import get_external_sync_service
from app.repositories.organization_repository import OrganizationRepository
from app.repositories.anpr_repository import AnprDetectionRepository


class DatabaseTask(Task):
    """Base task with database session management."""
    _db = None

    @property
    def db(self) -> Session:
        if self._db is None:
            self._db = SessionLocal()
        return self._db

    def after_return(self, *args, **kwargs):
        if self._db is not None:
            self._db.close()
            self._db = None


@celery_app.task(bind=True, base=DatabaseTask, name="sync_org_create", max_retries=3)
def sync_org_create(self, org_id: int, org_name: str, org_token: str):
    """
    Sync organization creation to external server.
    Retries: max 3, exponential backoff (60s, 120s, 240s).
    """
    try:
        sync_service = get_external_sync_service()
        if not sync_service.is_enabled:
            logger.info(f"External sync disabled, skipping org create {org_id}")
            return {"status": "skipped", "org_id": org_id}

        logger.info(f"Syncing org create to external: org_id={org_id}, name={org_name}")
        ext_id = sync_service.organization.create(
            name=org_name,
            password=org_token[:20],
            role="admin",
        )

        # Store external org ID in our DB
        db = self.db
        repo = OrganizationRepository(db)
        repo.update(org_id, {"external_org_id": ext_id})
        db.commit()

        logger.info(f"Org {org_id} synced to external server: {ext_id}")
        return {"status": "success", "org_id": org_id, "external_org_id": ext_id}

    except Exception as exc:
        current_retry = self.request.retries
        logger.error(f"External sync failed for org create {org_id}: {exc} (attempt {current_retry + 1}/3)")

        if current_retry < 3:
            retry_delay = 60 * (2 ** current_retry)
            raise self.retry(exc=exc, countdown=retry_delay)
        else:
            logger.error(f"Org create sync failed permanently for org {org_id}")
            return {"status": "failed", "org_id": org_id, "error": str(exc)}


@celery_app.task(bind=True, base=DatabaseTask, name="sync_org_update", max_retries=3)
def sync_org_update(self, org_id: int, external_org_id: str, org_name: str,
                    org_token: str, update_fields: dict):
    """
    Sync organization update to external server.
    If external_org_id is missing, self-heals by creating first.
    """
    try:
        sync_service = get_external_sync_service()
        if not sync_service.is_enabled:
            return {"status": "skipped", "org_id": org_id}

        if external_org_id:
            logger.info(f"Syncing org update to external: org_id={org_id}")
            sync_service.organization.update(
                external_org_id=external_org_id,
                name=update_fields.get("name"),
                status="in-active" if update_fields.get("is_active") is False else None,
            )
            return {"status": "success", "org_id": org_id}
        else:
            # Self-healing: create on external if never synced
            logger.info(f"Self-healing: creating org {org_id} on external (was never synced)")
            ext_id = sync_service.organization.create(
                name=org_name,
                password=org_token[:20],
                role="admin",
            )
            db = self.db
            repo = OrganizationRepository(db)
            repo.update(org_id, {"external_org_id": ext_id})
            db.commit()
            return {"status": "success", "org_id": org_id, "external_org_id": ext_id}

    except Exception as exc:
        current_retry = self.request.retries
        logger.error(f"External sync failed for org update {org_id}: {exc} (attempt {current_retry + 1}/3)")

        if current_retry < 3:
            retry_delay = 60 * (2 ** current_retry)
            raise self.retry(exc=exc, countdown=retry_delay)
        else:
            logger.error(f"Org update sync failed permanently for org {org_id}")
            return {"status": "failed", "org_id": org_id, "error": str(exc)}


@celery_app.task(bind=True, name="sync_org_delete", max_retries=3)
def sync_org_delete(self, org_id: int, external_org_id: str):
    """
    Sync organization deletion to external server.
    """
    try:
        sync_service = get_external_sync_service()
        if not sync_service.is_enabled:
            return {"status": "skipped", "org_id": org_id}

        if not external_org_id:
            logger.info(f"No external_org_id for org {org_id}, skipping external delete")
            return {"status": "skipped", "org_id": org_id}

        logger.info(f"Syncing org delete to external: org_id={org_id}, ext_id={external_org_id}")
        sync_service.organization.delete(external_org_id)
        return {"status": "success", "org_id": org_id}

    except Exception as exc:
        current_retry = self.request.retries
        logger.error(f"External sync failed for org delete {org_id}: {exc} (attempt {current_retry + 1}/3)")

        if current_retry < 3:
            retry_delay = 60 * (2 ** current_retry)
            raise self.retry(exc=exc, countdown=retry_delay)
        else:
            logger.error(f"Org delete sync failed permanently for org {org_id}")
            return {"status": "failed", "org_id": org_id, "error": str(exc)}


@celery_app.task(bind=True, base=DatabaseTask, name="sync_detection", max_retries=3)
def sync_detection(self, detection_id: int):
    """
    Sync detection to external server as device + vehicle.
    Fired after LLM processing succeeds — so numberplate data is available.
    On failure after all retries, logs and moves on — does not mark as failed.
    """
    try:
        sync_service = get_external_sync_service()
        if not sync_service.is_enabled:
            logger.info(f"External sync disabled, skipping detection {detection_id}")
            return {"status": "skipped", "detection_id": detection_id}

        if not settings.EXTERNAL_DETECTION_SYNC_ENABLED:
            logger.info(f"Detection sync disabled (EXTERNAL_DETECTION_SYNC_ENABLED=false), skipping detection {detection_id}")
            return {"status": "skipped", "detection_id": detection_id}

        db = self.db
        repo = AnprDetectionRepository(db)
        org_repo = OrganizationRepository(db)

        # 1. Load detection
        detection = repo.get_by_id(detection_id)
        if not detection:
            logger.error(f"Detection {detection_id} not found for sync")
            return {"status": "error", "message": "Detection not found"}

        # 2. Check org has external_org_id
        org = org_repo.get_by_id(detection.organization_id)
        if not org or not org.external_org_id:
            logger.info(f"Org {detection.organization_id} not synced to external, skipping detection {detection_id}")
            return {"status": "skipped", "reason": "org not synced"}

        external_org_id = org.external_org_id

        # 3. Find or create device for this camera
        external_device_id = repo.get_external_device_id(
            organization_id=detection.organization_id,
            camera_id=detection.camera_id
        )

        if not external_device_id:
            device_name = detection.camera_name or detection.camera_id
            logger.info(f"Creating device on external for camera={device_name}")
            external_device_id = sync_service.device.create(
                name=device_name,
                source=None,
                frame_type=None,
                status="active",
                organization_id=external_org_id,
            )

        # 4. Read image and encode to base64 data URI
        image_full_path = os.path.join(settings.UPLOAD_DIR, detection.image_path)
        vehicle_image_b64 = None
        if os.path.exists(image_full_path):
            with open(image_full_path, "rb") as f:
                raw_b64 = base64.b64encode(f.read()).decode("utf-8")
                # External server expects data URI format
                ext = os.path.splitext(image_full_path)[1].lower()
                mime = "image/png" if ext == ".png" else "image/jpeg"
                vehicle_image_b64 = f"data:{mime};base64,{raw_b64}"

        # 5. Get numberplate from LLM results if available, otherwise send empty
        number_plate = ""
        if detection.numberplate_available and detection.numberplate_text and detection.numberplate_text != "N/A":
            number_plate = detection.numberplate_text

        # 6. Create vehicle on external server with LLM results
        device_name = detection.camera_name or detection.camera_id
        external_vehicle_id = sync_service.vehicle.create(
            number_plate=number_plate,
            vehicle_type=detection.vehicle_class,
            device_name=device_name,
            report_id=str(detection.id),
            number_plate_image=vehicle_image_b64,
            vehicle_image=vehicle_image_b64,
            device_id=external_device_id,
            organization_id=external_org_id,
            created_at=_fmt_dt(detection.detected_at),
            updated_at=_fmt_dt(detection.detected_at),
        )

        # 7. Update detection with external IDs
        repo.update(detection_id, {
            "external_device_id": external_device_id,
            "external_vehicle_id": external_vehicle_id,
            "sync_status": "synced",
        })
        db.commit()

        logger.info(f"Detection {detection_id} synced: device={external_device_id}, vehicle={external_vehicle_id}")
        return {"status": "success", "detection_id": detection_id}

    except Exception as exc:
        current_retry = self.request.retries
        logger.error(f"External sync failed for detection {detection_id}: {exc} (attempt {current_retry + 1}/3)")

        if current_retry < 3:
            retry_delay = 60 * (2 ** current_retry)
            raise self.retry(exc=exc, countdown=retry_delay)
        else:
            # All retries exhausted — log and move on, don't mark as failed
            logger.error(f"Detection sync failed permanently for {detection_id}, moving on")
            return {"status": "skipped", "detection_id": detection_id, "error": str(exc)}
