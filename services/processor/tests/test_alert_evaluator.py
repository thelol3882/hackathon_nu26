"""Tests for processor.services.alert_evaluator."""

import uuid
from unittest.mock import patch

import pytest

from processor.services.alert_evaluator import evaluate_alerts
from shared.enums import AlertSeverity, LocomotiveType, SensorType
from shared.schemas.telemetry import SensorPayload

from .conftest import KZ8A_ID, TE33A_ID

# Pydantic rejects uuid_utils.UUID from generate_id(); patch to stdlib.
_FAKE_UUID = uuid.UUID("00000000-0000-0000-0000-ffffffffffff")


@pytest.fixture(autouse=True)
def _mock_generate_id():
    with patch("processor.services.alert_evaluator.generate_id", return_value=_FAKE_UUID):
        yield


def _te33a_nominal_sensors() -> list[SensorPayload]:
    """Full set of TE33A sensors at nominal values."""
    return [
        SensorPayload(sensor_type=SensorType.DIESEL_RPM, value=700.0, unit="rpm"),
        SensorPayload(sensor_type=SensorType.OIL_PRESSURE, value=3.5, unit="bar"),
        SensorPayload(sensor_type=SensorType.COOLANT_TEMP, value=82.0, unit="C"),
        SensorPayload(sensor_type=SensorType.FUEL_LEVEL, value=50.0, unit="%"),
        SensorPayload(sensor_type=SensorType.FUEL_RATE, value=80.0, unit="L/h"),
        SensorPayload(sensor_type=SensorType.TRACTION_MOTOR_TEMP, value=85.0, unit="C"),
        SensorPayload(sensor_type=SensorType.CRANKCASE_PRESSURE, value=0.0, unit="mbar"),
        SensorPayload(sensor_type=SensorType.BRAKE_PIPE_PRESSURE, value=5.1, unit="kgf/cm2"),
        SensorPayload(sensor_type=SensorType.WHEEL_SLIP_RATIO, value=0.0, unit=""),
        SensorPayload(sensor_type=SensorType.SPEED_ACTUAL, value=60.0, unit="km/h"),
    ]


class TestEvaluateAlertsHappy:
    def test_no_alerts_all_nominal(self, make_reading):
        reading = make_reading(sensors=_te33a_nominal_sensors())
        alerts = evaluate_alerts(reading)
        assert alerts == []

    def test_upper_bound_violation_coolant_temp(self, make_reading):
        """coolant_temp = 96 exceeds p_nom(82) + delta_safe(13) = 95."""
        sensors = _te33a_nominal_sensors()
        for s in sensors:
            if s.sensor_type == SensorType.COOLANT_TEMP:
                s.value = 96.0
        reading = make_reading(sensors=sensors)
        alerts = evaluate_alerts(reading)
        sensor_types = [a.sensor_type for a in alerts]
        assert SensorType.COOLANT_TEMP.value in sensor_types

    def test_lower_bound_violation_brake_pipe(self, make_reading):
        """brake_pipe = 4.8 < p_nom(5.1) - delta_safe(0.2) = 4.9."""
        sensors = _te33a_nominal_sensors()
        for s in sensors:
            if s.sensor_type == SensorType.BRAKE_PIPE_PRESSURE:
                s.value = 4.8
        reading = make_reading(sensors=sensors)
        alerts = evaluate_alerts(reading)
        sensor_types = [a.sensor_type for a in alerts]
        assert SensorType.BRAKE_PIPE_PRESSURE.value in sensor_types

    def test_bidirectional_violation(self, make_reading):
        """KZ8A catenary_voltage far from nominal triggers alert."""
        sensors = [
            SensorPayload(sensor_type=SensorType.CATENARY_VOLTAGE, value=20000.0, unit="V"),
            SensorPayload(sensor_type=SensorType.BRAKE_PIPE_PRESSURE, value=5.1, unit="kgf/cm2"),
            SensorPayload(sensor_type=SensorType.WHEEL_SLIP_RATIO, value=0.0, unit=""),
            SensorPayload(sensor_type=SensorType.SPEED_ACTUAL, value=60.0, unit="km/h"),
        ]
        reading = make_reading(
            locomotive_id=KZ8A_ID,
            locomotive_type=LocomotiveType.KZ8A,
            sensors=sensors,
        )
        alerts = evaluate_alerts(reading)
        sensor_types = [a.sensor_type for a in alerts]
        assert SensorType.CATENARY_VOLTAGE.value in sensor_types

    def test_severity_levels(self, make_reading):
        """Crankcase pressure with weight>=35 should yield EMERGENCY."""
        sensors = _te33a_nominal_sensors()
        for s in sensors:
            if s.sensor_type == SensorType.CRANKCASE_PRESSURE:
                s.value = 55.0
        reading = make_reading(sensors=sensors)
        alerts = evaluate_alerts(reading)
        crankcase_alerts = [a for a in alerts if a.sensor_type == SensorType.CRANKCASE_PRESSURE.value]
        assert len(crankcase_alerts) == 1
        assert crankcase_alerts[0].severity == AlertSeverity.EMERGENCY


class TestAESSMasking:
    def test_aess_masking_suppresses_rpm_and_oil(self, make_reading):
        """When RPM=30 (<=50), diesel_rpm and oil_pressure alerts suppressed."""
        sensors = [
            SensorPayload(sensor_type=SensorType.DIESEL_RPM, value=30.0, unit="rpm"),
            SensorPayload(sensor_type=SensorType.OIL_PRESSURE, value=0.5, unit="bar"),
            SensorPayload(sensor_type=SensorType.COOLANT_TEMP, value=82.0, unit="C"),
            SensorPayload(sensor_type=SensorType.BRAKE_PIPE_PRESSURE, value=5.1, unit="kgf/cm2"),
            SensorPayload(sensor_type=SensorType.CRANKCASE_PRESSURE, value=0.0, unit="mbar"),
            SensorPayload(sensor_type=SensorType.WHEEL_SLIP_RATIO, value=0.0, unit=""),
            SensorPayload(sensor_type=SensorType.SPEED_ACTUAL, value=0.0, unit="km/h"),
        ]
        reading = make_reading(sensors=sensors)
        alerts = evaluate_alerts(reading)
        sensor_types = {a.sensor_type for a in alerts}
        assert SensorType.DIESEL_RPM.value not in sensor_types
        assert SensorType.OIL_PRESSURE.value not in sensor_types

    def test_aess_not_active_above_threshold(self, make_reading):
        """RPM=100 means AESS not active -> oil_pressure alerts still fire."""
        sensors = [
            SensorPayload(sensor_type=SensorType.DIESEL_RPM, value=100.0, unit="rpm"),
            SensorPayload(sensor_type=SensorType.OIL_PRESSURE, value=0.5, unit="bar"),
            SensorPayload(sensor_type=SensorType.COOLANT_TEMP, value=82.0, unit="C"),
            SensorPayload(sensor_type=SensorType.BRAKE_PIPE_PRESSURE, value=5.1, unit="kgf/cm2"),
            SensorPayload(sensor_type=SensorType.CRANKCASE_PRESSURE, value=0.0, unit="mbar"),
            SensorPayload(sensor_type=SensorType.WHEEL_SLIP_RATIO, value=0.0, unit=""),
            SensorPayload(sensor_type=SensorType.SPEED_ACTUAL, value=60.0, unit="km/h"),
        ]
        reading = make_reading(sensors=sensors)
        alerts = evaluate_alerts(reading)
        sensor_types = {a.sensor_type for a in alerts}
        assert SensorType.OIL_PRESSURE.value in sensor_types

    def test_aess_only_te33a_not_kz8a(self, make_reading):
        """AESS masking only applies to TE33A, not KZ8A."""
        sensors = [
            SensorPayload(sensor_type=SensorType.CATENARY_VOLTAGE, value=25000.0, unit="V"),
            SensorPayload(sensor_type=SensorType.BRAKE_PIPE_PRESSURE, value=4.0, unit="kgf/cm2"),
            SensorPayload(sensor_type=SensorType.WHEEL_SLIP_RATIO, value=0.0, unit=""),
            SensorPayload(sensor_type=SensorType.SPEED_ACTUAL, value=60.0, unit="km/h"),
        ]
        reading = make_reading(
            locomotive_id=KZ8A_ID,
            locomotive_type=LocomotiveType.KZ8A,
            sensors=sensors,
        )
        alerts = evaluate_alerts(reading)
        sensor_types = {a.sensor_type for a in alerts}
        assert SensorType.BRAKE_PIPE_PRESSURE.value in sensor_types

    def test_rpm_exactly_50_aess_active(self, make_reading):
        """RPM exactly at threshold (<=50) means AESS is active."""
        sensors = [
            SensorPayload(sensor_type=SensorType.DIESEL_RPM, value=50.0, unit="rpm"),
            SensorPayload(sensor_type=SensorType.OIL_PRESSURE, value=0.5, unit="bar"),
            SensorPayload(sensor_type=SensorType.COOLANT_TEMP, value=82.0, unit="C"),
            SensorPayload(sensor_type=SensorType.BRAKE_PIPE_PRESSURE, value=5.1, unit="kgf/cm2"),
            SensorPayload(sensor_type=SensorType.CRANKCASE_PRESSURE, value=0.0, unit="mbar"),
            SensorPayload(sensor_type=SensorType.WHEEL_SLIP_RATIO, value=0.0, unit=""),
            SensorPayload(sensor_type=SensorType.SPEED_ACTUAL, value=0.0, unit="km/h"),
        ]
        reading = make_reading(sensors=sensors)
        alerts = evaluate_alerts(reading)
        sensor_types = {a.sensor_type for a in alerts}
        assert SensorType.DIESEL_RPM.value not in sensor_types
        assert SensorType.OIL_PRESSURE.value not in sensor_types


class TestOilPressureContextual:
    def test_oil_pressure_contextual_acceptable(self, make_reading):
        """Low RPM: oil pressure 2.0 bar exceeds min_expected (~1.64), no alert."""
        sensors = [
            SensorPayload(sensor_type=SensorType.DIESEL_RPM, value=100.0, unit="rpm"),
            SensorPayload(sensor_type=SensorType.OIL_PRESSURE, value=2.0, unit="bar"),
            SensorPayload(sensor_type=SensorType.COOLANT_TEMP, value=82.0, unit="C"),
            SensorPayload(sensor_type=SensorType.BRAKE_PIPE_PRESSURE, value=5.1, unit="kgf/cm2"),
            SensorPayload(sensor_type=SensorType.CRANKCASE_PRESSURE, value=0.0, unit="mbar"),
            SensorPayload(sensor_type=SensorType.WHEEL_SLIP_RATIO, value=0.0, unit=""),
            SensorPayload(sensor_type=SensorType.SPEED_ACTUAL, value=60.0, unit="km/h"),
        ]
        reading = make_reading(sensors=sensors)
        alerts = evaluate_alerts(reading)
        sensor_types = {a.sensor_type for a in alerts}
        assert SensorType.OIL_PRESSURE.value not in sensor_types

    def test_oil_pressure_low_for_high_rpm(self, make_reading):
        """High RPM: 2.0 bar is below min_expected (~2.79), threshold check runs."""
        sensors = [
            SensorPayload(sensor_type=SensorType.DIESEL_RPM, value=900.0, unit="rpm"),
            SensorPayload(sensor_type=SensorType.OIL_PRESSURE, value=2.0, unit="bar"),
            SensorPayload(sensor_type=SensorType.COOLANT_TEMP, value=82.0, unit="C"),
            SensorPayload(sensor_type=SensorType.BRAKE_PIPE_PRESSURE, value=5.1, unit="kgf/cm2"),
            SensorPayload(sensor_type=SensorType.CRANKCASE_PRESSURE, value=0.0, unit="mbar"),
            SensorPayload(sensor_type=SensorType.WHEEL_SLIP_RATIO, value=0.0, unit=""),
            SensorPayload(sensor_type=SensorType.SPEED_ACTUAL, value=60.0, unit="km/h"),
        ]
        reading = make_reading(sensors=sensors)
        alerts = evaluate_alerts(reading)
        sensor_types = {a.sensor_type for a in alerts}
        assert SensorType.OIL_PRESSURE.value in sensor_types


class TestEvaluateAlertsEdge:
    def test_sensor_not_in_specs_ignored(self, make_reading):
        """A sensor type not in LOCO_SPECS should produce no alerts."""
        sensors = [
            SensorPayload(sensor_type=SensorType.RECUPERATION_CURRENT, value=999.0, unit="A"),
        ]
        reading = make_reading(sensors=sensors)
        alerts = evaluate_alerts(reading)
        assert alerts == []

    def test_empty_sensors(self, make_reading):
        reading = make_reading(sensors=[])
        alerts = evaluate_alerts(reading)
        assert alerts == []

    def test_crankcase_emergency_weight_ge_35(self, make_reading):
        """Crankcase weight>=35 always yields EMERGENCY on violation."""
        sensors = _te33a_nominal_sensors()
        for s in sensors:
            if s.sensor_type == SensorType.CRANKCASE_PRESSURE:
                s.value = 15.0
        reading = make_reading(sensors=sensors)
        alerts = evaluate_alerts(reading)
        crankcase_alerts = [a for a in alerts if a.sensor_type == SensorType.CRANKCASE_PRESSURE.value]
        assert len(crankcase_alerts) == 1
        assert crankcase_alerts[0].severity == AlertSeverity.EMERGENCY


class TestAlertFields:
    def test_alert_fields_populated(self, make_reading):
        sensors = _te33a_nominal_sensors()
        for s in sensors:
            if s.sensor_type == SensorType.COOLANT_TEMP:
                s.value = 96.0
        reading = make_reading(sensors=sensors)
        alerts = evaluate_alerts(reading)
        coolant_alerts = [a for a in alerts if a.sensor_type == SensorType.COOLANT_TEMP.value]
        assert len(coolant_alerts) == 1
        alert = coolant_alerts[0]
        assert alert.id is not None
        assert alert.locomotive_id == TE33A_ID
        assert alert.sensor_type == SensorType.COOLANT_TEMP.value
        assert alert.severity is not None
        assert alert.value == pytest.approx(96.0)
        assert alert.threshold_min is not None
        assert alert.threshold_max is not None
        assert alert.message is not None
        assert alert.timestamp is not None
        assert alert.acknowledged is False

    def test_message_format(self, make_reading):
        sensors = _te33a_nominal_sensors()
        for s in sensors:
            if s.sensor_type == SensorType.COOLANT_TEMP:
                s.value = 96.0
        reading = make_reading(sensors=sensors)
        alerts = evaluate_alerts(reading)
        coolant_alerts = [a for a in alerts if a.sensor_type == SensorType.COOLANT_TEMP.value]
        msg = coolant_alerts[0].message
        assert "TE33A" in msg
        assert "96.00" in msg
        # Range uses en-dash.
        assert "\u2013" in msg
