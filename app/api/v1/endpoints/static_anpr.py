"""
Static (unauthenticated) ANPR endpoints for public detection review and manual correction.
"""
from typing import Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.anpr_detection import ProcessingStatus
from app.repositories.anpr_repository import AnprDetectionRepository
from app.schemas.anpr_schemas import (
    AnprDetectionResultResponse,
    StaticDetectionResponse,
    StaticDetectionListResponse,
    NumberplateUpdateRequest,
    NumberplateUpdateResponse,
)
from app.core.logging import app_logger as logger

router = APIRouter()


def _to_detection_response(detection, serial_no: int) -> StaticDetectionResponse:
    """Map an AnprDetection model to StaticDetectionResponse."""
    return StaticDetectionResponse(
        detection_id=detection.id,
        client_detection_id=detection.client_detection_id,
        organization_id=detection.organization_id,
        organization_name=detection.organization.name if detection.organization else None,
        camera_id=detection.camera_id,
        camera_name=detection.camera_name,
        object_type=detection.vehicle_class,
        vehicle_track_id=detection.vehicle_track_id,
        activity_type=detection.activity_type,
        detected_at=detection.detected_at,
        image_url=f"/uploads/{detection.image_path}" if detection.image_path else None,
        status=detection.status,
        retry_count=detection.retry_count,
        error_message=detection.error_message,
        created_at=detection.created_at,
        updated_at=detection.updated_at,
        numberplate_available=detection.numberplate_available,
        numberplate_text=detection.numberplate_text,
        numberplate_color=detection.numberplate_color,
        vehicle_side=detection.vehicle_side,
        llm_confidence=detection.llm_confidence,
        llm_reasoning=detection.llm_raw_response,
        serial_no=serial_no,
    )


@router.get(
    "/detections",
    response_model=StaticDetectionListResponse,
    summary="List detections (public)",
    description="Paginated list of detections where numberplate_text is not null. No authentication required."
)
async def list_detections_static(
    page: int = Query(1, ge=1, description="Page number (starts from 1)"),
    page_size: int = Query(100, ge=1, le=100, description="Number of items per page (max 100)"),
    status_filter: Optional[ProcessingStatus] = Query(None, description="Filter by processing status"),
    camera_id: Optional[str] = Query(None, description="Filter by camera ID"),
    activity_type: Optional[str] = Query(None, description="Filter by activity type (in/out)"),
    plate: Optional[str] = Query(None, description="Search by numberplate text (partial match)"),
    start_date: Optional[datetime] = Query(None, description="Start date filter (ISO format)"),
    end_date: Optional[datetime] = Query(None, description="End date filter (ISO format)"),
    organization_id: Optional[int] = Query(None, description="Filter by organization ID"),
    db: Session = Depends(get_db)
):
    """
    List detections with numberplate_text present.

    Only records where numberplate_text IS NOT NULL are returned.
    Serial numbers are 1-based within the current page.
    """
    skip = (page - 1) * page_size

    repo = AnprDetectionRepository(db)

    detections = repo.get_all_with_filters(
        skip=skip,
        limit=page_size,
        status=status_filter,
        camera_id=camera_id,
        organization_id=organization_id,
        start_date=start_date,
        end_date=end_date,
        activity_type=activity_type,
        plate=plate,
        numberplate_not_null=True,
    )
    total = repo.count_with_filters(
        organization_id=organization_id,
        status=status_filter,
        camera_id=camera_id,
        start_date=start_date,
        end_date=end_date,
        activity_type=activity_type,
        plate=plate,
        numberplate_not_null=True,
    )

    return StaticDetectionListResponse(
        detections=[
            _to_detection_response(d, serial_no=skip + idx + 1)
            for idx, d in enumerate(detections)
        ],
        total=total,
    )


@router.get(
    "/detection/{detection_id}",
    response_model=StaticDetectionResponse,
    summary="Get detection detail (public)",
    description="Get full details for a single detection record. No authentication required."
)
async def get_detection_static(
    detection_id: int,
    db: Session = Depends(get_db)
):
    """
    Get full detail for a detection by ID.

    Returns all fields including organization info and image URL.
    """
    repo = AnprDetectionRepository(db)
    detection = repo.get_by_id(detection_id)

    if not detection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Detection {detection_id} not found"
        )

    return _to_detection_response(detection, serial_no=detection.id)


@router.put(
    "/detection/update",
    response_model=NumberplateUpdateResponse,
    summary="Update numberplate text (public)",
    description="Manually correct a numberplate text by record ID. No authentication required."
)
async def update_numberplate_static(
    body: NumberplateUpdateRequest,
    db: Session = Depends(get_db)
):
    """
    Update numberplate_text for an ANPR detection record.

    Only two inputs accepted: id (record ID) and numberplate_text (corrected value).
    """
    repo = AnprDetectionRepository(db)

    detection = repo.get_by_id(body.id)
    if not detection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Detection {body.id} not found"
        )

    try:
        updated = repo.update(body.id, {"numberplate_text": body.numberplate_text})
        logger.info(f"Numberplate manually updated: detection_id={body.id}, plate={body.numberplate_text}")
    except Exception as e:
        logger.error(f"Failed to update numberplate for detection {body.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update numberplate: {str(e)}"
        )

    return NumberplateUpdateResponse(
        success=True,
        message="Numberplate updated successfully",
        detection=_to_detection_response(updated, serial_no=updated.id),
    )
