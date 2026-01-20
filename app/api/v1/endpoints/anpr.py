"""
ANPR Detection API Endpoints - Upload and query vehicle detections.
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, File, UploadFile, Form, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
from datetime import datetime, timedelta
from io import StringIO
import csv

from app.db.session import get_db
from app.api.dependencies import verify_org_token, get_org_filter
from app.models.organization import Organization
from app.models.anpr_detection import AnprDetection, ProcessingStatus
from app.repositories.anpr_repository import AnprDetectionRepository
from app.schemas.anpr_schemas import (
    AnprDetectionUploadResponse,
    AnprDetectionResultResponse,
    ErrorResponse
)
from app.services.storage_service import get_storage_service
from app.services.report_service import ReportService
from app.tasks.anpr_tasks import process_anpr_detection
from app.core.logging import app_logger as logger
from app.core.config import settings

router = APIRouter()


@router.post(
    "/upload",
    response_model=AnprDetectionUploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload ANPR detection",
    description="Upload vehicle detection data with image for processing"
)
async def upload_anpr_detection(
    image: UploadFile = File(..., description="Vehicle image file"),
    client_detection_id: Optional[str] = Form(None, max_length=100),
    camera_id: str = Form(..., max_length=100),
    camera_name: Optional[str] = Form(None, max_length=255),
    vehicle_class: Optional[str] = Form(None, max_length=50),
    vehicle_track_id: Optional[str] = Form(None, max_length=100),
    activity_type: Optional[str] = Form(None, description="Activity type: in/IN or out/OUT"),
    detected_at: Optional[datetime] = Form(None, description="Client-side detection timestamp"),
    organization: Organization = Depends(verify_org_token),
    db: Session = Depends(get_db)
):
    """
    Upload ANPR detection data from organization.

    Requires:
    - X-API-Token header with valid organization token
    - Multipart form data with image file and detection metadata

    Returns immediate confirmation with detection_id for tracking.
    Processing happens asynchronously via Celery.
    """
    try:
        # Convert activity_type to lowercase string (case-insensitive input)
        activity_type_value = None
        if activity_type:
            activity_type_lower = activity_type.lower()
            if activity_type_lower not in ["in", "out"]:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid activity_type '{activity_type}'. Must be 'in' or 'out' (case-insensitive)"
                )
            activity_type_value = activity_type_lower
        # Validate file size
        file_content = await image.read()
        file_size = len(file_content)

        if file_size > settings.MAX_UPLOAD_SIZE:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"File size {file_size} exceeds maximum {settings.MAX_UPLOAD_SIZE} bytes"
            )

        # Validate content type
        if not image.content_type or not image.content_type.startswith('image/'):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Only image files are allowed"
            )

        logger.info(
            f"Receiving ANPR upload from org_id={organization.id}, "
            f"camera={camera_id}, size={file_size} bytes"
        )

        # Reset file pointer for storage service
        await image.seek(0)

        # Save image to storage (returns relative path like "detections/1/2025/01/uuid.jpg")
        storage_service = get_storage_service()
        image_path = await storage_service.save_file(
            file=image,
            organization_id=organization.id
        )

        logger.info(f"Image saved to: {image_path}")

        # Create detection record in database
        detection_data = {
            "organization_id": organization.id,
            "client_detection_id": client_detection_id,
            "camera_id": camera_id,
            "camera_name": camera_name,
            "vehicle_class": vehicle_class,
            "vehicle_track_id": vehicle_track_id,
            "activity_type": activity_type_value,
            "detected_at": detected_at,
            "image_path": image_path,
            "status": ProcessingStatus.PENDING,
            "retry_count": 0
        }

        repo = AnprDetectionRepository(db)
        detection = repo.create(detection_data)
        db.commit()

        logger.info(f"Created detection record: id={detection.id}")

        # Queue for async processing
        process_anpr_detection.apply_async(
            args=[detection.id],
            queue="anpr_processing"
        )

        logger.info(f"Queued detection {detection.id} for processing")

        return AnprDetectionUploadResponse(
            success=True,
            message="Detection received and queued for processing",
            detection_id=detection.id,
            client_detection_id=detection.client_detection_id,
            status=detection.status,
            created_at=detection.created_at
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error uploading ANPR detection: {e}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to upload detection: {str(e)}"
        )


@router.get(
    "/detection/{detection_id}",
    response_model=AnprDetectionResultResponse,
    summary="Get detection result by ID",
    description="Retrieve processing results for a specific detection"
)
async def get_detection_result(
    detection_id: int,
    organization: Organization = Depends(verify_org_token),
    db: Session = Depends(get_db)
):
    """
    Get detection result by central detection ID.

    Requires:
    - X-API-Token header with valid organization token
    - detection_id path parameter

    Returns detection data and processing results (if completed).
    """
    repo = AnprDetectionRepository(db)
    detection = repo.get_by_id(detection_id)

    if not detection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Detection {detection_id} not found"
        )

    # Verify organization owns this detection
    if detection.organization_id != organization.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this detection"
        )

    return AnprDetectionResultResponse(
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
        numberplate_color=detection.numberplate_color,
        vehicle_side=detection.vehicle_side,
        llm_confidence=detection.llm_confidence,
        llm_reasoning=detection.llm_raw_response
    )


@router.get(
    "/detection/client/{client_detection_id}",
    response_model=AnprDetectionResultResponse,
    summary="Get detection result by client ID",
    description="Retrieve processing results using client's tracking ID"
)
async def get_detection_by_client_id(
    client_detection_id: str,
    organization: Organization = Depends(verify_org_token),
    db: Session = Depends(get_db)
):
    """
    Get detection result by client's tracking ID.

    Requires:
    - X-API-Token header with valid organization token
    - client_detection_id path parameter

    Returns detection data and processing results (if completed).
    """
    repo = AnprDetectionRepository(db)
    detection = repo.get_by_client_detection_id(
        organization_id=organization.id,
        client_detection_id=client_detection_id
    )

    if not detection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Detection with client_id '{client_detection_id}' not found"
        )

    return AnprDetectionResultResponse(
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
        numberplate_color=detection.numberplate_color,
        vehicle_side=detection.vehicle_side,
        llm_confidence=detection.llm_confidence,
        llm_reasoning=detection.llm_raw_response
    )


@router.get(
    "/detections",
    response_model=List[AnprDetectionResultResponse],
    summary="List detections",
    description="Get paginated list of detections. Super admin can view all orgs, regular users see only their data."
)
async def list_detections(
    skip: int = 0,
    limit: int = 100,
    status_filter: Optional[ProcessingStatus] = None,
    camera_id: Optional[str] = None,
    org_filter: Optional[int] = Depends(get_org_filter),
    db: Session = Depends(get_db)
):
    """
    List detections with smart filtering.

    Regular users: Always see only their own organization's data
    Super admins: Can optionally filter by organization_id or see all

    Requires:
    - X-API-Token header with valid organization token

    Query parameters:
    - skip: Number of records to skip (pagination)
    - limit: Maximum records to return (max 100)
    - status_filter: Filter by processing status
    - camera_id: Filter by camera ID
    - organization_id: Filter by org ID (super admin only)

    Returns paginated list of detections.
    """
    if limit > 100:
        limit = 100

    repo = AnprDetectionRepository(db)

    # Get detections based on filter
    if org_filter is not None:
        # Filtered to specific org (regular user or super admin filtering)
        if camera_id:
            detections = repo.get_by_camera(
                organization_id=org_filter,
                camera_id=camera_id,
                skip=skip,
                limit=limit,
                status=status_filter
            )
        else:
            detections = repo.get_by_organization(
                organization_id=org_filter,
                skip=skip,
                limit=limit,
                status=status_filter
            )
    else:
        # Super admin viewing all orgs
        detections = repo.get_all_with_filters(
            skip=skip,
            limit=limit,
            status=status_filter,
            camera_id=camera_id
        )

    return [
        AnprDetectionResultResponse(
            detection_id=d.id,
            client_detection_id=d.client_detection_id,
            organization_id=d.organization_id,
            organization_name=d.organization.name if d.organization else None,
            camera_id=d.camera_id,
            camera_name=d.camera_name,
            object_type=d.vehicle_class,
            vehicle_track_id=d.vehicle_track_id,
            activity_type=d.activity_type,
            detected_at=d.detected_at,
            image_url=f"/uploads/{d.image_path}" if d.image_path else None,
            status=d.status,
            retry_count=d.retry_count,
            error_message=d.error_message,
            created_at=d.created_at,
            updated_at=d.updated_at,
            numberplate_available=d.numberplate_available,
            numberplate_color=d.numberplate_color,
            vehicle_side=d.vehicle_side,
            llm_confidence=d.llm_confidence,
            llm_reasoning=d.llm_raw_response
        )
        for d in detections
    ]


@router.get(
    "/reports/export",
    summary="Export detections report",
    description="Export filtered detections as CSV file"
)
async def export_detections_report(
    date_filter: Optional[str] = Query(None, description="today/yesterday/this_week/this_month/custom"),
    start_date: Optional[datetime] = Query(None, description="Start date for custom range"),
    end_date: Optional[datetime] = Query(None, description="End date for custom range"),
    organization_id: Optional[int] = Query(None, description="Filter by organization ID"),
    camera_id: Optional[str] = Query(None, description="Filter by camera ID"),
    activity_type: Optional[str] = Query(None, description="Filter by activity type (in/out)"),
    timezone_offset: Optional[int] = Query(0, description="Timezone offset in minutes from UTC (e.g., 330 for IST, -300 for EST)"),
    db: Session = Depends(get_db)
):
    """
    Export detections report with flexible filters.

    Query parameters:
    - date_filter: Predefined date ranges (today/yesterday/this_week/this_month/custom)
    - start_date, end_date: For custom date range
    - organization_id: Filter by organization (super admin only)
    - camera_id: Filter by camera
    - activity_type: Filter by activity type

    Returns CSV file with detection data.
    """
    try:
        logger.info(f"Export request - date_filter: {date_filter}, org: {organization_id}, camera: {camera_id}")

        # Get filtered detections from repository
        repo = AnprDetectionRepository(db)
        detections = repo.get_filtered_for_report(
            organization_id=organization_id,
            camera_id=camera_id,
            activity_type=activity_type,
            date_filter=date_filter,
            start_date=start_date,
            end_date=end_date
        )

        logger.info(f"Found {len(detections)} detections for export")

        # Generate CSV using service with timezone offset
        report_service = ReportService()
        csv_content = report_service.generate_csv(detections, timezone_offset_minutes=timezone_offset)
        filename = report_service.generate_filename()

        logger.info(f"Generated CSV file: {filename}")

        return StreamingResponse(
            iter([csv_content]),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
    except Exception as e:
        logger.error(f"Error exporting report: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to export report: {str(e)}"
        )
