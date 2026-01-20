"""
Base schemas with common patterns.
"""
from pydantic import BaseModel, ConfigDict
from datetime import datetime


class BaseSchema(BaseModel):
    """Base schema with common configuration."""

    model_config = ConfigDict(
        from_attributes=True,
        validate_assignment=True,
        arbitrary_types_allowed=True
    )


class TimestampSchema(BaseSchema):
    """Schema with timestamp fields."""

    created_at: datetime
    updated_at: datetime


class ResponseSchema(TimestampSchema):
    """Base response schema with ID and timestamps."""

    id: int


class PaginationParams(BaseSchema):
    """Pagination parameters."""

    skip: int = 0
    limit: int = 100


class MessageResponse(BaseSchema):
    """Simple message response."""

    message: str
    success: bool = True
