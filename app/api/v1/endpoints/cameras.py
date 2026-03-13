"""
Camera API Endpoints - Query cameras derived from detection records.
"""
from typing import List, Optional
from pydantic import BaseModel, Field
from datetime import datetime
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.api.dependencies import get_org_filter
from app.repositories.anpr_repository import AnprDetectionRepository


class CameraResponse(BaseModel):
    """Response schema for a camera."""
    camera_id: str = Field(..., description="Camera ID")
    camera_name: str = Field(..., description="Camera name")
    organization_id: int = Field(..., description="Organization ID")
    organization_name: Optional[str] = Field(None, description="Organization name")
    detection_count: int = Field(..., description="Total detections from this camera")
    last_detection: Optional[datetime] = Field(None, description="Last detection timestamp")
    first_detection: Optional[datetime] = Field(None, description="First detection timestamp")


class CameraListResponse(BaseModel):
    """Paginated response for camera list."""
    cameras: List[CameraResponse] = Field(..., description="List of cameras")
    total: int = Field(..., description="Total number of cameras")


router = APIRouter()


@router.get(
    "/",
    response_model=CameraListResponse,
    summary="List all cameras",
    description="Get paginated list of cameras derived from detection records."
)
async def list_cameras(
    page: int = Query(1, ge=1, description="Page number (starts from 1)"),
    page_size: int = Query(100, ge=1, le=1000, description="Number of items per page"),
    org_filter: Optional[int] = Depends(get_org_filter),
    db: Session = Depends(get_db)
):
    """
    List cameras with detection counts.

    Cameras are derived from detection records (not a separate table).
    Regular users see only their organization's cameras.
    Super admins can see all or filter by organization.
    """
    skip = (page - 1) * page_size
    repo = AnprDetectionRepository(db)

    cameras_data = repo.get_distinct_cameras(
        organization_id=org_filter,
        skip=skip,
        limit=page_size
    )
    total = repo.count_distinct_cameras(organization_id=org_filter)

    # Fetch org names for each camera
    from app.repositories.organization_repository import OrganizationRepository
    org_repo = OrganizationRepository(db)
    org_cache = {}

    cameras = []
    for cam in cameras_data:
        org_id = cam['organization_id']
        if org_id not in org_cache:
            org = org_repo.get_by_id(org_id)
            org_cache[org_id] = org.name if org else None

        cameras.append(CameraResponse(
            camera_id=cam['camera_id'],
            camera_name=cam['camera_name'],
            organization_id=org_id,
            organization_name=org_cache[org_id],
            detection_count=cam['detection_count'],
            last_detection=cam['last_detection'],
            first_detection=cam['first_detection']
        ))

    return CameraListResponse(cameras=cameras, total=total)


@router.get(
    "/organization/{org_id}",
    response_model=CameraListResponse,
    summary="List cameras by organization",
    description="Get cameras for a specific organization."
)
async def list_cameras_by_organization(
    org_id: int,
    page: int = Query(1, ge=1, description="Page number (starts from 1)"),
    page_size: int = Query(100, ge=1, le=1000, description="Number of items per page"),
    db: Session = Depends(get_db)
):
    """Get cameras for a specific organization."""
    skip = (page - 1) * page_size
    repo = AnprDetectionRepository(db)

    cameras_data = repo.get_distinct_cameras(
        organization_id=org_id,
        skip=skip,
        limit=page_size
    )
    total = repo.count_distinct_cameras(organization_id=org_id)

    from app.repositories.organization_repository import OrganizationRepository
    org_repo = OrganizationRepository(db)
    org = org_repo.get_by_id(org_id)
    org_name = org.name if org else None

    cameras = [
        CameraResponse(
            camera_id=cam['camera_id'],
            camera_name=cam['camera_name'],
            organization_id=org_id,
            organization_name=org_name,
            detection_count=cam['detection_count'],
            last_detection=cam['last_detection'],
            first_detection=cam['first_detection']
        )
        for cam in cameras_data
    ]

    return CameraListResponse(cameras=cameras, total=total)
