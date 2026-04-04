from shared.schemas.locomotive import LocomotiveBase, LocomotiveCreate, LocomotiveRead
from shared.schemas.telemetry import TelemetryReading, SensorPayload, GPSCoordinate
from shared.schemas.alert import AlertEvent, AlertThreshold
from shared.schemas.health import HealthIndex, ComponentHealth, HealthSnapshot

__all__ = [
    "LocomotiveBase",
    "LocomotiveCreate",
    "LocomotiveRead",
    "TelemetryReading",
    "SensorPayload",
    "GPSCoordinate",
    "AlertEvent",
    "AlertThreshold",
    "HealthIndex",
    "ComponentHealth",
    "HealthSnapshot",
]
