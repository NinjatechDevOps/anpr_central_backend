"""
Base model mixins for common database fields.
"""
from sqlalchemy import Column, Integer, Boolean, DateTime
from sqlalchemy.sql import func


class TimestampMixin:
    """Mixin for created_at and updated_at timestamps."""

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False
    )


class IDMixin:
    """Mixin for primary key ID."""

    id = Column(Integer, primary_key=True, index=True)


class ActiveMixin:
    """Mixin for soft delete with is_active flag."""

    is_active = Column(Boolean, default=True, nullable=False, index=True)


class BaseModel(IDMixin, TimestampMixin):
    """
    Base model with ID and timestamps.

    Use this for tables that need: id, created_at, updated_at
    """
    pass


class BaseActiveModel(IDMixin, TimestampMixin, ActiveMixin):
    """
    Base model with ID, timestamps, and active status.

    Use this for tables that need: id, created_at, updated_at, is_active
    """
    pass
