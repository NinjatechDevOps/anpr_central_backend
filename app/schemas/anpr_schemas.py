"""
Pydantic schemas for ANPR detection API requests and responses.
"""
from typing import Optional
from pydantic import BaseModel, Field, field_validator
from datetime import datetime

from app.models.anpr_detection import ProcessingStatus, NumberplateColor, VehicleSide


class AnprDetectionUploadRequest(BaseModel):
    """Request schema for uploading ANPR detection data."""

    organization_id: int = Field(..., description="Organization ID", gt=0)
    client_detection_id: Optional[str] = Field(
        None,
        description="Client's tracking ID for this detection",
        max_length=100
    )
    camera_id: str = Field(..., description="Camera ID", max_length=100)
    camera_name: Optional[str] = Field(None, description="Camera name", max_length=255)
    vehicle_class: Optional[str] = Field(None, description="Vehicle class", max_length=50)
    vehicle_track_id: Optional[str] = Field(
        None,
        description="Vehicle tracking ID",
        max_length=100
    )
    activity_type: Optional[str] = Field(
        None,
        description="Activity type: in or out"
    )
    detected_at: Optional[datetime] = Field(
        None,
        description="Client-side detection timestamp"
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "organization_id": 1,
                    "client_detection_id": "CAM001-20250101-000123",
                    "camera_id": "CAM001",
                    "camera_name": "Main Gate Camera",
                    "vehicle_class": "car",
                    "vehicle_track_id": "TRK-12345",
                    "activity_type": "in",
                    "detected_at": "2025-01-15T10:30:00Z"
                }
            ]
        }
    }


class AnprDetectionUploadResponse(BaseModel):
    """Response schema after successfully uploading ANPR detection."""

    success: bool = Field(..., description="Whether upload was successful")
    message: str = Field(..., description="Response message")
    detection_id: int = Field(..., description="Central server detection ID")
    client_detection_id: Optional[str] = Field(
        None,
        description="Client's tracking ID (if provided)"
    )
    status: ProcessingStatus = Field(..., description="Current processing status")
    created_at: datetime = Field(..., description="When detection was received by server")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "success": True,
                    "message": "Detection received and queued for processing",
                    "detection_id": 12345,
                    "client_detection_id": "CAM001-20250101-000123",
                    "status": "pending",
                    "created_at": "2025-01-15T10:30:00Z"
                }
            ]
        }
    }


class AnprDetectionResultResponse(BaseModel):
    """Response schema for querying detection results."""

    detection_id: int = Field(..., description="Central server detection ID")
    client_detection_id: Optional[str] = Field(
        None,
        description="Client's tracking ID"
    )
    organization_id: int = Field(..., description="Organization ID")
    organization_name: Optional[str] = Field(None, description="Organization name")
    camera_id: str = Field(..., description="Camera ID")
    camera_name: Optional[str] = Field(None, description="Camera name")
    object_type: Optional[str] = Field(None, description="Object/Vehicle type")
    vehicle_track_id: Optional[str] = Field(None, description="Vehicle tracking ID")
    activity_type: Optional[str] = Field(None, description="Activity type: in or out")
    detected_at: Optional[datetime] = Field(None, description="Client-side detection timestamp")
    image_url: Optional[str] = Field(None, description="URL to access the detection image")

    # Processing status
    status: ProcessingStatus = Field(..., description="Processing status")
    retry_count: int = Field(..., description="Number of retries")
    error_message: Optional[str] = Field(None, description="Error message if failed")

    # Timestamps
    created_at: datetime = Field(..., description="Server received timestamp")
    updated_at: datetime = Field(..., description="When detection was last updated")

    # LLM Results (null if not yet processed)
    numberplate_available: Optional[bool] = Field(
        None,
        description="Whether numberplate is visible"
    )
    numberplate_color: Optional[NumberplateColor] = Field(
        None,
        description="Numberplate color"
    )
    vehicle_side: Optional[VehicleSide] = Field(None, description="Vehicle side")
    llm_confidence: Optional[str] = Field(None, description="LLM confidence score")
    llm_reasoning: Optional[str] = Field(None, description="LLM reasoning/explanation")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "detection_id": 12345,
                    "client_detection_id": "CAM001-20250101-000123",
                    "organization_id": 1,
                    "camera_id": "CAM001",
                    "camera_name": "Main Gate Camera",
                    "vehicle_class": "car",
                    "vehicle_track_id": "TRK-12345",
                    "activity_type": "in",
                    "detected_at": "2025-01-15T10:30:00Z",
                    "status": "success",
                    "retry_count": 0,
                    "error_message": None,
                    "created_at": "2025-01-15T10:30:00Z",
                    "updated_at": "2025-01-15T10:30:05Z",
                    "numberplate_available": True,
                    "numberplate_text": "MH12AB1234",
                    "numberplate_color": "white",
                    "vehicle_side": "front",
                    "llm_confidence": '{"score": 0.95}'
                }
            ]
        }
    }


class ErrorResponse(BaseModel):
    """Standard error response schema."""

    success: bool = Field(default=False, description="Always false for errors")
    error: str = Field(..., description="Error type")
    message: str = Field(..., description="Error message")
    details: Optional[dict] = Field(None, description="Additional error details")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "success": False,
                    "error": "ValidationError",
                    "message": "Invalid organization_id",
                    "details": {"field": "organization_id", "issue": "must be greater than 0"}
                }
            ]
        }
    }
