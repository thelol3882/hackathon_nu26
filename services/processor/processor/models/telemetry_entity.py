from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass
class TelemetryRow:
    """Maps to the raw_telemetry TimescaleDB hypertable."""

    time: datetime
    locomotive_id: UUID
    sensor_type: str
    value: float
    unit: str
    latitude: float | None = None
    longitude: float | None = None
