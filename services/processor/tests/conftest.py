"""Shared fixtures for processor tests."""

from datetime import UTC, datetime
from uuid import UUID

import pytest

from shared.enums import LocomotiveType, SensorType
from shared.schemas.telemetry import GPSCoordinate, SensorPayload, TelemetryReading

# Fixed UUIDs for deterministic tests
TE33A_ID = UUID("00000000-0000-0000-0000-000000000001")
KZ8A_ID = UUID("00000000-0000-0000-0000-000000000002")


@pytest.fixture(autouse=True)
def _clear_module_state():
    """Clear all module-level dicts before AND after each test."""
    import processor.services.filter_service as fs
    import processor.services.health_service as hs
    import processor.services.ingestion_service as ings

    fs._ema_state.clear()
    ings._last_persisted.clear()
    hs._damage_state.clear()

    yield

    fs._ema_state.clear()
    ings._last_persisted.clear()
    hs._damage_state.clear()


@pytest.fixture
def make_sensor():
    """Factory for SensorPayload objects."""

    def _make(
        sensor_type: SensorType,
        value: float,
        unit: str = "",
    ) -> SensorPayload:
        return SensorPayload(sensor_type=sensor_type, value=value, unit=unit)

    return _make


@pytest.fixture
def make_reading(make_sensor):
    """Factory for TelemetryReading objects."""

    def _make(
        locomotive_id: UUID = TE33A_ID,
        locomotive_type: LocomotiveType = LocomotiveType.TE33A,
        sensors: list[SensorPayload] | None = None,
        sample_rate_hz: float = 1.0,
        gps: GPSCoordinate | None = None,
    ) -> TelemetryReading:
        return TelemetryReading(
            locomotive_id=locomotive_id,
            locomotive_type=locomotive_type,
            timestamp=datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC),
            sample_rate_hz=sample_rate_hz,
            gps=gps,
            sensors=sensors or [],
        )

    return _make
