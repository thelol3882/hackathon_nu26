from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass
class LocomotiveRow:
    """Maps to the locomotives table."""

    id: UUID
    serial_number: str
    model: str
    manufacturer: str
    year_manufactured: int
    status: str
    created_at: datetime
    updated_at: datetime
