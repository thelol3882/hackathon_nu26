from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from shared.enums import AlertSeverity, SensorType


class AlertThreshold(BaseModel):
    sensor_type: SensorType
    min_value: float
    max_value: float


class AlertEvent(BaseModel):
    id: UUID
    locomotive_id: UUID
    sensor_type: SensorType
    severity: AlertSeverity
    value: float
    threshold_min: float
    threshold_max: float
    message: str
    timestamp: datetime
    acknowledged: bool = False
