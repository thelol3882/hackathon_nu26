from datetime import UTC, datetime
from uuid import uuid4

from shared.constants import DEFAULT_THRESHOLDS
from shared.enums import AlertSeverity
from shared.schemas.alert import AlertEvent
from shared.schemas.telemetry import SensorPayload


def evaluate_sensor(
    locomotive_id: str,
    sensor: SensorPayload,
) -> AlertEvent | None:
    """Check a sensor reading against default thresholds. Returns an AlertEvent if violated."""
    bounds = DEFAULT_THRESHOLDS.get(sensor.sensor_type.value)
    if bounds is None:
        return None

    min_val, max_val = bounds
    if min_val <= sensor.value <= max_val:
        return None

    severity = (
        AlertSeverity.CRITICAL
        if sensor.value > max_val * 1.2 or sensor.value < min_val * 0.8
        else AlertSeverity.WARNING
    )

    return AlertEvent(
        id=uuid4(),
        locomotive_id=locomotive_id,
        sensor_type=sensor.sensor_type,
        severity=severity,
        value=sensor.value,
        threshold_min=min_val,
        threshold_max=max_val,
        message=f"{sensor.sensor_type.value} out of range: {sensor.value} {sensor.unit}",
        timestamp=datetime.now(UTC),
    )
