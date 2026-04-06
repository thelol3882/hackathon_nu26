"""Flatten a TelemetryReading into rows after EMA filtering.

High-frequency readings (>=10 Hz) are dedup'd against a noise floor to keep
TimescaleDB from being flooded at 50 Hz.
"""

from processor.services.filter_service import ema_filter
from shared.schemas.telemetry import TelemetryReading

# Minimum relative change required to persist an HF reading.
_HF_NOISE_FLOOR = 0.005

_last_persisted: dict[tuple[str, str], float] = {}


def flatten_reading(reading: TelemetryReading) -> list[dict]:
    """Flatten reading to rows and mutate sensor.value to the EMA-filtered signal.

    Returned rows exclude HF readings suppressed by the noise-floor dedup.
    """
    loco_id = str(reading.locomotive_id)
    is_hf = reading.sample_rate_hz >= 10.0
    rows: list[dict] = []

    for sensor in reading.sensors:
        sensor_key = sensor.sensor_type.value

        raw_value = sensor.value
        filtered = ema_filter(loco_id, sensor_key, raw_value)

        # Downstream services read the filtered signal through this mutation.
        sensor.value = filtered

        if is_hf:
            dedup_key = (loco_id, sensor_key)
            last = _last_persisted.get(dedup_key)
            if last is not None:
                relative_change = abs(filtered - last) / (abs(last) + 1e-9)
                if relative_change < _HF_NOISE_FLOOR:
                    continue
            _last_persisted[dedup_key] = filtered

        rows.append(
            {
                "time": reading.timestamp,
                "locomotive_id": reading.locomotive_id,
                "locomotive_type": reading.locomotive_type.value,
                "sensor_type": sensor_key,
                "value": raw_value,
                "filtered_value": filtered,
                "unit": sensor.unit,
                "sample_rate_hz": reading.sample_rate_hz,
                "latitude": reading.gps.latitude if reading.gps else None,
                "longitude": reading.gps.longitude if reading.gps else None,
            }
        )

    return rows
