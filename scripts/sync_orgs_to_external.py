"""
Script to sync all organizations from the central DB to the external ANPR server.
Saves the returned external org ID back into each organization record.

Usage:
    Local:     python scripts/sync_orgs_to_external.py
    Dry run:   python scripts/sync_orgs_to_external.py --dry-run
    Force:     python scripts/sync_orgs_to_external.py --force
    Docker:    docker exec vehicle-detection-api python scripts/sync_orgs_to_external.py
"""
import sys
import os

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)
os.chdir(PROJECT_ROOT)

# Load .env explicitly so pydantic-settings picks up the values even when
# the shell environment has empty overrides for these variables.
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(PROJECT_ROOT, ".env"), override=True)
except ImportError:
    pass  # python-dotenv not installed; rely on pydantic-settings env_file fallback

from app.db.session import SessionLocal
from app.repositories.organization_repository import OrganizationRepository
from app.services.external_sync_service import get_external_sync_service


def sync_orgs(force: bool = False, dry_run: bool = False):
    db = SessionLocal()
    try:
        repo = OrganizationRepository(db)
        orgs = repo.get_all(skip=0, limit=10000)

        sync_service = get_external_sync_service()
        if not sync_service.is_enabled:
            print("External sync is disabled (EXTERNAL_SYNC_ENABLED=false). Aborting.")
            return

        total = len(orgs)
        synced = 0
        skipped = 0
        failed = 0

        print(f"Found {total} organization(s). dry_run={dry_run}, force={force}\n")

        for org in orgs:
            prefix = f"  [{org.id}] {org.name}"

            if org.is_super_admin:
                print(f"{prefix} — SKIPPED (super admin)")
                skipped += 1
                continue

            if org.external_org_id and not force:
                print(f"{prefix} — SKIPPED (already synced: external_org_id={org.external_org_id})")
                skipped += 1
                continue

            if dry_run:
                print(f"{prefix} — DRY RUN (would sync)")
                synced += 1
                continue

            try:
                ext_id = sync_service.organization.create(
                    name=org.name,
                    password=org.token[:20],
                    role="admin",
                )
                repo.update(org.id, {"external_org_id": ext_id})
                db.commit()
                print(f"{prefix} — OK (external_org_id={ext_id})")
                synced += 1
            except Exception as e:
                db.rollback()
                print(f"{prefix} — FAILED: {e}")
                failed += 1

        print(f"\nDone. total={total} synced={synced} skipped={skipped} failed={failed}")

    finally:
        db.close()


if __name__ == "__main__":
    force = "--force" in sys.argv
    dry_run = "--dry-run" in sys.argv
    sync_orgs(force=force, dry_run=dry_run)
