from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from shared.enums import LocomotiveType, SensorType


class GPSCoordinate(BaseModel):
    latitude: float
    longitude: float
    # Compass bearing from the local polyline segment. Optional so historical
    # readings without bearing data still validate.
    bearing_deg: float | None = None


class SensorPayload(BaseModel):
    sensor_type: SensorType
    value: float
    unit: str


class TelemetryReading(BaseModel):
    locomotive_id: UUID
    locomotive_type: LocomotiveType
    timestamp: datetime
    # 1 Hz for thermal/slow params; 50 Hz for electrodynamic/mechanical
    sample_rate_hz: float = Field(default=1.0, ge=0.1, le=200.0)
    gps: GPSCoordinate | None = None
    sensors: list[SensorPayload]
    # Route this locomotive is traversing; lets the dashboard look up
    # polyline + stations via /routes. Optional for backward compat.
    route_name: str | None = None
