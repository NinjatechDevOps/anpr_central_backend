"""
Plate Recognizer Service for numberplate extraction using platerecognizer.com API.
"""
from io import BytesIO
from typing import Optional

import httpx
from PIL import Image

from app.core.config import settings
from app.core.logging import app_logger as logger
from app.schemas.llm_schemas import NumberplateExtractionResult
from app.services.storage_service import get_storage_service


class PlateRecognizerService:
    """
    Service for extracting numberplate information from vehicle images
    using the Plate Recognizer API (https://platerecognizer.com).
    """

    def __init__(self):
        """Initialize Plate Recognizer service with settings from config."""
        if not settings.PLATE_RECOGNIZER_API_TOKEN:
            raise ValueError("PLATE_RECOGNIZER_API_TOKEN not set in environment variables")

        self.api_url = settings.PLATE_RECOGNIZER_API_URL
        self.token = settings.PLATE_RECOGNIZER_API_TOKEN
        self.regions = [settings.PLATE_RECOGNIZER_REGIONS]

        logger.info("Plate Recognizer Service initialized")

    def _empty_result(self, reasoning: str = "N/A") -> NumberplateExtractionResult:
        """Build the fallback result used when no plate is detected or the response is unusable."""
        return NumberplateExtractionResult(
            numberplate_available=False,
            numberplate_text="N/A",
            numberplate_color="unknown",
            vehicle_side="unknown",
            confidence_score=0.0,
            reasoning=reasoning,
        )

    def extract_numberplate(
        self,
        image_path: str,
        image_data: Optional[bytes] = None
    ) -> NumberplateExtractionResult:
        """
        Extract numberplate information from a vehicle image via Plate Recognizer.

        Args:
            image_path: Path to the image file
            image_data: Optional raw image bytes (if already loaded)

        Returns:
            NumberplateExtractionResult with extracted information

        Raises:
            httpx.HTTPError: If the API call itself fails (network error, timeout, non-2xx
                status) — left to bubble up so Celery's existing retry/backoff can recover
                from transient outages. Only a successful response with no plate detected,
                or an unparseable successful response, is mapped to the N/A fallback.
        """
        logger.info(f"Sending image to Plate Recognizer: {image_path}")

        if image_data is None:
            storage_service = get_storage_service()
            image_data = storage_service.get_file(image_path)

        response = httpx.post(
            self.api_url,
            data={"regions": self.regions},
            files={"upload": image_data},
            headers={"Authorization": f"Token {self.token}"},
            timeout=60.0,
        )
        response.raise_for_status()

        logger.info(f"Plate Recognizer raw response: {response.text}")

        try:
            data = response.json()
            results = data.get("results") or []

            if not results:
                return self._empty_result()

            best = results[0]
            plate = (best.get("plate") or "").upper()
            if not plate:
                return self._empty_result()

            vehicle = best.get("vehicle") or {}
            region = best.get("region") or {}
            reasoning = f"vehicle_type={vehicle.get('type', 'unknown')}, region={region.get('code', 'unknown')}"

            result = NumberplateExtractionResult(
                numberplate_available=True,
                numberplate_text=plate,
                numberplate_color="unknown",
                vehicle_side="unknown",
                confidence_score=best.get("score", 0.0),
                reasoning=reasoning,
            )
        except (ValueError, KeyError, TypeError) as parse_error:
            logger.warning(f"Failed to parse Plate Recognizer response: {parse_error}")
            result = self._empty_result()

        logger.info(
            f"Plate Recognizer extraction complete: "
            f"numberplate_available={result.numberplate_available}, "
            f"numberplate_text={result.numberplate_text}, "
            f"confidence_score={result.confidence_score}"
        )

        return result

    def validate_image(self, image_path: str) -> bool:
        """
        Validate if image file is readable.

        Args:
            image_path: Relative path to image file (e.g., "detections/1/2025/01/uuid.jpg")

        Returns:
            True if image is valid, False otherwise
        """
        try:
            storage_service = get_storage_service()
            image_data = storage_service.get_file(image_path)
            with Image.open(BytesIO(image_data)) as img:
                img.verify()
            return True
        except Exception as exc:
            logger.error(f"Image validation failed for {image_path}: {exc}")
            return False


# Singleton instance
_plate_recognizer_service_instance: Optional[PlateRecognizerService] = None


def get_plate_recognizer_service() -> PlateRecognizerService:
    """
    Get singleton instance of Plate Recognizer service.

    Returns:
        PlateRecognizerService instance
    """
    global _plate_recognizer_service_instance
    if _plate_recognizer_service_instance is None:
        _plate_recognizer_service_instance = PlateRecognizerService()
    return _plate_recognizer_service_instance
