"""
Analytics Schemas - Request/Response models for analytics endpoints.
"""
from pydantic import BaseModel


class HourlyStatsResponse(BaseModel):
    """Hourly statistics response."""
    hour: int
    total: int
    success: int
    failed: int
    in_count: int
    out_count: int


class DailyStatsResponse(BaseModel):
    """Daily statistics response."""
    date: str
    total: int
    success: int
    failed: int
    in_count: int
    out_count: int
    success_rate: float


class WeeklyStatsResponse(BaseModel):
    """Weekly statistics response."""
    year: int
    week: int
    total: int
    success: int
    failed: int
    in_count: int
    out_count: int
    success_rate: float


class MonthlyStatsResponse(BaseModel):
    """Monthly statistics response."""
    year: int
    month: int
    total: int
    success: int
    failed: int
    in_count: int
    out_count: int
    success_rate: float


class VehicleTypeStatsResponse(BaseModel):
    """Vehicle type statistics response."""
    vehicle_type: str
    count: int


class CameraPerformanceResponse(BaseModel):
    """Camera performance statistics response."""
    camera_id: str
    camera_name: str
    total: int
    success: int
    failed: int
    success_rate: float
