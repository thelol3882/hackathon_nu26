"""Tests for processor.services.filter_service (EMA filter)."""

import pytest

from processor.services.filter_service import _ema_state, ema_filter, reset_filter
from shared.constants import EMA_GAINS
from shared.enums import SensorType

LOCO_A = "loco-a"
LOCO_B = "loco-b"


class TestEmaFilterHappy:
    def test_cold_start_returns_raw(self):
        result = ema_filter(LOCO_A, SensorType.COOLANT_TEMP, 82.0)
        assert result == 82.0

    def test_second_call_applies_gain(self):
        ema_filter(LOCO_A, SensorType.COOLANT_TEMP, 80.0)
        result = ema_filter(LOCO_A, SensorType.COOLANT_TEMP, 90.0)
        gain = EMA_GAINS[SensorType.COOLANT_TEMP]
        expected = gain * 90.0 + (1.0 - gain) * 80.0
        assert result == pytest.approx(expected)

    def test_uses_default_gain_for_unknown_sensor(self):
        ema_filter(LOCO_A, "unknown_sensor", 100.0)
        result = ema_filter(LOCO_A, "unknown_sensor", 200.0)
        default_gain = EMA_GAINS["__default__"]
        expected = default_gain * 200.0 + (1.0 - default_gain) * 100.0
        assert result == pytest.approx(expected)

    def test_converges_over_many_calls(self):
        target = 95.0
        ema_filter(LOCO_A, SensorType.COOLANT_TEMP, 70.0)
        for _ in range(50):
            val = ema_filter(LOCO_A, SensorType.COOLANT_TEMP, target)
        assert val == pytest.approx(target, abs=1.0)

    def test_separate_state_per_locomotive(self):
        ema_filter(LOCO_A, SensorType.DIESEL_RPM, 500.0)
        ema_filter(LOCO_B, SensorType.DIESEL_RPM, 800.0)
        result_a = ema_filter(LOCO_A, SensorType.DIESEL_RPM, 600.0)
        gain = EMA_GAINS[SensorType.DIESEL_RPM]
        expected_a = gain * 600.0 + (1.0 - gain) * 500.0
        assert result_a == pytest.approx(expected_a)

    def test_separate_state_per_sensor(self):
        ema_filter(LOCO_A, SensorType.COOLANT_TEMP, 80.0)
        ema_filter(LOCO_A, SensorType.DIESEL_RPM, 700.0)
        ema_filter(LOCO_A, SensorType.COOLANT_TEMP, 90.0)
        result_rpm = ema_filter(LOCO_A, SensorType.DIESEL_RPM, 750.0)
        gain_rpm = EMA_GAINS[SensorType.DIESEL_RPM]
        expected = gain_rpm * 750.0 + (1.0 - gain_rpm) * 700.0
        assert result_rpm == pytest.approx(expected)

    def test_reset_specific_sensor(self):
        ema_filter(LOCO_A, SensorType.COOLANT_TEMP, 80.0)
        ema_filter(LOCO_A, SensorType.DIESEL_RPM, 700.0)
        reset_filter(LOCO_A, SensorType.COOLANT_TEMP)
        result = ema_filter(LOCO_A, SensorType.COOLANT_TEMP, 95.0)
        assert result == 95.0
        assert (LOCO_A, SensorType.DIESEL_RPM) in _ema_state

    def test_reset_all_sensors_for_loco(self):
        ema_filter(LOCO_A, SensorType.COOLANT_TEMP, 80.0)
        ema_filter(LOCO_A, SensorType.DIESEL_RPM, 700.0)
        ema_filter(LOCO_B, SensorType.COOLANT_TEMP, 85.0)
        reset_filter(LOCO_A)
        assert not any(k[0] == LOCO_A for k in _ema_state)
        assert (LOCO_B, SensorType.COOLANT_TEMP) in _ema_state


class TestEmaFilterEdge:
    def test_zero_raw_value(self):
        result = ema_filter(LOCO_A, SensorType.DIESEL_RPM, 0.0)
        assert result == 0.0

    def test_negative_value(self):
        result = ema_filter(LOCO_A, SensorType.COOLANT_TEMP, -40.0)
        assert result == -40.0

    def test_very_large_value(self):
        ema_filter(LOCO_A, SensorType.CATENARY_VOLTAGE, 25_000.0)
        result = ema_filter(LOCO_A, SensorType.CATENARY_VOLTAGE, 1e12)
        gain = EMA_GAINS[SensorType.CATENARY_VOLTAGE]
        expected = gain * 1e12 + (1.0 - gain) * 25_000.0
        assert result == pytest.approx(expected)

    def test_gain_boundaries_different_results(self):
        """Higher gain tracks raw values more closely."""
        ema_filter(LOCO_A, SensorType.COOLANT_TEMP, 50.0)
        result_slow = ema_filter(LOCO_A, SensorType.COOLANT_TEMP, 100.0)
        ema_filter(LOCO_A, SensorType.DC_LINK_VOLTAGE, 50.0)
        result_fast = ema_filter(LOCO_A, SensorType.DC_LINK_VOLTAGE, 100.0)

        assert result_slow != pytest.approx(result_fast)
        assert abs(result_fast - 100.0) < abs(result_slow - 100.0)


class TestEmaFilterNegative:
    def test_reset_nonexistent_key_no_error(self):
        reset_filter(LOCO_A, SensorType.COOLANT_TEMP)

    def test_reset_nonexistent_loco_no_error(self):
        reset_filter("nonexistent-loco")
