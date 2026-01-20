"""
Organization Service - Business logic for organization management.
"""
import secrets
from typing import List, Optional
from sqlalchemy.orm import Session

from app.repositories.organization_repository import OrganizationRepository
from app.schemas.organization import (
    OrganizationCreate,
    OrganizationUpdate,
    OrganizationResponse,
    OrganizationListResponse
)
from app.core.logging import app_logger as logger
from app.core.exceptions import DuplicateException, NotFoundException


class OrganizationService:
    """Service for organization business logic."""

    def __init__(self, db: Session):
        self.db = db
        self.repo = OrganizationRepository(db)

    def _generate_token(self) -> str:
        """Generate a unique API token for organization."""
        return secrets.token_hex(32)  # 64 character hex string

    def create_organization(self, data: OrganizationCreate) -> OrganizationResponse:
        """Create a new organization with auto-generated token."""
        # Check if code already exists
        existing = self.repo.get_by_code(data.code)
        if existing:
            raise DuplicateException("Organization", "code", data.code)

        org_dict = data.model_dump()
        # Generate unique token for the organization
        org_dict['token'] = self._generate_token()
        org = self.repo.create(org_dict)

        logger.info(f"Organization created: {org.id} - {org.name} with token")
        return self._to_response(org)

    def regenerate_token(self, org_id: int) -> OrganizationResponse:
        """Regenerate API token for an organization."""
        org = self.repo.get_by_id(org_id)
        if org is None:
            raise NotFoundException("Organization", org_id)

        new_token = self._generate_token()
        org = self.repo.update(org_id, {'token': new_token})

        logger.info(f"Token regenerated for organization: {org_id}")
        return self._to_response(org)

    def get_organization(self, org_id: int) -> OrganizationResponse:
        """Get organization by ID."""
        result = self.repo.get_with_stats(org_id)
        if result is None:
            raise NotFoundException("Organization", org_id)

        return self._to_response(
            result["organization"],
            camera_count=result["camera_count"],
            detection_count=result["detection_count"]
        )

    def get_all_organizations(self, skip: int = 0, limit: int = 100) -> OrganizationListResponse:
        """Get all organizations with pagination."""
        organizations = self.repo.get_all(skip=skip, limit=limit)
        total = self.repo.count()

        return OrganizationListResponse(
            organizations=[self._to_response(org) for org in organizations],
            total=total
        )

    def update_organization(self, org_id: int, data: OrganizationUpdate) -> OrganizationResponse:
        """Update an organization."""
        update_dict = data.model_dump(exclude_unset=True)
        if not update_dict:
            result = self.repo.get_with_stats(org_id)
            if result is None:
                raise NotFoundException("Organization", org_id)
            return self._to_response(result["organization"])

        org = self.repo.update(org_id, update_dict)
        if org is None:
            raise NotFoundException("Organization", org_id)

        logger.info(f"Organization updated: {org_id}")
        return self._to_response(org)

    def delete_organization(self, org_id: int) -> bool:
        """Delete an organization."""
        success = self.repo.delete(org_id)
        if not success:
            raise NotFoundException("Organization", org_id)

        logger.info(f"Organization deleted: {org_id}")
        return True

    def search_organizations(self, query: str, skip: int = 0, limit: int = 100) -> OrganizationListResponse:
        """Search organizations."""
        organizations = self.repo.search(query, skip=skip, limit=limit)
        return OrganizationListResponse(
            organizations=[self._to_response(org) for org in organizations],
            total=len(organizations)
        )

    def _to_response(
        self,
        org,
        camera_count: int = 0,
        detection_count: int = 0
    ) -> OrganizationResponse:
        """Convert organization model to response."""
        return OrganizationResponse(
            id=org.id,
            name=org.name,
            code=org.code,
            location=org.location,
            description=org.description,
            token=org.token,
            email=org.email,
            phone=org.phone,
            address=org.address,
            is_active=org.is_active,
            is_super_admin=org.is_super_admin,
            camera_count=camera_count,
            detection_count=detection_count,
            created_at=org.created_at,
            updated_at=org.updated_at
        )
