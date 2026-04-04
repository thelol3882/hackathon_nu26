from datetime import datetime

from pydantic import BaseModel


class TimeRange(BaseModel):
    start: datetime
    end: datetime


class PaginationParams(BaseModel):
    offset: int = 0
    limit: int = 50


class FilterParams(BaseModel):
    locomotive_id: str | None = None
    sensor_type: str | None = None
    time_range: TimeRange | None = None
    pagination: PaginationParams = PaginationParams()
