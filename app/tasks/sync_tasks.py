"""
Celery tasks for syncing data to external ANPR server.
All external API calls go through these async tasks with 3 retries.
"""
from celery import Task
from sqlalchemy.orm import Session

from app.core.celery_app import celery_app
from app.core.logging import app_logger as logger
from app.db.session import SessionLocal
from app.services.external_sync_service import get_external_sync_service
from app.repositories.organization_repository import OrganizationRepository


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
