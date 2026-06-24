"""
Script to export external sync status of all ANPR detections to a CSV file.

The CSV is written to the logs/ directory which is volume-mounted to the host,
so the file is immediately accessible outside Docker at ./logs/sync_status_<timestamp>.csv

Usage:
    Local:       python scripts/export_sync_status.py
    Custom file: python scripts/export_sync_status.py --output /app/logs/my_report.csv
    Synced only: python scripts/export_sync_status.py --synced-only
    Docker:      docker exec central-server-worker python scripts/export_sync_status.py
"""
import sys
import os
import csv
from datetime import datetime, timezone

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)
os.chdir(PROJECT_ROOT)

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(PROJECT_ROOT, ".env"), override=True)
except ImportError:
    pass

from sqlalchemy import case
from app.db.session import SessionLocal
from app.models.anpr_detection import AnprDetection
from app.models.organization import Organization

# logs/ is volume-mounted to the host (./logs:/app/logs in docker-compose.yml)
# so writing here makes the file accessible outside Docker automatically
EXPORT_DIR = os.path.join(PROJECT_ROOT, "logs")


def export_sync_status(output_path: str, synced_only: bool = False):
    db = SessionLocal()
    try:
        query = (
            db.query(
                Organization.name.label("org_name"),
                Organization.external_org_id.label("external_org_id"),
                AnprDetection.camera_id.label("camera_id"),
                AnprDetection.camera_name.label("camera_name"),
                AnprDetection.external_device_id.label("external_device_id"),
                AnprDetection.external_vehicle_id.label("external_vehicle_id"),
                # case(
                #     (AnprDetection.external_vehicle_id.isnot(None), "Synced"),
                #     else_="Not Synced"
                # ).label("sync_status"),
                case(AnprDetection.sync_status).label("sync_status"),
                AnprDetection.created_at.label("detection_created_at"),
                AnprDetection.processed_at.label("llm_processed_at"),
                AnprDetection.updated_at.label("last_updated_at"),
            )
            .join(Organization, Organization.id == AnprDetection.organization_id)
            .filter(
                Organization.is_active == True,
                Organization.is_super_admin == False,
                AnprDetection.is_deleted == False,
            )
        )

        if synced_only:
            query = query.filter(AnprDetection.external_vehicle_id.isnot(None))

        query = query.order_by(
            Organization.name,
            AnprDetection.camera_id,
            AnprDetection.created_at.desc()
        )

        rows = query.all()

        if not rows:
            print("No records found matching the filter.")
            return

        fieldnames = [
            "org_name",
            "external_org_id",
            "camera_id",
            "camera_name",
            "external_device_id",
            "external_vehicle_id",
            "sync_status",
            "detection_created_at",
            "llm_processed_at",
            "last_updated_at",
        ]

        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        with open(output_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for row in rows:
                writer.writerow({
                    "org_name":            row.org_name,
                    "external_org_id":     row.external_org_id or "",
                    "camera_id":           row.camera_id,
                    "camera_name":         row.camera_name or row.camera_id,
                    "external_device_id":  row.external_device_id or "",
                    "external_vehicle_id": row.external_vehicle_id or "",
                    "sync_status":         row.sync_status,
                    "detection_created_at": row.detection_created_at.strftime("%Y-%m-%d %H:%M:%S") if row.detection_created_at else "",
                    "llm_processed_at":    row.llm_processed_at.strftime("%Y-%m-%d %H:%M:%S") if row.llm_processed_at else "",
                    "last_updated_at":     row.last_updated_at.strftime("%Y-%m-%d %H:%M:%S") if row.last_updated_at else "",
                })

        synced_count = sum(1 for r in rows if r.external_vehicle_id)
        not_synced_count = len(rows) - synced_count

        print(f"\nExport complete → {output_path}")
        print(f"  Total records : {len(rows)}")
        print(f"  Synced        : {synced_count}")
        print(f"  Not Synced    : {not_synced_count}")
        print(f"\nFile is accessible on the host at: ./logs/{os.path.basename(output_path)}")

    finally:
        db.close()


if __name__ == "__main__":
    synced_only = "--synced-only" in sys.argv

    output_path = None
    if "--output" in sys.argv:
        idx = sys.argv.index("--output")
        try:
            output_path = sys.argv[idx + 1]
        except IndexError:
            print("Error: --output requires a file path, e.g. --output /app/logs/report.csv")
            sys.exit(1)

    if not output_path:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        output_path = os.path.join(EXPORT_DIR, f"sync_status_{timestamp}.csv")

    export_sync_status(output_path=output_path, synced_only=synced_only)
