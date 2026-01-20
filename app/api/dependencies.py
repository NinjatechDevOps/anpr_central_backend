"""
API Dependencies - Authentication and authorization.
"""
from typing import Annotated, Optional
from fastapi import Depends, HTTPException, status, Header, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.repositories.organization_repository import OrganizationRepository
from app.models.organization import Organization


async def verify_org_token(
    x_api_token: Annotated[str, Header(description="Organization API token")],
    db: Session = Depends(get_db)
) -> Organization:
    """
    Verify organization API token from header.

    Args:
        x_api_token: API token from X-API-Token header
        db: Database session

    Returns:
        Organization object if token is valid

    Raises:
        HTTPException: If token is invalid or organization not found
    """
    if not x_api_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API token required in X-API-Token header"
        )

    org_repo = OrganizationRepository(db)
    organization = org_repo.get_by_token(x_api_token)

    if not organization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API token"
        )

    if not organization.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Organization is inactive"
        )

    return organization


async def verify_super_admin(
    x_api_token: Annotated[str, Header(description="Super admin API token")],
    db: Session = Depends(get_db)
) -> Organization:
    """
    Verify super admin API token from header.

    Args:
        x_api_token: API token from X-API-Token header
        db: Database session

    Returns:
        Organization object if token is valid and user is super admin

    Raises:
        HTTPException: If token is invalid or user is not super admin
    """
    # First verify the token is valid
    organization = await verify_org_token(x_api_token, db)

    # Check if user is super admin
    if not organization.is_super_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Super admin access required"
        )

    return organization


def get_org_filter(
    organization: Organization = Depends(verify_org_token),
    organization_id: Optional[int] = Query(
        None,
        description="Filter by organization ID (super admin only)"
    )
) -> Optional[int]:
    """
    Get organization filter for queries.

    - Regular users: Always filtered to their own org
    - Super admins: Can optionally filter by org_id, or see all if not specified

    Args:
        organization: Authenticated organization
        organization_id: Optional org ID filter (super admin only)

    Returns:
        Organization ID to filter by, or None for super admin viewing all

    Raises:
        HTTPException: If regular user tries to specify different org_id
    """
    if organization.is_super_admin:
        # Super admin can filter by any org or see all
        return organization_id
    else:
        # Regular user can only see their own data
        if organization_id is not None and organization_id != organization.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only access your own organization's data"
            )
        return organization.id
