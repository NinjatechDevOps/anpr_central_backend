"""
ANPR Detection model - Vehicle detections with LLM-based numberplate recognition.
"""
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Enum, Text
from sqlalchemy.orm import relationship
import enum

from app.db.session import Base
from app.models.base import BaseModel


class ProcessingStatus(str, enum.Enum):
    """Processing status for ANPR detections."""
    PENDING = "pending"
    PROCESSING = "processing"
    RETRYING = "retrying"
    SUCCESS = "success"
    FAILED = "failed"


class NumberplateColor(str, enum.Enum):
    """Indian numberplate color options."""
    WHITE = "white"  # Private vehicles
    YELLOW = "yellow"  # Commercial vehicles (taxis, auto-rickshaws)
    BLACK = "black"  # Commercial rental vehicles
    BLUE = "blue"  # Foreign diplomats
    RED = "red"  # Temporary registration (President, Governor, etc.)
    GREEN = "green"  # Electric vehicles
    UNKNOWN = "unknown"


class VehicleSide(str, enum.Enum):
    """Vehicle side captured in image."""
    FRONT = "front"
    BACK = "back"
    SIDE = "side"
    UNKNOWN = "unknown"


# ActivityType values (no longer an enum, just plain strings)
# Valid values: "in", "out"


class AnprDetection(Base, BaseModel):
    """
    ANPR Detection model with LLM-based numberplate recognition.

    Stores vehicle detection data from organizations and processes images
    using Google Gemini LLM to extract numberplate information.

    Inherits: id, created_at, updated_at from BaseModel
    """

    __tablename__ = "anpr_detections"

    # Organization Reference (Direct FK for fast org-wise queries)
    organization_id = Column(
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # Client Tracking ID (provided by organization for their own tracking)
    client_detection_id = Column(String(100), nullable=True, index=True)

    # Camera/Source Metadata
    camera_id = Column(String(100), nullable=False, index=True)
    camera_name = Column(String(255), nullable=True)

    # Vehicle Detection Info
    vehicle_class = Column(String(50), nullable=True, index=True)  # car, truck, bus, motorcycle
    vehicle_track_id = Column(String(100), nullable=True, index=True)  # Track ID from detection system
    activity_type = Column(String(10), nullable=True, index=True)  # in/out
    detected_at = Column(DateTime(timezone=True), nullable=True, index=True)  # Client-side detection timestamp

    # Image Storage (relative path from uploads directory)
    # Will be served via /uploads/{image_path}
    image_path = Column(String(512), nullable=False)

    # Processing Status & Retry Logic
    status = Column(
        Enum(ProcessingStatus),
        default=ProcessingStatus.PENDING,
        nullable=False,
        index=True
    )
    retry_count = Column(Integer, default=0, nullable=False)
    error_message = Column(Text, nullable=True)

    # LLM Results - Numberplate Information
    numberplate_available = Column(Boolean, nullable=True)  # True if plate detected by LLM
    numberplate_text = Column(String(20), nullable=True, index=True)  # Extracted plate number
    numberplate_color = Column(Enum(NumberplateColor), nullable=True)
    vehicle_side = Column(Enum(VehicleSide), nullable=True)

    # LLM Additional Metadata (confidence scores, etc.)
    llm_confidence = Column(String(512), nullable=True)  # JSON string for confidence scores
    llm_raw_response = Column(Text, nullable=True)  # Store raw LLM response for debugging

    # Timestamps
    processed_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    organization = relationship("Organization", back_populates="anpr_detections")

    def __repr__(self):
        return (
            f"<AnprDetection(id={self.id}, org_id={self.organization_id}, "
            f"camera='{self.camera_name}', status='{self.status.value}')>"
        )
