"""
Script to sync all detections from the central DB to the external ANPR server, org by org.

For each active organization (that has been synced to external), fetches all its detections
and sends them to the external server. If GOOGLE_API_KEY is set, runs LLM numberplate
extraction first; otherwise sends with whatever plate data is already stored.

Usage:
    Local:     python scripts/sync_detections_to_external.py
    Dry run:   python scripts/sync_detections_to_external.py --dry-run
    Force:     python scripts/sync_detections_to_external.py --force
    Docker:    docker exec central-server-worker python scripts/sync_detections_to_external.py
"""
import sys
import os
import base64

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)
os.chdir(PROJECT_ROOT)

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(PROJECT_ROOT, ".env"), override=True)
except ImportError:
    pass

from app.db.session import SessionLocal
from app.models.anpr_detection import AnprDetection
from app.repositories.organization_repository import OrganizationRepository
from app.repositories.anpr_repository import AnprDetectionRepository
from app.services.external_sync_service import get_external_sync_service
from app.core.config import settings
from app.core.logging import app_logger as logger


def get_image_b64(image_path: str):
    """Read image from disk and return base64 data URI, or None if file missing."""
    full_path = os.path.join(settings.UPLOAD_DIR, image_path)
    if not os.path.exists(full_path):
        return None
    with open(full_path, "rb") as f:
        raw_b64 = base64.b64encode(f.read()).decode("utf-8")
    ext = os.path.splitext(full_path)[1].lower()
    mime = "image/png" if ext == ".png" else "image/jpeg"
    return f"data:{mime};base64,{raw_b64}"


def get_number_plate(detection: AnprDetection) -> str:
    """Extract number plate string from detection — same logic as sync_tasks.py."""
    if (detection.numberplate_available
            and detection.numberplate_text
            and detection.numberplate_text != "N/A"):
        return detection.numberplate_text
    return ""


def run_llm(detection: AnprDetection, db, repo: AnprDetectionRepository) -> str:
    """Run LLM extraction and update DB. Returns log message."""
    from app.services.llm_service import get_llm_service
    llm_service = get_llm_service()
    if not llm_service.validate_image(detection.image_path):
        return "LLM skipped (invalid image)"
    llm_result = llm_service.extract_numberplate(image_path=detection.image_path)
    from datetime import datetime
    repo.update(detection.id, {
        "numberplate_available": llm_result.numberplate_available if llm_result else False,
        "numberplate_text": llm_result.numberplate_text if llm_result and llm_result.numberplate_text else None,
        "numberplate_color": llm_result.numberplate_color if llm_result and llm_result.numberplate_color else "unknown",
        "vehicle_side": llm_result.vehicle_side if llm_result and llm_result.vehicle_side else "unknown",
        "llm_confidence": str(llm_result.confidence_score) if llm_result else "0.0",
        "llm_raw_response": llm_result.reasoning if llm_result and llm_result.reasoning else None,
        "processed_at": datetime.utcnow(),
    })
    db.commit()
    db.refresh(detection)
    plate = llm_result.numberplate_text if llm_result and llm_result.numberplate_available else "none"
    return f"LLM done (plate={plate})"


def sync_detections(force: bool = False, dry_run: bool = False):
    db = SessionLocal()
    try:
        org_repo = OrganizationRepository(db)
        det_repo = AnprDetectionRepository(db)
        orgs = org_repo.get_all(skip=0, limit=10000)

        sync_service = get_external_sync_service()
        if not sync_service.is_enabled:
            print("External sync is disabled (EXTERNAL_SYNC_ENABLED=false). Aborting.")
            return

        total_orgs = 0
        total_detections = 0
        total_synced = 0
        total_skipped = 0
        total_failed = 0

        # Cache: (org_id, camera_id) -> external_device_id
        device_cache: dict = {}

        for org in orgs:
            # Skip inactive (soft-deleted), super admin, or unsynced orgs
            if not org.is_active:
                continue
            if org.is_super_admin:
                continue
            if not org.external_org_id:
                print(f"\nOrg [{org.id}] {org.name} — SKIPPED (no external_org_id, run sync_orgs_to_external.py first)")
                continue

            total_orgs += 1
            detections = db.query(AnprDetection).filter(
                AnprDetection.organization_id == org.id,AnprDetection.is_deleted == False
            ).all()

            print(f"\nOrg [{org.id}] {org.name} (external_org_id={org.external_org_id}) — {len(detections)} detection(s)")

            for detection in detections:
                total_detections += 1
                prefix = f"  Detection [{detection.id}] camera={detection.camera_id}"

                if detection.sync_status == "synced" and not force:
                    print(f"{prefix} — SKIPPED (already synced)")
                    total_skipped += 1
                    continue

                if dry_run:
                    print(f"{prefix} — DRY RUN (would sync)")
                    total_synced += 1
                    continue

                try:
                    llm_note = "LLM skipped (no key)"

                    # Step 1 — Optional LLM
                    # Skip if numberplate data already exists (already processed)
                    already_processed = detection.processed_at is not None
                    if settings.GOOGLE_API_KEY and not already_processed:
                        try:
                            llm_note = run_llm(detection, db, det_repo)
                        except Exception as llm_err:
                            llm_note = f"LLM failed ({llm_err})"
                    elif already_processed:
                        plate = detection.numberplate_text if detection.numberplate_available else "none"
                        llm_note = f"LLM skipped (already processed, plate={plate})"

                    # Step 2 — Device (find or create)
                    cache_key = (org.id, detection.camera_id)
                    external_device_id = device_cache.get(cache_key) or detection.external_device_id

                    if not external_device_id:
                        device_name = detection.camera_name or detection.camera_id
                        external_device_id = sync_service.device.create(
                            name=device_name,
                            source=None,
                            frame_type=None,
                            status="active",
                            organization_id=org.external_org_id,
                        )
                    device_cache[cache_key] = external_device_id

                    # Step 3 — Image → base64
                    vehicle_image_b64 = get_image_b64(detection.image_path)

                    # Step 4 — Number plate
                    number_plate = get_number_plate(detection)

                    # Step 5 — Vehicle create on external
                    device_name = detection.camera_name or detection.camera_id
                    external_vehicle_id = sync_service.vehicle.create(
                        number_plate=number_plate,
                        vehicle_type=detection.vehicle_class,
                        device_name=device_name,
                        report_id=str(detection.id),
                        number_plate_image=vehicle_image_b64,
                        vehicle_image=vehicle_image_b64,
                        device_id=external_device_id,
                        organization_id=org.external_org_id,
                    )

                    # Step 6 — Save back
                    det_repo.update(detection.id, {
                        "external_device_id": external_device_id,
                        "external_vehicle_id": external_vehicle_id,
                        "sync_status": "synced",
                    })
                    db.commit()

                    print(f"{prefix} — {llm_note} — OK (vehicle={external_vehicle_id})")
                    total_synced += 1

                except Exception as e:
                    db.rollback()
                    print(f"{prefix} — FAILED: {e}")
                    total_failed += 1

        print(f"\nDone. orgs={total_orgs} detections={total_detections} "
              f"synced={total_synced} skipped={total_skipped} failed={total_failed}")

    finally:
        db.close()


if __name__ == "__main__":
    force = "--force" in sys.argv
    dry_run = "--dry-run" in sys.argv
    sync_detections(force=force, dry_run=dry_run)
