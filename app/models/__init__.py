"""
Database models for Central Server.
"""
from app.models.organization import Organization
from app.models.anpr_detection import AnprDetection

__all__ = [
    "Organization",
    "AnprDetection",
]
