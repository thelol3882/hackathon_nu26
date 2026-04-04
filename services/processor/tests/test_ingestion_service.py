"""Tests for processor.services.ingestion_service (flatten_reading)."""

import pytest

from processor.services.ingestion_service import flatten_reading
from shared.enums import LocomotiveType, SensorType
from shared.schemas.telemetry import GPSCoordinate

from .conftest import KZ8A_ID, TE33A_ID

# ── Happy path ──────────────────────────────────────────────────────────────


class TestFlattenReadingHappy:
    def test_single_sensor_low_freq(self, make_reading, make_sensor):
        sensors = [make_sensor(SensorType.COOLANT_TEMP, 82.0, "C")]
        reading = make_reading(sensors=sensors, sample_rate_hz=1.0)
        rows = flatten_reading(reading)
        assert len(rows) == 1
        row = rows[0]
        assert row.sensor_type == SensorType.COOLANT_TEMP.value
        assert row.unit == "C"

    def test_multiple_sensors(self, make_reading, make_sensor):
        sensors = [
            make_sensor(SensorType.COOLANT_TEMP, 82.0, "C"),
            make_sensor(SensorType.DIESEL_RPM, 700.0, "rpm"),
            make_sensor(SensorType.OIL_PRESSURE, 3.5, "bar"),
        ]
        reading = make_reading(sensors=sensors)
        rows = flatten_reading(reading)
        assert len(rows) == 3

    def test_gps_propagated(self, make_reading, make_sensor):
        gps = GPSCoordinate(latitude=51.1, longitude=71.4)
        sensors = [make_sensor(SensorType.COOLANT_TEMP, 82.0, "C")]
        reading = make_reading(sensors=sensors, gps=gps)
        rows = flatten_reading(reading)
        assert rows[0].latitude == pytest.approx(51.1)
        assert rows[0].longitude == pytest.approx(71.4)

    def test_gps_none_sets_null(self, make_reading, make_sensor):
        sensors = [make_sensor(SensorType.COOLANT_TEMP, 82.0, "C")]
        reading = make_reading(sensors=sensors, gps=None)
        rows = flatten_reading(reading)
        assert rows[0].latitude is None
        assert rows[0].longitude is None

    def test_hf_first_reading_always_persisted(self, make_reading, make_sensor):
        sensors = [make_sensor(SensorType.CATENARY_VOLTAGE, 25000.0, "V")]
        reading = make_reading(
            locomotive_id=KZ8A_ID,
            locomotive_type=LocomotiveType.KZ8A,
            sensors=sensors,
            sample_rate_hz=50.0,
        )
        rows = flatten_reading(reading)
        assert len(rows) == 1

    def test_hf_significant_change_persisted(self, make_reading, make_sensor):
        """A change of >0.5% should be persisted even at HF."""
        sensors1 = [make_sensor(SensorType.CATENARY_VOLTAGE, 25000.0, "V")]
        reading1 = make_reading(
            locomotive_id=KZ8A_ID,
            locomotive_type=LocomotiveType.KZ8A,
            sensors=sensors1,
            sample_rate_hz=50.0,
        )
        flatten_reading(reading1)

        # Second reading with a big change (>0.5%)
        sensors2 = [make_sensor(SensorType.CATENARY_VOLTAGE, 26000.0, "V")]
        reading2 = make_reading(
            locomotive_id=KZ8A_ID,
            locomotive_type=LocomotiveType.KZ8A,
            sensors=sensors2,
            sample_rate_hz=50.0,
        )
        rows = flatten_reading(reading2)
        assert len(rows) == 1


# ── Edge cases ──────────────────────────────────────────────────────────────


class TestFlattenReadingEdge:
    def test_hf_dedup_skips_unchanged(self, make_reading, make_sensor):
        """Same value at 50Hz -> second returns 0 rows (dedup)."""
        sensors = [make_sensor(SensorType.CATENARY_VOLTAGE, 25000.0, "V")]
        reading = make_reading(
            locomotive_id=KZ8A_ID,
            locomotive_type=LocomotiveType.KZ8A,
            sensors=sensors,
            sample_rate_hz=50.0,
        )
        rows1 = flatten_reading(reading)
        assert len(rows1) == 1

        # Same value -> EMA converges, relative change < 0.5%
        sensors2 = [make_sensor(SensorType.CATENARY_VOLTAGE, 25000.0, "V")]
        reading2 = make_reading(
            locomotive_id=KZ8A_ID,
            locomotive_type=LocomotiveType.KZ8A,
            sensors=sensors2,
            sample_rate_hz=50.0,
        )
        rows2 = flatten_reading(reading2)
        assert len(rows2) == 0

    def test_low_freq_no_dedup(self, make_reading, make_sensor):
        """At 1Hz, even identical values are always persisted (no dedup)."""
        sensors = [make_sensor(SensorType.COOLANT_TEMP, 82.0, "C")]
        reading = make_reading(sensors=sensors, sample_rate_hz=1.0)
        flatten_reading(reading)

        sensors2 = [make_sensor(SensorType.COOLANT_TEMP, 82.0, "C")]
        reading2 = make_reading(sensors=sensors2, sample_rate_hz=1.0)
        rows = flatten_reading(reading2)
        assert len(rows) == 1

    def test_sample_rate_9_99_not_hf(self, make_reading, make_sensor):
        sensors = [make_sensor(SensorType.COOLANT_TEMP, 82.0, "C")]
        reading = make_reading(sensors=sensors, sample_rate_hz=9.99)
        flatten_reading(reading)

        # Same value second time - should still persist (not HF)
        sensors2 = [make_sensor(SensorType.COOLANT_TEMP, 82.0, "C")]
        reading2 = make_reading(sensors=sensors2, sample_rate_hz=9.99)
        rows = flatten_reading(reading2)
        assert len(rows) == 1

    def test_sample_rate_10_is_hf(self, make_reading, make_sensor):
        sensors = [make_sensor(SensorType.CATENARY_VOLTAGE, 25000.0, "V")]
        reading = make_reading(
            locomotive_id=KZ8A_ID,
            locomotive_type=LocomotiveType.KZ8A,
            sensors=sensors,
            sample_rate_hz=10.0,
        )
        flatten_reading(reading)

        # Same value -> dedup should kick in
        sensors2 = [make_sensor(SensorType.CATENARY_VOLTAGE, 25000.0, "V")]
        reading2 = make_reading(
            locomotive_id=KZ8A_ID,
            locomotive_type=LocomotiveType.KZ8A,
            sensors=sensors2,
            sample_rate_hz=10.0,
        )
        rows = flatten_reading(reading2)
        assert len(rows) == 0

    def test_empty_sensors(self, make_reading):
        reading = make_reading(sensors=[])
        rows = flatten_reading(reading)
        assert rows == []

    def test_hf_threshold_boundary(self, make_reading, make_sensor):
        """A change of exactly the noise floor boundary."""
        # Seed with first reading
        sensors1 = [make_sensor(SensorType.CATENARY_VOLTAGE, 10000.0, "V")]
        reading1 = make_reading(
            locomotive_id=KZ8A_ID,
            locomotive_type=LocomotiveType.KZ8A,
            sensors=sensors1,
            sample_rate_hz=50.0,
        )
        flatten_reading(reading1)
        # The persisted value is 10000.0 (cold start)
        # Now send a value that after EMA is just barely above 0.5% change
        # EMA gain for catenary_voltage = 0.30
        # filtered = 0.30 * new + 0.70 * 10000 = 0.30*new + 7000
        # We need |filtered - 10000| / (10000 + 1e-9) >= 0.005
        # |0.30*new - 3000| / 10000 >= 0.005
        # |0.30*new - 3000| >= 50
        # 0.30*new >= 3050 -> new >= 10166.67
        sensors2 = [make_sensor(SensorType.CATENARY_VOLTAGE, 10200.0, "V")]
        reading2 = make_reading(
            locomotive_id=KZ8A_ID,
            locomotive_type=LocomotiveType.KZ8A,
            sensors=sensors2,
            sample_rate_hz=50.0,
        )
        rows = flatten_reading(reading2)
        assert len(rows) == 1  # should persist because change exceeds floor


# ── Key behavioral checks ──────────────────────────────────────────────────


class TestFlattenReadingKeyBehavior:
    def test_sensor_value_mutated_to_filtered(self, make_reading, make_sensor):
        """Verify sensor.value is replaced with the EMA-filtered value."""
        sensor = make_sensor(SensorType.COOLANT_TEMP, 82.0, "C")
        reading = make_reading(sensors=[sensor])
        flatten_reading(reading)
        # First call -> cold start, filtered == raw
        assert sensor.value == pytest.approx(82.0)

        # Second reading with different raw
        sensor2 = make_sensor(SensorType.COOLANT_TEMP, 90.0, "C")
        reading2 = make_reading(sensors=[sensor2])
        flatten_reading(reading2)
        # sensor2.value should now be the EMA-filtered value, not 90.0
        assert sensor2.value != pytest.approx(90.0)

    def test_record_raw_and_filtered_values(self, make_reading, make_sensor):
        """TelemetryRecord.value should be raw, filtered_value should be filtered."""
        sensor = make_sensor(SensorType.COOLANT_TEMP, 82.0, "C")
        reading = make_reading(sensors=[sensor])
        flatten_reading(reading)

        sensor2 = make_sensor(SensorType.COOLANT_TEMP, 90.0, "C")
        reading2 = make_reading(sensors=[sensor2])
        rows = flatten_reading(reading2)
        row = rows[0]
        assert row.value == pytest.approx(90.0)  # raw value
        assert row.filtered_value != pytest.approx(90.0)  # EMA-smoothed
        assert row.filtered_value == pytest.approx(sensor2.value)  # mutated

    def test_record_fields_populated(self, make_reading, make_sensor):
        gps = GPSCoordinate(latitude=51.1, longitude=71.4)
        sensors = [make_sensor(SensorType.DIESEL_RPM, 700.0, "rpm")]
        reading = make_reading(sensors=sensors, gps=gps, sample_rate_hz=1.0)
        rows = flatten_reading(reading)
        row = rows[0]
        assert row.locomotive_id == TE33A_ID
        assert row.locomotive_type == LocomotiveType.TE33A.value
        assert row.sensor_type == SensorType.DIESEL_RPM.value
        assert row.sample_rate_hz == 1.0
        assert row.time == reading.timestamp
