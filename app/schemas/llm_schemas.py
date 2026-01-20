"""
Pydantic schemas for LLM structured output.
"""
from typing import Literal, Optional
from pydantic import BaseModel, Field
from enum import Enum


class NumberplateColor(str, Enum):
    """Indian numberplate color options."""
    WHITE = "white"
    YELLOW = "yellow"
    BLACK = "black"
    BLUE = "blue"
    RED = "red"
    GREEN = "green"
    UNKNOWN = "unknown"


class VehicleSide(str, Enum):
    """Vehicle side captured in image."""
    FRONT = "front"
    BACK = "back"
    SIDE = "side"
    UNKNOWN = "unknown"


class NumberplateExtractionResult(BaseModel):
    """
    Structured output from LLM for numberplate extraction.

    This schema defines exactly what we expect the LLM to return
    when analyzing a vehicle image.
    """

    numberplate_available: bool = Field(
        description="Whether a numberplate is visible and readable in the image"
    )

    numberplate_text: str = Field(
        default="N/A",
        description="The numberplate text in uppercase without spaces, e.g. MH12AB1234. Use N/A if not available."
    )

    numberplate_color: Literal["white", "yellow", "black", "blue", "red", "green", "unknown"] = Field(
        default="unknown",
        description="Color of the numberplate: white, yellow, black, blue, red, green, or unknown"
    )

    vehicle_side: Literal["front", "back", "side", "unknown"] = Field(
        default="unknown",
        description="Which side of the vehicle is visible: front, back, side, or unknown"
    )

    confidence_score: float = Field(
        default=0.0,
        description="Confidence score from 0.0 to 1.0"
    )

    reasoning: str = Field(
        default="N/A",
        description="Brief explanation of the extraction result"
    )
