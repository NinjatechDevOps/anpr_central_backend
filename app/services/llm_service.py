"""
LLM Service for numberplate extraction using Google Gemini.
"""
import base64
import json
import re
from typing import Optional

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage
from PIL import Image

from app.core.config import settings
from app.core.prompts import NUMBERPLATE_EXTRACTION_PROMPT
from app.core.logging import app_logger as logger
from app.schemas.llm_schemas import NumberplateExtractionResult
from app.services.storage_service import get_storage_service


class LLMService:
    """
    Service for extracting numberplate information from vehicle images using LLM.

    Uses Google Gemini Flash model with manual JSON parsing.
    Note: with_structured_output() has known issues with Gemini returning None
    due to MALFORMED_FUNCTION_CALL errors, so we use direct invocation instead.
    """

    def __init__(self):
        """Initialize LLM service with settings from config."""
        if not settings.GOOGLE_API_KEY:
            raise ValueError("GOOGLE_API_KEY not set in environment variables")

        # Initialize Gemini Flash model
        self.llm = ChatGoogleGenerativeAI(
            model="gemini-3-flash-preview",
            google_api_key=settings.GOOGLE_API_KEY,
            temperature=0,
            max_retries=2,
        )

        logger.info("LLM Service initialized with Gemini Flash")

    def _parse_json_response(self, response_text: str) -> dict:
        """
        Parse JSON from LLM response text.
        Handles markdown code blocks and raw JSON.
        """
        # Try to extract JSON from markdown code block
        json_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', response_text)
        if json_match:
            json_str = json_match.group(1).strip()
        else:
            # Try to find raw JSON object
            json_match = re.search(r'\{[\s\S]*\}', response_text)
            if json_match:
                json_str = json_match.group(0)
            else:
                json_str = response_text.strip()

        return json.loads(json_str)

    def extract_numberplate(
        self,
        image_path: str,
        image_data: Optional[bytes] = None
    ) -> NumberplateExtractionResult:
        """
        Extract numberplate information from a vehicle image.

        Args:
            image_path: Path to the image file
            image_data: Optional raw image bytes (if already loaded)

        Returns:
            NumberplateExtractionResult with extracted information

        Raises:
            Exception: If LLM call fails or image cannot be processed
        """
        try:
            logger.info(f"Processing image for numberplate extraction: {image_path}")

            # Load image if not provided
            if image_data is None:
                storage_service = get_storage_service()
                image_data = storage_service.get_file(image_path)

            # Encode image to base64
            image_base64 = base64.b64encode(image_data).decode("utf-8")

            # Create message with image
            message = HumanMessage(
                content=[
                    {"type": "text", "text": NUMBERPLATE_EXTRACTION_PROMPT},
                    {
                        "type": "image_url",
                        "image_url": f"data:image/jpeg;base64,{image_base64}"
                    }
                ]
            )

            # Call LLM directly (not with_structured_output which fails with Gemini)
            logger.info("Sending image to Gemini Flash LLM...")
            response = self.llm.invoke([message])

            # Log full LLM response
            logger.info(f"LLM raw response: {response.content}")

            # Parse JSON from response and validate with Pydantic
            try:
                json_data = self._parse_json_response(response.content)
                result = NumberplateExtractionResult(**json_data)
            except (json.JSONDecodeError, ValueError) as parse_error:
                logger.warning(f"Failed to parse LLM response: {parse_error}")
                result = NumberplateExtractionResult(
                    numberplate_available=False,
                    numberplate_text="N/A",
                    numberplate_color="unknown",
                    vehicle_side="unknown",
                    confidence_score=0.0,
                    reasoning="N/A"
                )

            logger.info(
                f"LLM extraction complete: "
                f"numberplate_available={result.numberplate_available}, "
                f"numberplate_text={result.numberplate_text}, "
                f"numberplate_color={result.numberplate_color}, "
                f"vehicle_side={result.vehicle_side}, "
                f"confidence_score={result.confidence_score}, "
                f"reasoning={result.reasoning}"
            )

            return result

        except Exception as exc:
            logger.error(f"Error in LLM numberplate extraction: {exc}")
            raise

    def validate_image(self, image_path: str) -> bool:
        """
        Validate if image file is readable.

        Args:
            image_path: Relative path to image file (e.g., "detections/1/2025/01/uuid.jpg")

        Returns:
            True if image is valid, False otherwise
        """
        try:
            # Use storage service to get full path
            storage_service = get_storage_service()
            image_data = storage_service.get_file(image_path)
            # Validate by attempting to open with PIL
            from io import BytesIO
            with Image.open(BytesIO(image_data)) as img:
                img.verify()
            return True
        except Exception as exc:
            logger.error(f"Image validation failed for {image_path}: {exc}")
            return False


# Singleton instance
_llm_service_instance: Optional[LLMService] = None


def get_llm_service() -> LLMService:
    """
    Get singleton instance of LLM service.

    Returns:
        LLMService instance
    """
    global _llm_service_instance
    if _llm_service_instance is None:
        _llm_service_instance = LLMService()
    return _llm_service_instance
