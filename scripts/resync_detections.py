"""
Idempotent resync script — verifies each detection's external vehicle against the
external ANPR server before deciding to create.

For detections that already have an external_vehicle_id:
  - Calls GET /api/v1/vehicle/find-one/{id} first.
  - If vehicle EXISTS on external → skip entirely (no DB update, no status change).
  - If vehicle NOT FOUND (exception) → recreate it.

For detections without external_vehicle_id → create fresh.

Device handling:
  - If external_device_id is set → calls GET /api/v1/device/find-one/{id}.
      Found: reuse the existing device_id.
      Not found: create a new device.
  - If external_device_id not set → create device fresh.

sync_status is set to "resynced" ONLY when a vehicle is actually created/recreated.
Records that are found on the external server are left untouched.

Usage:
    python scripts/resync_detections.py
    python scripts/resync_detections.py --org-id 5
    python scripts/resync_detections.py --dry-run
    python scripts/resync_detections.py --org-id 5 --skip-llm
    docker exec central-server-worker python scripts/resync_detections.py
"""
import sys
import os
import argparse
import base64
import json as _json
from datetime import datetime, timezone

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)
os.chdir(PROJECT_ROOT)

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(PROJECT_ROOT, ".env"), override=True)
except ImportError:
    pass

import httpx
from loguru import logger

from app.db.session import SessionLocal
from app.models.anpr_detection import AnprDetection
from app.repositories.organization_repository import OrganizationRepository
from app.repositories.anpr_repository import AnprDetectionRepository
from app.services.external_sync_service import get_external_sync_service
from app.core.exceptions import ExternalSyncException
from app.core.config import settings


# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------

def setup_logger() -> str:
    """Configure loguru with console + per-run file sink. Returns the log file path."""
    os.makedirs(os.path.join(PROJECT_ROOT, "logs"), exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    log_path = os.path.join(PROJECT_ROOT, "logs", f"resync_detections_{timestamp}.log")

    logger.remove()
    logger.add(
        sys.stdout,
        format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | {message}",
        level="DEBUG",
        colorize=True,
    )
    logger.add(
        log_path,
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {message}",
        level="DEBUG",
        encoding="utf-8",
    )
    return log_path


# ---------------------------------------------------------------------------
# HTTP request/response logging hooks (attached to the httpx client)
# ---------------------------------------------------------------------------

_BASE64_FIELDS = {"numberPlateImage", "vehicleImage"}
_BODY_PREVIEW_LIMIT = 2000  # characters shown before truncation


def _truncate_body(raw: str) -> str:
    """Return body string with base64 image fields replaced and length capped."""
    try:
        parsed = _json.loads(raw)
        for field in _BASE64_FIELDS:
            val = parsed.get(field)
            if val and isinstance(val, str) and len(val) > 100:
                parsed[field] = f"<base64 {len(val)} chars>"
        text = _json.dumps(parsed, ensure_ascii=False)
    except Exception:
        text = raw
    if len(text) > _BODY_PREVIEW_LIMIT:
        text = text[:_BODY_PREVIEW_LIMIT] + f"... [+{len(text) - _BODY_PREVIEW_LIMIT} chars truncated]"
    return text


_HTTP_LINE = "─" * 68


def _http_request_hook(request: httpx.Request) -> None:
    try:
        raw_body = request.content.decode("utf-8", errors="replace")
        body_display = _truncate_body(raw_body) if raw_body.strip() else "<empty>"
    except Exception as e:
        body_display = f"<unreadable: {e}>"
    logger.debug(
        f"\n"
        f"  ┌─[ EXTERNAL SERVER REQUEST ]{_HTTP_LINE[:40]}\n"
        f"  │  Method  : {request.method}\n"
        f"  │  URL     : {request.url}\n"
        f"  │  Body    : {body_display}\n"
        f"  └{_HTTP_LINE[:42]}"
    )


def _http_response_hook(response: httpx.Response) -> None:
    try:
        response.read()  # force-read the body before the service method consumes it
        body_display = _truncate_body(response.text)
    except Exception as e:
        body_display = f"<unreadable: {e}>"
    ok = response.status_code < 400
    status_icon = "✓ OK" if ok else "✗ ERROR"
    logger.debug(
        f"\n"
        f"  ┌─[ EXTERNAL SERVER RESPONSE ]{_HTTP_LINE[:39]}\n"
        f"  │  Status  : {response.status_code} {status_icon}\n"
        f"  │  URL     : {response.url}\n"
        f"  │  Body    : {body_display}\n"
        f"  └{_HTTP_LINE[:42]}"
    )


def attach_http_logging(sync_service) -> None:
    """Attach request/response logging hooks to the shared httpx client."""
    client = sync_service._client
    client.event_hooks.setdefault("request", []).append(_http_request_hook)
    client.event_hooks.setdefault("response", []).append(_http_response_hook)
    logger.debug("HTTP request/response logging hooks attached.")


# ---------------------------------------------------------------------------
# Helpers (same logic as sync_detections_to_external.py)
# ---------------------------------------------------------------------------

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
    """Extract number plate string from detection."""
    # if (
    #     detection.numberplate_available
    #     and detection.numberplate_text
    #     and detection.numberplate_text != "N/A"
    # ):
    #     return detection.numberplate_text
    return detection.numberplate_text


def run_llm(detection: AnprDetection, db, repo: AnprDetectionRepository) -> str:
    """Run LLM extraction and update DB. Returns log message."""
    from app.services.llm_service import get_llm_service
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


# ---------------------------------------------------------------------------
# Core resync
# ---------------------------------------------------------------------------

def resync_detections(org_id: int = None, dry_run: bool = False, skip_llm: bool = False):
    log_path = setup_logger()

    logger.info("=" * 72)
    logger.info("ANPR Central — Resync Detections")
    logger.info(f"dry_run={dry_run}  skip_llm={skip_llm}  org_id={org_id or 'ALL'}")
    logger.info("=" * 72)

    db = SessionLocal()
    try:
        sync_service = get_external_sync_service()
        if not sync_service.is_enabled:
            logger.error("External sync is disabled (EXTERNAL_SYNC_ENABLED=false). Aborting.")
            return

        attach_http_logging(sync_service)

        org_repo = OrganizationRepository(db)

        if org_id:
            org = org_repo.get(org_id)
            orgs = [org] if org else []
        else:
            orgs = org_repo.get_all(skip=0, limit=10000)

        # Counters
        total_orgs = 0
        total_detections = 0
        count_found_on_external = 0   # vehicle GET succeeded with data → skipped
        count_recreated = 0           # vehicle GET failed or data null → recreated
        count_created_fresh = 0       # no external_vehicle_id → created new
        count_failed = 0

        for org in orgs:
            if not org:
                logger.error(f"Organization ID {org_id} not found.")
                sys.exit(1)

            if not org.is_active:
                logger.warning(f"Org [{org.id}] {org.name} — SKIPPED (inactive/deleted)")
                continue
            if org.is_super_admin:
                logger.debug(f"Org [{org.id}] {org.name} — SKIPPED (super admin)")
                continue
            if not org.external_org_id:
                logger.warning(
                    f"Org [{org.id}] {org.name} — SKIPPED (no external_org_id, "
                    f"run sync_orgs_to_external.py first)"
                )
                continue

            total_orgs += 1
            detections = (
                db.query(AnprDetection)
                .filter(
                    AnprDetection.organization_id == org.id,
                    AnprDetection.is_deleted == False,
                )
                .all()
            )

            logger.info("")
            logger.info(
                f"┌── Org [{org.id}] {org.name}  "
                f"(external_org_id={org.external_org_id})  "
                f"— {len(detections)} detection(s)"
            )

            det_total = len(detections)

            # ------------------------------------------------------------------
            # Resolve the single device ID for this entire org before looping.
            # Priority: DB (any detection that already has one) → verify on
            # external → create once if nothing exists.
            # ------------------------------------------------------------------
            org_device_id = None
            existing_device = (
                db.query(AnprDetection.external_device_id)
                .filter(
                    AnprDetection.organization_id == org.id,
                    AnprDetection.external_device_id.isnot(None),
                )
                .limit(1)
                .scalar()
            )
            if existing_device:
                logger.info(
                    f"│  [device] Found existing device in DB: {existing_device}. "
                    f"Verifying on external server..."
                )
                try:
                    sync_service.device.find_one(existing_device)
                    org_device_id = existing_device
                    logger.info(f"│  [device] Confirmed on external. Will reuse for all detections.")
                except ExternalSyncException as _dev_err:
                    logger.warning(
                        f"│  [device] Not found on external ({_dev_err}). "
                        f"Will create a new device on first detection."
                    )
            else:
                logger.info(
                    f"│  [device] No existing device for org. "
                    f"Will create one on first detection."
                )

            for det_idx, detection in enumerate(detections, start=1):
                total_detections += 1
                rec_title = f"  STARTING RECORD  #{det_idx} / {det_total}  "
                rec_line = "═" * max(58, len(rec_title) + 4)
                logger.info(f"│")
                logger.info(f"│  ╔{rec_line}╗")
                logger.info(f"│  ║{rec_title.center(len(rec_line))}║")
                logger.info(f"│  ╠{rec_line}╣")
                logger.info(f"│  ║  Detection ID       : {detection.id:<38}║")
                logger.info(f"│  ║  Camera             : {str(detection.camera_id):<38}║")
                logger.info(f"│  ║  Activity           : {str(detection.activity_type or 'n/a'):<38}║")
                logger.info(f"│  ║  Vehicle Class      : {str(detection.vehicle_class or 'n/a'):<38}║")
                logger.info(f"│  ║  Sync Status        : {str(detection.sync_status or 'none'):<38}║")
                logger.info(f"│  ║  Org (external_id)  : {str(org.external_org_id):<38}║")
                logger.info(f"│  ║  Device (external)  : {str(detection.external_device_id or 'none'):<38}║")
                logger.info(f"│  ║  Vehicle (external) : {str(detection.external_vehicle_id or 'none'):<38}║")
                logger.info(f"│  ╚{rec_line}╝")

                try:
                    # ----------------------------------------------------------
                    # Step 1 — Check if vehicle already exists on external server
                    # ----------------------------------------------------------
                    if detection.external_vehicle_id:
                        logger.info(
                            f"│    [1] Has external_vehicle_id={detection.external_vehicle_id}. "
                            f"Calling find_one on external server..."
                        )
                        try:
                            vehicle_data = sync_service.vehicle.find_one(
                                detection.external_vehicle_id
                            )

                            # Unwrap nested {"data": {...}} or use flat response directly
                            actual_vehicle = (
                                vehicle_data.get("data", vehicle_data)
                                if isinstance(vehicle_data, dict) else None
                            )

                            if not actual_vehicle or not actual_vehicle.get("id"):
                                # 200 but data is null — treat as missing, fall through
                                # to the create flow below (same as a 404).
                                logger.warning(
                                    f"│    [1] Vehicle FOUND (200) but data is NULL. "
                                    f"Treating as missing — will create fresh."
                                )

                            else:
                                # 200 with valid data — nothing to do
                                logger.info(
                                    f"│    [1] Vehicle FOUND with data. "
                                    f"Skipping — no action needed."
                                )
                                count_found_on_external += 1
                                continue

                        except ExternalSyncException as e:
                            logger.warning(
                                f"│    [1] Vehicle NOT FOUND on external server "
                                f"(error: {e}). Will recreate."
                            )
                            # Fall through to create flow below
                    else:
                        logger.info(
                            f"│    [1] No external_vehicle_id stored. Will create fresh."
                        )

                    if dry_run:
                        logger.info(f"│    DRY RUN — would create vehicle. Skipping.")
                        if detection.external_vehicle_id:
                            count_recreated += 1
                        else:
                            count_created_fresh += 1
                        continue

                    # ----------------------------------------------------------
                    # Step 2 — Get or create the single device for this org.
                    # One device per org — resolved once before the loop and
                    # reused for every detection. Create only if still missing.
                    # ----------------------------------------------------------
                    if org_device_id:
                        external_device_id = org_device_id
                        logger.info(
                            f"│    [2] Reusing org device: {external_device_id}"
                        )
                    else:
                        device_name = org.name
                        logger.info(
                            f"│    [2] No device for org yet. Creating device '{device_name}'..."
                        )
                        external_device_id = sync_service.device.create(
                            name=device_name,
                            source=None,
                            frame_type=None,
                            status="active",
                            organization_id=org.external_org_id,
                        )
                        org_device_id = external_device_id
                        logger.info(
                            f"│    [2] Device created: {external_device_id}. "
                            f"Will reuse for remaining detections of this org."
                        )

                    # ----------------------------------------------------------
                    # Step 3 — Optional LLM
                    # ----------------------------------------------------------
                    llm_note = "LLM skipped (no key)"
                    if not skip_llm and settings.GOOGLE_API_KEY:
                        already_processed = detection.processed_at is not None
                        if already_processed:
                            plate = detection.numberplate_text if detection.numberplate_available else "none"
                            llm_note = f"LLM skipped (already processed, plate={plate})"
                        else:
                            try:
                                llm_note = run_llm(detection, db, AnprDetectionRepository(db))
                            except Exception as llm_err:
                                llm_note = f"LLM failed ({llm_err})"
                    elif skip_llm:
                        llm_note = "LLM skipped (--skip-llm)"

                    logger.info(f"│    [3] {llm_note}")

                    # ----------------------------------------------------------
                    # Step 4 — Load image
                    # ----------------------------------------------------------
                    vehicle_image_b64 = get_image_b64(detection.image_path)
                    if vehicle_image_b64:
                        logger.info(f"│    [4] Image loaded (path={detection.image_path})")
                    else:
                        logger.warning(
                            f"│    [4] Image missing (path={detection.image_path}). "
                            f"Proceeding without image."
                        )

                    # ----------------------------------------------------------
                    # Step 5 — Create vehicle on external server
                    # ----------------------------------------------------------
                    number_plate = get_number_plate(detection)
                    device_name = detection.camera_name or detection.camera_id

                    logger.info(
                        f"│    [5] Creating vehicle on external "
                        f"(plate='{number_plate or 'none'}', "
                        f"device_id={external_device_id})..."
                    )
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
                    logger.info(
                        f"│    [5] Vehicle created: external_vehicle_id={external_vehicle_id}"
                    )

                    # ----------------------------------------------------------
                    # Step 6 — Save back to DB, set sync_status="resynced"
                    # ----------------------------------------------------------
                    AnprDetectionRepository(db).update(detection.id, {
                        "external_device_id": external_device_id,
                        "external_vehicle_id": external_vehicle_id,
                        "sync_status": "resynced",
                    })
                    db.commit()
                    logger.info(
                        f"│    [6] DB updated — sync_status=resynced, "
                        f"external_vehicle_id={external_vehicle_id}"
                    )

                    if detection.external_vehicle_id:
                        # Had an old (now invalid) vehicle_id — this is a recreate
                        count_recreated += 1
                    else:
                        count_created_fresh += 1

                except Exception as e:
                    db.rollback()
                    logger.error(
                        f"│    FAILED — detection [{detection.id}]: {e}"
                    )
                    count_failed += 1

            logger.info(f"└── Org [{org.id}] {org.name} done")

        # ------------------------------------------------------------------
        # Summary
        # ------------------------------------------------------------------
        logger.info("")
        logger.info("=" * 72)
        logger.info("RESYNC SUMMARY")
        logger.info("=" * 72)
        logger.info(f"  Orgs processed             : {total_orgs}")
        logger.info(f"  Total detections            : {total_detections}")
        logger.info(f"  Found on external (skipped) : {count_found_on_external}")
        logger.info(f"  Recreated (missing/null)    : {count_recreated}")
        logger.info(f"  Created fresh (no prior id) : {count_created_fresh}")
        logger.info(f"  Failed                      : {count_failed}")
        logger.info(f"  Log file                    : {log_path}")
        logger.info("=" * 72)

    finally:
        db.close()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description=(
            "Idempotent resync: checks each detection's vehicle on the external server "
            "via GET before creating. Only creates if vehicle is missing externally."
        )
    )
    parser.add_argument(
        "--org-id", type=int, default=None,
        help="Restrict resync to a single organization (numeric ID). Omit to process all orgs."
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Print what would happen without making any changes."
    )
    parser.add_argument(
        "--skip-llm", action="store_true",
        help="Skip LLM numberplate extraction even if GOOGLE_API_KEY is set."
    )
    args = parser.parse_args()

    resync_detections(org_id=args.org_id, dry_run=args.dry_run, skip_llm=args.skip_llm)
