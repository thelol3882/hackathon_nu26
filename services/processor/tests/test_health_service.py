"""Tests for processor.services.health_service (Health Index + Montsinger)."""

import pytest

from processor.services.health_service import (
    calculate_health,
    get_damage_state,
)
from shared.enums import LocomotiveType, SensorType
from shared.schemas.telemetry import SensorPayload

from .conftest import KZ8A_ID, TE33A_ID


def _te33a_nominal_sensors() -> list[SensorPayload]:
    """All TE33A sensors at nominal values (penalty ~0)."""
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


def _kz8a_nominal_sensors() -> list[SensorPayload]:
    """All KZ8A sensors at nominal values."""
    return [
        SensorPayload(sensor_type=SensorType.CATENARY_VOLTAGE, value=25000.0, unit="V"),
        SensorPayload(sensor_type=SensorType.PANTOGRAPH_CURRENT, value=200.0, unit="A"),
        SensorPayload(sensor_type=SensorType.TRANSFORMER_TEMP, value=65.0, unit="C"),
        SensorPayload(sensor_type=SensorType.IGBT_TEMP, value=57.0, unit="C"),
        SensorPayload(sensor_type=SensorType.RECUPERATION_CURRENT, value=100.0, unit="A"),
        SensorPayload(sensor_type=SensorType.DC_LINK_VOLTAGE, value=2800.0, unit="V"),
        SensorPayload(sensor_type=SensorType.BRAKE_PIPE_PRESSURE, value=5.1, unit="kgf/cm2"),
        SensorPayload(sensor_type=SensorType.WHEEL_SLIP_RATIO, value=0.0, unit=""),
        SensorPayload(sensor_type=SensorType.SPEED_ACTUAL, value=60.0, unit="km/h"),
    ]


# ── Happy path: score & category ────────────────────────────────────────────


class TestHealthScoreHappy:
    def test_perfect_health_all_nominal(self, make_reading):
        reading = make_reading(sensors=_te33a_nominal_sensors())
        hi = calculate_health(reading)
        assert hi.overall_score >= 99.0
        assert hi.category == "\u041d\u043e\u0440\u043c\u0430"

    def test_category_norma(self, make_reading):
        reading = make_reading(sensors=_te33a_nominal_sensors())
        hi = calculate_health(reading)
        assert hi.overall_score >= 80.0
        assert hi.category == "\u041d\u043e\u0440\u043c\u0430"

    def test_category_vnimanie(self, make_reading):
        """A moderately degraded reading should yield 'Внимание' (50-79)."""
        sensors = _te33a_nominal_sensors()
        for s in sensors:
            if s.sensor_type == SensorType.COOLANT_TEMP:
                s.value = 95.5  # just over p_nom + delta_safe
            if s.sensor_type == SensorType.CRANKCASE_PRESSURE:
                s.value = 25.0  # moderate deviation
        reading = make_reading(sensors=sensors)
        hi = calculate_health(reading)
        assert 50.0 <= hi.overall_score < 80.0
        assert hi.category == "\u0412\u043d\u0438\u043c\u0430\u043d\u0438\u0435"

    def test_category_kritichno(self, make_reading):
        """Extreme values should yield 'Критично' (<50)."""
        sensors = _te33a_nominal_sensors()
        for s in sensors:
            if s.sensor_type == SensorType.CRANKCASE_PRESSURE:
                s.value = 55.0  # far above critical, weight=40
            if s.sensor_type == SensorType.BRAKE_PIPE_PRESSURE:
                s.value = 1.0  # far below critical, weight=40
        reading = make_reading(sensors=sensors)
        hi = calculate_health(reading)
        assert hi.overall_score < 50.0
        assert hi.category == "\u041a\u0440\u0438\u0442\u0438\u0447\u043d\u043e"


# ── Top factors ─────────────────────────────────────────────────────────────


class TestTopFactors:
    def test_top_factors_limited_to_5(self, make_reading):
        """Even with many degraded sensors, only 5 factors returned."""
        sensors = _te33a_nominal_sensors()
        # Push many sensors out of safe zone
        for s in sensors:
            if s.sensor_type == SensorType.COOLANT_TEMP:
                s.value = 96.0
            if s.sensor_type == SensorType.CRANKCASE_PRESSURE:
                s.value = 20.0
            if s.sensor_type == SensorType.BRAKE_PIPE_PRESSURE:
                s.value = 4.0
            if s.sensor_type == SensorType.WHEEL_SLIP_RATIO:
                s.value = 0.2
            if s.sensor_type == SensorType.DIESEL_RPM:
                s.value = 950.0
            if s.sensor_type == SensorType.OIL_PRESSURE:
                s.value = 2.0
        reading = make_reading(sensors=sensors)
        hi = calculate_health(reading)
        assert len(hi.top_factors) <= 5

    def test_top_factors_sorted_by_penalty(self, make_reading):
        sensors = _te33a_nominal_sensors()
        for s in sensors:
            if s.sensor_type == SensorType.CRANKCASE_PRESSURE:
                s.value = 40.0  # high weight, big deviation
            if s.sensor_type == SensorType.COOLANT_TEMP:
                s.value = 96.0  # moderate
        reading = make_reading(sensors=sensors)
        hi = calculate_health(reading)
        penalties = [f.penalty for f in hi.top_factors]
        assert penalties == sorted(penalties, reverse=True)

    def test_contribution_pct(self, make_reading):
        """Contribution percentages should sum to ~100% for the top factors if they cover all penalties."""
        sensors = _te33a_nominal_sensors()
        for s in sensors:
            if s.sensor_type == SensorType.CRANKCASE_PRESSURE:
                s.value = 30.0
        reading = make_reading(sensors=sensors)
        hi = calculate_health(reading)
        # If there's only one non-zero penalty factor, its contribution should be ~100%
        nonzero = [f for f in hi.top_factors if f.penalty > 0]
        if len(nonzero) == 1:
            assert nonzero[0].contribution_pct == pytest.approx(100.0, abs=0.1)


# ── Montsinger aging ────────────────────────────────────────────────────────


class TestMontsinger:
    def test_montsinger_accumulates(self, make_reading):
        """KZ8A transformer_temp above ref (65) should accumulate damage."""
        sensors = _kz8a_nominal_sensors()
        for s in sensors:
            if s.sensor_type == SensorType.TRANSFORMER_TEMP:
                s.value = 77.0  # 12 degrees above ref=65
        reading = make_reading(
            locomotive_id=KZ8A_ID,
            locomotive_type=LocomotiveType.KZ8A,
            sensors=sensors,
        )
        hi = calculate_health(reading)
        assert hi.damage_penalty > 0.0

    def test_montsinger_no_damage_below_ref(self, make_reading):
        """At or below ref temp, no damage accumulates."""
        sensors = _kz8a_nominal_sensors()
        for s in sensors:
            if s.sensor_type == SensorType.TRANSFORMER_TEMP:
                s.value = 60.0  # below ref=65
            if s.sensor_type == SensorType.IGBT_TEMP:
                s.value = 50.0  # below ref=57
        reading = make_reading(
            locomotive_id=KZ8A_ID,
            locomotive_type=LocomotiveType.KZ8A,
            sensors=sensors,
        )
        hi = calculate_health(reading)
        assert hi.damage_penalty == pytest.approx(0.0)

    def test_damage_persists_across_calls(self, make_reading):
        """Calling calculate_health twice should accumulate damage."""
        sensors = _kz8a_nominal_sensors()
        for s in sensors:
            if s.sensor_type == SensorType.TRANSFORMER_TEMP:
                s.value = 77.0
        reading = make_reading(
            locomotive_id=KZ8A_ID,
            locomotive_type=LocomotiveType.KZ8A,
            sensors=sensors,
        )
        hi1 = calculate_health(reading)
        dmg1 = hi1.damage_penalty

        # Second call with same overtemp
        sensors2 = _kz8a_nominal_sensors()
        for s in sensors2:
            if s.sensor_type == SensorType.TRANSFORMER_TEMP:
                s.value = 77.0
        reading2 = make_reading(
            locomotive_id=KZ8A_ID,
            locomotive_type=LocomotiveType.KZ8A,
            sensors=sensors2,
        )
        hi2 = calculate_health(reading2)
        assert hi2.damage_penalty > dmg1


# ── Edge cases ──────────────────────────────────────────────────────────────


class TestHealthEdge:
    def test_score_clamped_to_zero(self, make_reading):
        """Extreme penalty values should clamp score to 0, not go negative."""
        sensors = _te33a_nominal_sensors()
        for s in sensors:
            if s.sensor_type == SensorType.CRANKCASE_PRESSURE:
                s.value = 200.0  # extreme
            if s.sensor_type == SensorType.BRAKE_PIPE_PRESSURE:
                s.value = 0.0  # extreme
        reading = make_reading(sensors=sensors)
        hi = calculate_health(reading)
        assert hi.overall_score >= 0.0

    def test_score_clamped_to_100(self, make_reading):
        """Nominal readings cannot produce score > 100."""
        reading = make_reading(sensors=_te33a_nominal_sensors())
        hi = calculate_health(reading)
        assert hi.overall_score <= 100.0

    def test_no_sensors_returns_100_empty_factors(self, make_reading):
        reading = make_reading(sensors=[])
        hi = calculate_health(reading)
        assert hi.overall_score == pytest.approx(100.0)
        assert hi.top_factors == []

    def test_sensors_not_in_specs_ignored(self, make_reading):
        """Sensors not in LOCO_SPECS for the type are simply skipped."""
        # recuperation_current is not in TE33A specs
        sensors = [
            SensorPayload(sensor_type=SensorType.RECUPERATION_CURRENT, value=999.0, unit="A"),
        ]
        reading = make_reading(sensors=sensors)
        hi = calculate_health(reading)
        assert hi.overall_score == pytest.approx(100.0)
        assert hi.top_factors == []


# ── Diagnostic ──────────────────────────────────────────────────────────────


class TestGetDamageState:
    def test_get_damage_state_returns_dict(self, make_reading):
        sensors = _kz8a_nominal_sensors()
        for s in sensors:
            if s.sensor_type == SensorType.TRANSFORMER_TEMP:
                s.value = 77.0
        reading = make_reading(
            locomotive_id=KZ8A_ID,
            locomotive_type=LocomotiveType.KZ8A,
            sensors=sensors,
        )
        calculate_health(reading)
        state = get_damage_state(str(KZ8A_ID))
        assert isinstance(state, dict)
        assert SensorType.TRANSFORMER_TEMP.value in state
        assert state[SensorType.TRANSFORMER_TEMP.value] > 0.0

    def test_get_damage_state_empty_for_unknown_loco(self):
        state = get_damage_state("nonexistent")
        assert state == {}


# ── Fields completeness ─────────────────────────────────────────────────────


class TestHealthIndexFields:
    def test_health_index_fields_complete(self, make_reading):
        reading = make_reading(sensors=_te33a_nominal_sensors())
        hi = calculate_health(reading)
        assert hi.locomotive_id == TE33A_ID
        assert hi.locomotive_type == LocomotiveType.TE33A.value
        assert hi.overall_score is not None
        assert hi.category in (
            "\u041d\u043e\u0440\u043c\u0430",
            "\u0412\u043d\u0438\u043c\u0430\u043d\u0438\u0435",
            "\u041a\u0440\u0438\u0442\u0438\u0447\u043d\u043e",
        )
        assert isinstance(hi.top_factors, list)
        assert hi.damage_penalty is not None
        assert hi.calculated_at is not None
