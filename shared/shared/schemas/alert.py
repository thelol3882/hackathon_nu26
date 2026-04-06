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
    # str (not SensorType enum) so new sensor keys don't break deserialization
    sensor_type: str
    severity: AlertSeverity
    value: float
    threshold_min: float
    threshold_max: float
    message: str
    recommendation: str = ""
    timestamp: datetime
    acknowledged: bool = False
