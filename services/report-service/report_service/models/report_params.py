from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel


class ReportFormat(StrEnum):
    JSON = "json"
    CSV = "csv"
    PDF = "pdf"


class DateRange(BaseModel):
    start: datetime
    end: datetime


class ReportRequest(BaseModel):
    locomotive_id: str | None = None
    report_type: str = "health_summary"
    format: ReportFormat = ReportFormat.JSON
    date_range: DateRange
