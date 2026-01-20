"""
Organization schemas for request/response validation.
"""
from typing import Optional, List
from pydantic import Field, EmailStr

from app.schemas.base import BaseSchema, ResponseSchema


class OrganizationBase(BaseSchema):
    """Base organization schema."""

    name: str = Field(..., min_length=1, max_length=255, description="Organization name")
    code: str = Field(..., min_length=1, max_length=50, description="Unique organization code")
    location: Optional[str] = Field(None, max_length=255, description="Organization location")
    description: Optional[str] = Field(None, description="Organization description")
    email: Optional[EmailStr] = Field(None, description="Contact email")
    phone: Optional[str] = Field(None, max_length=50, description="Contact phone")
    address: Optional[str] = Field(None, description="Address")


class OrganizationCreate(OrganizationBase):
    """Schema for creating an organization."""

    is_active: bool = Field(default=True, description="Active status")


class OrganizationUpdate(BaseSchema):
    """Schema for updating an organization."""

    name: Optional[str] = Field(None, min_length=1, max_length=255)
    location: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = Field(None, max_length=50)
    address: Optional[str] = None
    is_active: Optional[bool] = None


class OrganizationResponse(ResponseSchema, OrganizationBase):
    """Schema for organization response."""

    token: Optional[str] = Field(None, description="API token for organization")
    is_active: bool
    is_super_admin: bool = Field(default=False, description="Super admin status")
    camera_count: Optional[int] = Field(default=0, description="Number of cameras")
    detection_count: Optional[int] = Field(default=0, description="Total detections")


class OrganizationListResponse(BaseSchema):
    """Schema for list of organizations."""

    organizations: List[OrganizationResponse]
    total: int
