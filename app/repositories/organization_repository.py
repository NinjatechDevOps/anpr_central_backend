"""
Organization repository - Database operations for Organization model.
"""
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models.organization import Organization
from app.models.anpr_detection import AnprDetection
from app.repositories.base_repository import BaseRepository


class OrganizationRepository(BaseRepository[Organization]):
    """Repository for Organization model."""

    def __init__(self, db: Session):
        super().__init__(Organization, db)

    def get_by_code(self, code: str) -> Optional[Organization]:
        """Get organization by code."""
        return self.db.query(Organization).filter(Organization.code == code).first()

    def get_by_name(self, name: str) -> Optional[Organization]:
        """Get organization by name."""
        return self.db.query(Organization).filter(Organization.name == name).first()

    def get_by_token(self, token: str) -> Optional[Organization]:
        """Get organization by API token."""
        return self.db.query(Organization).filter(Organization.token == token).first()

    def get_active(self, skip: int = 0, limit: int = 100) -> List[Organization]:
        """Get active organizations."""
        return self.db.query(Organization).filter(
            Organization.is_active == True
        ).order_by(Organization.id.desc()).offset(skip).limit(limit).all()

    def search(self, query: str, skip: int = 0, limit: int = 100) -> List[Organization]:
        """Search organizations by name or code."""
        search_pattern = f"%{query}%"
        return self.db.query(Organization).filter(
            (Organization.name.ilike(search_pattern)) |
            (Organization.code.ilike(search_pattern))
        ).order_by(Organization.id.desc()).offset(skip).limit(limit).all()

    def get_with_stats(self, org_id: int) -> Optional[dict]:
        """Get organization with camera and detection counts."""
        org = self.get_by_id(org_id)
        if org is None:
            return None

        # Count total detections for this organization
        detection_count = self.db.query(func.count(AnprDetection.id)).filter(
            AnprDetection.organization_id == org_id
        ).scalar()

        # Count distinct cameras based on camera_id from detections
        camera_count = self.db.query(func.count(func.distinct(AnprDetection.camera_id))).filter(
            AnprDetection.organization_id == org_id,
            AnprDetection.camera_id.isnot(None)
        ).scalar()

        return {
            "organization": org,
            "camera_count": camera_count or 0,
            "detection_count": detection_count or 0
        }

    def activate(self, org_id: int) -> Optional[Organization]:
        """Activate an organization."""
        return self.update(org_id, {"is_active": True})

    def deactivate(self, org_id: int) -> Optional[Organization]:
        """Deactivate an organization."""
        return self.update(org_id, {"is_active": False})
