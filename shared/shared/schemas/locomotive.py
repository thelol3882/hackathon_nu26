from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from shared.enums import LocomotiveStatus


class LocomotiveBase(BaseModel):
    serial_number: str
    model: str
    manufacturer: str
    year_manufactured: int


class LocomotiveCreate(LocomotiveBase):
    pass


class LocomotiveRead(LocomotiveBase):
    id: UUID
    status: LocomotiveStatus
    created_at: datetime
    updated_at: datetime


class LocomotiveListResponse(BaseModel):
    items: list[LocomotiveRead]
    total: int
