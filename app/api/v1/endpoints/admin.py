"""
Admin API Endpoints - Super admin operations.
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.api.dependencies import verify_super_admin
from app.models.organization import Organization
from app.repositories.organization_repository import OrganizationRepository
from app.repositories.anpr_repository import AnprDetectionRepository
from pydantic import BaseModel
from datetime import datetime, timedelta

router = APIRouter()


class OrganizationStatsResponse(BaseModel):
    """Organization with statistics."""
    id: int
    name: str
    code: str
    is_super_admin: bool
    is_active: bool
    camera_count: int
    detection_count: int
    created_at: datetime
    updated_at: datetime


class AllOrganizationsResponse(BaseModel):
    """Response with all organizations and their stats."""
    total_organizations: int
    organizations: List[OrganizationStatsResponse]


@router.get(
    "/organizations",
    response_model=AllOrganizationsResponse,
    summary="Get all organizations (Super Admin)",
    description="Get list of all organizations with statistics. Requires super admin access."
)
async def get_all_organizations(
    skip: int = 0,
    limit: int = 100,
    organization: Organization = Depends(verify_super_admin),
    db: Session = Depends(get_db)
):
    """
    Get all organizations with statistics.

    Requires:
    - X-API-Token header with super admin token

    Query parameters:
    - skip: Number of records to skip (pagination)
    - limit: Maximum records to return (max 100)

    Returns list of all organizations with camera and detection counts.
    """
    if limit > 100:
        limit = 100

    org_repo = OrganizationRepository(db)
    organizations = org_repo.get_all(skip=skip, limit=limit)

    org_stats_list = []
    for org in organizations:
        stats = org_repo.get_with_stats(org.id)
        org_stats_list.append(
            OrganizationStatsResponse(
                id=org.id,
                name=org.name,
                code=org.code,
                is_super_admin=org.is_super_admin,
                is_active=org.is_active,
                camera_count=stats["camera_count"],
                detection_count=stats["detection_count"],
                created_at=org.created_at,
                updated_at=org.updated_at
            )
        )

    total = org_repo.count()

    return AllOrganizationsResponse(
        total_organizations=total,
        organizations=org_stats_list
    )


@router.get(
    "/organizations/{org_id}/stats",
    response_model=OrganizationStatsResponse,
    summary="Get organization statistics (Super Admin)",
    description="Get detailed statistics for a specific organization. Requires super admin access."
)
async def get_organization_stats(
    org_id: int,
    organization: Organization = Depends(verify_super_admin),
    db: Session = Depends(get_db)
):
    """
    Get statistics for a specific organization.

    Requires:
    - X-API-Token header with super admin token

    Returns organization details with statistics.
    """
    org_repo = OrganizationRepository(db)
    org = org_repo.get_by_id(org_id)

    if not org:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Organization {org_id} not found"
        )

    stats = org_repo.get_with_stats(org_id)

    return OrganizationStatsResponse(
        id=org.id,
        name=org.name,
        code=org.code,
        is_super_admin=org.is_super_admin,
        is_active=org.is_active,
        camera_count=stats["camera_count"],
        detection_count=stats["detection_count"],
        created_at=org.created_at,
        updated_at=org.updated_at
    )


class SystemStatsResponse(BaseModel):
    """System-wide statistics."""
    total_organizations: int
    active_organizations: int
    total_detections: int
    pending_detections: int
    processing_detections: int
    success_detections: int
    failed_detections: int
    total_cameras: int
    total_in: int
    total_out: int
    active_occupancy: int


@router.get(
    "/stats",
    response_model=SystemStatsResponse,
    summary="Get system statistics (Super Admin)",
    description="Get system-wide statistics across all organizations. Requires super admin access."
)
async def get_system_stats(
    date_filter: Optional[str] = Query("today", description="Date filter: today, yesterday, this_week, this_month, all_time"),
    organization: Organization = Depends(verify_super_admin),
    db: Session = Depends(get_db)
):
    """
    Get system-wide statistics.

    Requires:
    - X-API-Token header with super admin token

    Query parameters:
    - date_filter: Filter by date range (today, yesterday, this_week, this_month, all_time)

    Returns aggregated statistics across all organizations.
    """
    org_repo = OrganizationRepository(db)
    detection_repo = AnprDetectionRepository(db)

    # Calculate date range
    from sqlalchemy import func, case
    from app.models.anpr_detection import AnprDetection, ProcessingStatus

    now = datetime.utcnow()
    start_date = None

    if date_filter == "today":
        start_date = datetime(now.year, now.month, now.day)
    elif date_filter == "yesterday":
        yesterday = now - timedelta(days=1)
        start_date = datetime(yesterday.year, yesterday.month, yesterday.day)
        end_date = datetime(now.year, now.month, now.day)
    elif date_filter == "this_week":
        start_date = now - timedelta(days=now.weekday())
        start_date = datetime(start_date.year, start_date.month, start_date.day)
    elif date_filter == "this_month":
        start_date = datetime(now.year, now.month, 1)
    # For all_time, start_date remains None

    # Get organization counts
    total_orgs = org_repo.count()
    active_orgs = len(org_repo.get_active())

    # Base query for detections
    query = db.query(
        func.count(AnprDetection.id).label('total'),
        func.sum(case((AnprDetection.status == ProcessingStatus.PENDING, 1), else_=0)).label('pending'),
        func.sum(case((AnprDetection.status == ProcessingStatus.PROCESSING, 1), else_=0)).label('processing'),
        func.sum(case((AnprDetection.status == ProcessingStatus.SUCCESS, 1), else_=0)).label('success'),
        func.sum(case((AnprDetection.status == ProcessingStatus.FAILED, 1), else_=0)).label('failed'),
        func.sum(case((AnprDetection.activity_type == 'in', 1), else_=0)).label('total_in'),
        func.sum(case((AnprDetection.activity_type == 'out', 1), else_=0)).label('total_out')
    )

    # Apply date filter
    if start_date:
        query = query.filter(AnprDetection.created_at >= start_date)
        if date_filter == "yesterday":
            query = query.filter(AnprDetection.created_at < end_date)

    result = query.first()

    # Get total unique cameras
    camera_query = db.query(func.count(func.distinct(AnprDetection.camera_id)))
    if start_date:
        camera_query = camera_query.filter(AnprDetection.created_at >= start_date)
        if date_filter == "yesterday":
            camera_query = camera_query.filter(AnprDetection.created_at < end_date)

    total_cameras = camera_query.filter(AnprDetection.camera_id.isnot(None)).scalar() or 0

    # Calculate active occupancy (in - out)
    total_in = result.total_in or 0
    total_out = result.total_out or 0
    active_occupancy = max(0, total_in - total_out)

    return SystemStatsResponse(
        total_organizations=total_orgs,
        active_organizations=active_orgs,
        total_detections=result.total or 0,
        pending_detections=result.pending or 0,
        processing_detections=result.processing or 0,
        success_detections=result.success or 0,
        failed_detections=result.failed or 0,
        total_cameras=total_cameras,
        total_in=total_in,
        total_out=total_out,
        active_occupancy=active_occupancy
    )
