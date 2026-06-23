"""
Sync ALL detections for a specific organization (by ID) to the external ANPR server.

Always sends every detection regardless of sync_status (force mode).

Usage:
    python scripts/sync_org_detections.py --org-id 5
    python scripts/sync_org_detections.py --org-id 5 --dry-run
    python scripts/sync_org_detections.py --org-id 5 --skip-llm
"""
import sys
import os
import argparse
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


def get_image_b64(image_path: str):
    full_path = os.path.join(settings.UPLOAD_DIR, image_path)
    if not os.path.exists(full_path):
        return None
    with open(full_path, "rb") as f:
        raw_b64 = base64.b64encode(f.read()).decode("utf-8")
    ext = os.path.splitext(full_path)[1].lower()
    mime = "image/png" if ext == ".png" else "image/jpeg"
    return f"data:{mime};base64,{raw_b64}"


def get_number_plate(detection: AnprDetection) -> str:
    if (detection.numberplate_available
            and detection.numberplate_text
            and detection.numberplate_text != "N/A"):
        return detection.numberplate_text
    return ""


def run_llm(detection: AnprDetection, db, repo: AnprDetectionRepository) -> str:
    from app.services.llm_service import get_llm_service
    from datetime import datetime
    llm_service = get_llm_service()
    if not llm_service.validate_image(detection.image_path):
        return "LLM skipped (invalid image)"
    llm_result = llm_service.extract_numberplate(image_path=detection.image_path)
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


def sync_org_detections(org_id: int, dry_run: bool = False, skip_llm: bool = False):
    db = SessionLocal()
    try:
        sync_service = get_external_sync_service()
        if not sync_service.is_enabled:
            print("External sync is disabled (EXTERNAL_SYNC_ENABLED=false). Aborting.")
            return

        org_repo = OrganizationRepository(db)
        org = org_repo.get(org_id)
        if not org:
            print(f"ERROR: Organization with ID {org_id} not found.")
            sys.exit(1)
        if not org.is_active:
            print(f"ERROR: Organization '{org.name}' (ID={org_id}) is inactive/deleted.")
            sys.exit(1)
        if org.is_super_admin:
            print(f"ERROR: Organization '{org.name}' (ID={org_id}) is a super-admin org — skipping.")
            sys.exit(1)
        if not org.external_org_id:
            print(f"ERROR: Organization '{org.name}' (ID={org_id}) has no external_org_id. "
                  f"Run sync_orgs_to_external.py first.")
            sys.exit(1)

        det_repo = AnprDetectionRepository(db)
        detections = db.query(AnprDetection).filter(
            AnprDetection.organization_id == org_id,
            AnprDetection.is_deleted == False,
        ).all()

        print(f"\nOrg [{org.id}] {org.name} (external_org_id={org.external_org_id})")
        print(f"Total detections: {len(detections)}  (force-syncing ALL regardless of sync_status)\n")

        total = len(detections)
        synced = 0
        failed = 0
        device_cache: dict = {}

        for detection in detections:
            prefix = f"  Detection [{detection.id}] camera={detection.camera_id} status={detection.sync_status}"

            if dry_run:
                print(f"{prefix} — DRY RUN (would sync)")
                synced += 1
                continue

            try:
                llm_note = "LLM skipped (no key)"

                # Step 1 — Optional LLM
                if not skip_llm and settings.GOOGLE_API_KEY:
                    already_processed = detection.processed_at is not None
                    if already_processed:
                        plate = detection.numberplate_text if detection.numberplate_available else "none"
                        llm_note = f"LLM skipped (already processed, plate={plate})"
                    else:
                        try:
                            llm_note = run_llm(detection, db, det_repo)
                        except Exception as llm_err:
                            llm_note = f"LLM failed ({llm_err})"
                elif skip_llm:
                    llm_note = "LLM skipped (--skip-llm)"

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
                synced += 1

            except Exception as e:
                db.rollback()
                print(f"{prefix} — FAILED: {e}")
                failed += 1

        print(f"\nDone. total={total} synced={synced} failed={failed}")

    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Force-sync all detections for a specific organization by ID.")
    parser.add_argument("--org-id", type=int, required=True, help="Organization ID (numeric)")
    parser.add_argument("--dry-run", action="store_true", help="Print what would be synced without making changes")
    parser.add_argument("--skip-llm", action="store_true", help="Skip LLM numberplate extraction even if GOOGLE_API_KEY is set")
    args = parser.parse_args()

    sync_org_detections(org_id=args.org_id, dry_run=args.dry_run, skip_llm=args.skip_llm)
