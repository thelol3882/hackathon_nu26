from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass
class ReportRow:
    """Maps to the generated_reports table."""

    id: UUID
    locomotive_id: UUID | None
    report_type: str
    format: str
    created_at: datetime
    data: dict
