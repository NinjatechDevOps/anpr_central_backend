"""
Celery tasks for ANPR detection processing with LLM.
"""
from celery import Task
from sqlalchemy.orm import Session
from datetime import datetime

from app.core.celery_app import celery_app
from app.core.logging import app_logger as logger
from app.db.session import SessionLocal
from app.models.anpr_detection import AnprDetection, ProcessingStatus
from app.repositories.anpr_repository import AnprDetectionRepository
from app.services.llm_service import get_llm_service


class DatabaseTask(Task):
    """
    Base task with database session management.

    Ensures proper session cleanup after task execution.
    """
    _db = None

    @property
    def db(self) -> Session:
        """Get database session (singleton per task)."""
        if self._db is None:
            self._db = SessionLocal()
        return self._db

    def after_return(self, *args, **kwargs):
        """Close database session after task completion."""
        if self._db is not None:
            self._db.close()
            self._db = None


@celery_app.task(bind=True, base=DatabaseTask, name="process_anpr_detection")
def process_anpr_detection(self, detection_id: int):
    """
    Process ANPR detection with LLM to extract numberplate information.

    Args:
        detection_id: ID of the AnprDetection record to process

    Flow:
        1. Load detection from database
        2. Update status to PROCESSING
        3. Load image from storage
        4. Send to LLM for numberplate extraction
        5. Parse LLM response (structured output)
        6. Update database with results
        7. Handle errors and retries

    Retries:
        - Max 3 retries
        - Exponential backoff: 60s, 120s, 240s
    """
    db: Session = self.db
    repo = AnprDetectionRepository(db)

    try:
        logger.info(f"Starting ANPR processing for detection {detection_id}")

        # Step 1: Load detection record
        detection = repo.get_by_id(detection_id)
        if not detection:
            logger.error(f"Detection {detection_id} not found")
            return {"status": "error", "message": "Detection not found"}

        # Step 2: Update status to PROCESSING
        repo.update(detection_id, {
            "status": ProcessingStatus.PROCESSING,
            "error_message": None
        })
        db.commit()
        logger.info(f"Detection {detection_id} status updated to PROCESSING")

        # Step 3: Validate image exists
        # Image path is already in detection.image_path
        llm_service = get_llm_service()
        if not llm_service.validate_image(detection.image_path):
            raise ValueError(f"Invalid or corrupted image: {detection.image_path}")

        # Step 4: Send to LLM for numberplate extraction
        logger.info(f"Calling LLM service for detection {detection_id}")
        llm_result = llm_service.extract_numberplate(
            image_path=detection.image_path
        )

        # Step 5: Update database with LLM results
        update_data = {
            "status": ProcessingStatus.SUCCESS,
            "processed_at": datetime.utcnow(),
            "numberplate_available": llm_result.numberplate_available if llm_result else False,
            "numberplate_text": llm_result.numberplate_text if llm_result and llm_result.numberplate_text else "N/A",
            "numberplate_color": llm_result.numberplate_color if llm_result and llm_result.numberplate_color else "N/A",
            "vehicle_side": llm_result.vehicle_side if llm_result and llm_result.vehicle_side else "N/A",
            "llm_confidence": str(llm_result.confidence_score) if llm_result else "0.0",
            "llm_raw_response": llm_result.reasoning if llm_result and llm_result.reasoning else "N/A",
        }

        repo.update(detection_id, update_data)
        db.commit()

        logger.info(f"Detection {detection_id} processed successfully")
        return {"status": "success", "detection_id": detection_id}

    except Exception as exc:
        logger.error(f"Error processing detection {detection_id}: {exc}")

        # Update retry count
        current_retry = self.request.retries
        repo.update(detection_id, {
            "retry_count": current_retry + 1,
            "error_message": str(exc)
        })

        # Check if we should retry
        if current_retry < 3:
            # Update status to RETRYING
            repo.update(detection_id, {"status": ProcessingStatus.RETRYING})
            db.commit()

            # Retry with exponential backoff
            retry_delay = 60 * (2 ** current_retry)  # 60s, 120s, 240s
            logger.warning(
                f"Retrying detection {detection_id} in {retry_delay}s "
                f"(attempt {current_retry + 1}/3)"
            )
            raise self.retry(exc=exc, countdown=retry_delay)
        else:
            # Max retries reached - mark as FAILED
            repo.update(detection_id, {
                "status": ProcessingStatus.FAILED,
                "error_message": f"Max retries exceeded: {str(exc)}"
            })
            db.commit()
            logger.error(f"Detection {detection_id} failed after 3 retries")
            return {"status": "failed", "detection_id": detection_id, "error": str(exc)}
