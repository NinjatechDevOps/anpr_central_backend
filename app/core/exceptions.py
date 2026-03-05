"""
Custom exceptions for the Central Server application.
"""
from fastapi import HTTPException, status


class AppException(HTTPException):
    """Base application exception."""

    def __init__(self, detail: str, status_code: int = status.HTTP_400_BAD_REQUEST):
        super().__init__(status_code=status_code, detail=detail)


class NotFoundException(AppException):
    """Resource not found exception."""

    def __init__(self, resource: str, identifier: str | int):
        super().__init__(
            detail=f"{resource} with identifier '{identifier}' not found",
            status_code=status.HTTP_404_NOT_FOUND
        )


class UnauthorizedException(AppException):
    """Unauthorized access exception."""

    def __init__(self, detail: str = "Invalid authentication credentials"):
        super().__init__(
            detail=detail,
            status_code=status.HTTP_401_UNAUTHORIZED
        )


class ForbiddenException(AppException):
    """Forbidden access exception."""

    def __init__(self, detail: str = "You don't have permission to access this resource"):
        super().__init__(
            detail=detail,
            status_code=status.HTTP_403_FORBIDDEN
        )


class DuplicateException(AppException):
    """Duplicate resource exception."""

    def __init__(self, resource: str, field: str, value: str):
        super().__init__(
            detail=f"{resource} with {field} '{value}' already exists",
            status_code=status.HTTP_409_CONFLICT
        )


class FileUploadException(AppException):
    """File upload exception."""

    def __init__(self, detail: str = "File upload failed"):
        super().__init__(
            detail=detail,
            status_code=status.HTTP_400_BAD_REQUEST
        )


class ExternalSyncException(Exception):
    """Exception for external server sync failures (not an HTTP exception)."""

    def __init__(self, endpoint: str, status_code: int = 0, detail: str = ""):
        self.endpoint = endpoint
        self.sync_status_code = status_code
        self.detail = detail
        super().__init__(f"External sync failed [{endpoint}] status={status_code}: {detail}")
