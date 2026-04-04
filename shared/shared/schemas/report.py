"""Shared report schemas used by api-gateway (producer) and report-service (consumer)."""

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel


class ReportFormat(StrEnum):
    JSON = "json"
    CSV = "csv"
    PDF = "pdf"


class ReportStatus(StrEnum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class DateRange(BaseModel):
    start: datetime
    end: datetime


class ReportRequest(BaseModel):
    locomotive_id: str | None = None
    report_type: str = "health_summary"
    format: ReportFormat = ReportFormat.JSON
    date_range: DateRange


class ReportJobMessage(BaseModel):
    """Message contract for the report.generate RabbitMQ queue."""

    report_id: UUID
    locomotive_id: str | None = None
    report_type: str
    format: ReportFormat
    date_range: DateRange
    requested_at: datetime


class ReportResponse(BaseModel):
    report_id: UUID
    locomotive_id: str | None = None
    report_type: str
    format: ReportFormat
    status: ReportStatus
    created_at: datetime
    data: dict | None = None
