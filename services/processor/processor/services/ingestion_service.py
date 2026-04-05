"""
Ingestion service: flatten a TelemetryReading into ORM rows,
applying EMA filtering before persistence.

HF readings (sample_rate_hz >= 10) are de-duplicated for DB storage:
a row is only written when the filtered value changes by more than a noise
floor, preventing TimescaleDB from being flooded at 50 Hz.
"""

from processor.models.telemetry_entity import TelemetryRecord
from processor.services.filter_service import ema_filter
from shared.schemas.telemetry import TelemetryReading

# Minimum relative change required to persist a high-frequency reading.
_HF_NOISE_FLOOR = 0.005  # 0.5 %

_last_persisted: dict[tuple[str, str], float] = {}


def flatten_reading(reading: TelemetryReading) -> list[TelemetryRecord]:
    """
    Convert a TelemetryReading into TelemetryRecord ORM rows ready for
    session.add_all().

    Side-effect: each SensorPayload.value is replaced with its EMA-filtered
    counterpart so that downstream callers (health_service, alert_evaluator)
    automatically operate on the clean signal.

    Returns only the rows that should be persisted (HF dedup applied).
    """
    loco_id = str(reading.locomotive_id)
    is_hf = reading.sample_rate_hz >= 10.0
    rows: list[TelemetryRecord] = []

    for sensor in reading.sensors:
        sensor_key = sensor.sensor_type.value

        raw_value = sensor.value
        filtered = ema_filter(loco_id, sensor_key, raw_value)

        # Mutate payload so downstream services receive the filtered signal.
        sensor.value = filtered

        if is_hf:
            dedup_key = (loco_id, sensor_key)
            last = _last_persisted.get(dedup_key)
            if last is not None:
                relative_change = abs(filtered - last) / (abs(last) + 1e-9)
                if relative_change < _HF_NOISE_FLOOR:
                    continue  # skip DB write — value hasn't moved enough
            _last_persisted[dedup_key] = filtered

        rows.append(
            TelemetryRecord(
                time=reading.timestamp,
                locomotive_id=reading.locomotive_id,
                locomotive_type=reading.locomotive_type.value,
                sensor_type=sensor_key,
                value=raw_value,
                filtered_value=filtered,
                unit=sensor.unit,
                sample_rate_hz=reading.sample_rate_hz,
                latitude=reading.gps.latitude if reading.gps else None,
                longitude=reading.gps.longitude if reading.gps else None,
            )
        )

    return rows
