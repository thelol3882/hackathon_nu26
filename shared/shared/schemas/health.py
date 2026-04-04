from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from shared.enums import SensorType


class ComponentHealth(BaseModel):
    sensor_type: SensorType
    score: float  # 0.0 - 1.0
    latest_value: float
    unit: str


class HealthIndex(BaseModel):
    locomotive_id: UUID
    overall_score: float  # 0.0 - 1.0
    components: list[ComponentHealth]
    calculated_at: datetime


class HealthSnapshot(BaseModel):
    locomotive_id: UUID
    overall_score: float
    calculated_at: datetime
