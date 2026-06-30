"""
Public (unauthenticated) endpoints to trigger and monitor date-range bulk syncs
of detections to the external ANPR server.

Only one job runs at a time, so callers do not track a job id — they ask for the
"current" job. Every run is recorded in the sync_jobs table, including the
caller's IP, for auditability.
"""
from fastapi import APIRouter, Depends, HTTPException, Request, status, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.repositories.sync_job_repository import SyncJobRepository
from app.repositories.sync_job_log_repository import SyncJobLogRepository
from app.schemas.sync_job_schemas import (
    SyncJobCreateRequest,
    SyncJobResponse,
    SyncJobListResponse,
    SyncJobLogResponse,
    SyncJobLogListResponse,
)
from app.tasks.bulk_sync_tasks import bulk_sync_detections_by_range
from app.core.logging import app_logger as logger

router = APIRouter()


def get_client_ip(request: Request) -> str:
    """Best-effort client IP: first X-Forwarded-For hop, else the socket peer."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


@router.post(
    "/",
    response_model=SyncJobResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Start a date-range bulk sync (public)",
    description="Sync all detections received in [from_datetime, to_datetime] to the external server. Only one job may run at a time.",
)
async def start_sync_job(
    body: SyncJobCreateRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    repo = SyncJobRepository(db)

    # Only one active job at a time
    active = repo.get_active_job()
    if active:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"A sync job is already {active.status} (id={active.id}). Wait for it to finish or cancel it.",
        )

    ip = get_client_ip(request)
    job = repo.create({
        "ip": ip,
        "from_datetime": body.from_datetime,
        "to_datetime": body.to_datetime,
        "status": "pending",
    })

    # Queue the task, then record its id on the row
    async_result = bulk_sync_detections_by_range.apply_async(
        args=[job.id],
        queue="bulk_sync",
    )
    job = repo.update(job.id, {"celery_task_id": async_result.id})

    logger.info(
        f"[sync-jobs] started job {job.id} ip={ip} task={async_result.id} "
        f"range=[{body.from_datetime} .. {body.to_datetime}]"
    )
    return SyncJobResponse.from_job(job)


@router.get(
    "/current",
    response_model=SyncJobResponse,
    summary="Get the current/latest sync job (public)",
    description="Returns the active job if one exists, otherwise the most recent job. Poll this for live progress.",
)
async def get_current_sync_job(db: Session = Depends(get_db)):
    repo = SyncJobRepository(db)
    job = repo.get_current()
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No sync job has been run yet.",
        )
    has_logs = SyncJobLogRepository(db).has_logs_for_job(job.id)
    return SyncJobResponse.from_job(job, has_logs=has_logs)


@router.post(
    "/cancel",
    response_model=SyncJobResponse,
    summary="Cancel the active sync job (public)",
    description="Requests cooperative cancellation of the running job. It stops at the next record boundary.",
)
async def cancel_sync_job(db: Session = Depends(get_db)):
    repo = SyncJobRepository(db)
    job = repo.get_active_job()
    if not job:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No active sync job to cancel.",
        )

    # Deschedule any pending retries / queued run, then flag for cooperative stop
    if job.celery_task_id:
        try:
            from app.core.celery_app import celery_app
            celery_app.control.revoke(job.celery_task_id)
        except Exception as e:
            logger.warning(f"[sync-jobs] revoke failed for task {job.celery_task_id}: {e}")

    job = repo.update(job.id, {"status": "cancelling"})
    logger.info(f"[sync-jobs] cancellation requested for job {job.id}")
    return SyncJobResponse.from_job(job)


@router.get(
    "/",
    response_model=SyncJobListResponse,
    summary="List recent sync jobs (public)",
    description="Paginated history of sync jobs, newest first.",
)
async def list_sync_jobs(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
):
    repo = SyncJobRepository(db)
    skip = (page - 1) * page_size
    jobs = repo.list_recent(skip=skip, limit=page_size)
    total = repo.count()
    job_ids = [j.id for j in jobs]
    jobs_with_logs = SyncJobLogRepository(db).get_job_ids_with_logs(job_ids)
    return SyncJobListResponse(
        jobs=[SyncJobResponse.from_job(j, has_logs=(j.id in jobs_with_logs)) for j in jobs],
        total=total,
    )


@router.get(
    "/{job_id}/logs",
    response_model=SyncJobLogListResponse,
    summary="List log entries for a sync job (public)",
    description="Paginated per-detection audit log for a bulk sync job. Default page size is 10.",
)
async def list_sync_job_logs(
    job_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db),
):
    job_repo = SyncJobRepository(db)
    if not job_repo.get_by_id(job_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Sync job {job_id} not found.",
        )
    log_repo = SyncJobLogRepository(db)
    skip = (page - 1) * page_size
    rows = log_repo.get_by_job(job_id, skip=skip, limit=page_size)
    total = log_repo.count_by_job(job_id)
    return SyncJobLogListResponse(
        logs=[SyncJobLogResponse.from_log(log, organization_name=org_name) for log, org_name in rows],
        total=total,
    )
