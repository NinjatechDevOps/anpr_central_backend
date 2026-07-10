"""
Factory for selecting the active numberplate recognition provider.

This is the single place that knows both providers exist. Switching providers
in production is purely a config change (NUMBERPLATE_PROVIDER + the matching
API key) — no code elsewhere needs to change.
"""
from typing import Optional, Union

from app.core.config import settings
from app.core.logging import app_logger as logger
from app.services.llm_service import LLMService
from app.services.plate_recognizer_service import PlateRecognizerService

NumberplateService = Union[LLMService, PlateRecognizerService]


def get_numberplate_service() -> Optional[NumberplateService]:
    """
    Get the configured numberplate recognition service.

    Returns:
        The active provider's service instance, or None if the selected
        provider has no API credentials configured (caller should skip
        extraction for this run, same as today's "no GOOGLE_API_KEY" behavior).

    Raises:
        ValueError: If NUMBERPLATE_PROVIDER is set to an unrecognized value.
    """
    provider = settings.NUMBERPLATE_PROVIDER.lower()

    if provider == "gemini":
        if not settings.GOOGLE_API_KEY:
            logger.warning("NUMBERPLATE_PROVIDER=gemini but GOOGLE_API_KEY is not set")
            return None
        from app.services.llm_service import get_llm_service
        return get_llm_service()

    if provider == "plate_recognizer":
        if not settings.PLATE_RECOGNIZER_API_TOKEN:
            logger.warning("NUMBERPLATE_PROVIDER=plate_recognizer but PLATE_RECOGNIZER_API_TOKEN is not set")
            return None
        from app.services.plate_recognizer_service import get_plate_recognizer_service
        return get_plate_recognizer_service()

    raise ValueError(f"Unknown NUMBERPLATE_PROVIDER: '{provider}'. Expected 'gemini' or 'plate_recognizer'.")
