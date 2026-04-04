from shared.schemas.telemetry import TelemetryReading
from processor.models.telemetry_entity import TelemetryRow


def flatten_reading(reading: TelemetryReading) -> list[TelemetryRow]:
    """Convert a single TelemetryReading into individual DB rows per sensor."""
    rows: list[TelemetryRow] = []
    for sensor in reading.sensors:
        rows.append(
            TelemetryRow(
                time=reading.timestamp,
                locomotive_id=reading.locomotive_id,
                sensor_type=sensor.sensor_type.value,
                value=sensor.value,
                unit=sensor.unit,
                latitude=reading.gps.latitude if reading.gps else None,
                longitude=reading.gps.longitude if reading.gps else None,
            )
        )
    return rows
