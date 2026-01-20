"""
Organization API endpoints.
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.organization_service import OrganizationService
from app.schemas.organization import (
    OrganizationCreate,
    OrganizationUpdate,
    OrganizationResponse,
    OrganizationListResponse
)
from app.core.exceptions import AppException

router = APIRouter()


@router.post(
    "/",
    response_model=OrganizationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create organization"
)
def create_organization(
    data: OrganizationCreate,
    db: Session = Depends(get_db)
):
    """Create a new organization."""
    service = OrganizationService(db)
    try:
        return service.create_organization(data)
    except AppException as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)


@router.get(
    "/",
    response_model=OrganizationListResponse,
    summary="Get all organizations"
)
def get_organizations(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db)
):
    """Get all organizations with pagination."""
    service = OrganizationService(db)
    return service.get_all_organizations(skip=skip, limit=limit)


@router.get(
    "/search",
    response_model=OrganizationListResponse,
    summary="Search organizations"
)
def search_organizations(
    q: str = Query(..., min_length=1),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db)
):
    """Search organizations by name or code."""
    service = OrganizationService(db)
    return service.search_organizations(q, skip=skip, limit=limit)


@router.get(
    "/{org_id}",
    response_model=OrganizationResponse,
    summary="Get organization by ID"
)
def get_organization(
    org_id: int,
    db: Session = Depends(get_db)
):
    """Get organization details."""
    service = OrganizationService(db)
    try:
        return service.get_organization(org_id)
    except AppException as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)


@router.put(
    "/{org_id}",
    response_model=OrganizationResponse,
    summary="Update organization"
)
def update_organization(
    org_id: int,
    data: OrganizationUpdate,
    db: Session = Depends(get_db)
):
    """Update an organization."""
    service = OrganizationService(db)
    try:
        return service.update_organization(org_id, data)
    except AppException as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)


@router.delete(
    "/{org_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete organization"
)
def delete_organization(
    org_id: int,
    db: Session = Depends(get_db)
):
    """Delete an organization."""
    service = OrganizationService(db)
    try:
        service.delete_organization(org_id)
    except AppException as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)


@router.post(
    "/{org_id}/regenerate-token",
    response_model=OrganizationResponse,
    summary="Regenerate organization token"
)
def regenerate_token(
    org_id: int,
    db: Session = Depends(get_db)
):
    """Regenerate API token for an organization."""
    service = OrganizationService(db)
    try:
        return service.regenerate_token(org_id)
    except AppException as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)
