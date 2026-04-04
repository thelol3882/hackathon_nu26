from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from shared.enums import SensorType


class GPSCoordinate(BaseModel):
    latitude: float
    longitude: float


class SensorPayload(BaseModel):
    sensor_type: SensorType
    value: float
    unit: str


class TelemetryReading(BaseModel):
    locomotive_id: UUID
    timestamp: datetime
    gps: GPSCoordinate | None = None
    sensors: list[SensorPayload]
