"""
Organization model - Companies/clients using the ANPR system.
"""
from sqlalchemy import Column, String, Text, Boolean
from sqlalchemy.orm import relationship

from app.db.session import Base
from app.models.base import BaseActiveModel


class Organization(Base, BaseActiveModel):
    """
    Organization model representing a company/client.
    Each organization can have multiple ANPR detections.
    """

    __tablename__ = "organizations"

    # Basic Info
    name = Column(String(255), nullable=False, index=True)
    code = Column(String(50), unique=True, nullable=False, index=True)  # Unique org code
    location = Column(String(255), nullable=True)  # Organization location
    description = Column(Text, nullable=True)

    # API Token for Authentication
    token = Column(String(64), unique=True, nullable=False, index=True)  # Unique API token

    # Role - Super Admin can access all organizations' data
    is_super_admin = Column(Boolean, default=False, nullable=False, index=True)

    # Contact Info
    email = Column(String(255), nullable=True)
    phone = Column(String(50), nullable=True)
    address = Column(Text, nullable=True)

    # Relationships
    anpr_detections = relationship("AnprDetection", back_populates="organization", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Organization(id={self.id}, name='{self.name}', code='{self.code}')>"
