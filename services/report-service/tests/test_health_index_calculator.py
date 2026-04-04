"""Tests for report_service.services.health_index_calculator."""

from report_service.services.health_index_calculator import (
    calculate_component_score,
    calculate_overall_score,
)
from shared.constants import DEFAULT_THRESHOLDS, HEALTH_WEIGHTS
from shared.schemas.health import ComponentHealth

# ── Component score tests ─────────────────────────────────────────────────────


class TestCalculateComponentScore:
    def test_component_at_midpoint(self):
        """Value exactly at midpoint -> score = 1.0."""
        # coolant_temp: (70, 95) -> midpoint = 82.5
        result = calculate_component_score("coolant_temp", 82.5, "°C")
        assert result.score == 1.0

    def test_component_at_boundary_min(self):
        """Value at min boundary -> deviation = 1.0 -> score = 0.0."""
        # coolant_temp: (70, 95) -> midpoint=82.5, half_range=12.5
        # deviation = |70 - 82.5| / 12.5 = 1.0 -> score = 0.0
        result = calculate_component_score("coolant_temp", 70.0, "°C")
        assert result.score == 0.0

    def test_component_at_boundary_max(self):
        """Value at max boundary -> deviation = 1.0 -> score = 0.0."""
        result = calculate_component_score("coolant_temp", 95.0, "°C")
        assert result.score == 0.0

    def test_component_outside_range_clamped(self):
        """Value beyond max -> deviation > 1.0 -> score clamped to 0.0."""
        result = calculate_component_score("coolant_temp", 110.0, "°C")
        assert result.score == 0.0

    def test_component_unknown_sensor(self):
        """Sensor not in DEFAULT_THRESHOLDS -> score = 1.0.

        speed_target is a valid SensorType but has no entry in DEFAULT_THRESHOLDS.
        """
        assert "speed_target" not in DEFAULT_THRESHOLDS
        result = calculate_component_score("speed_target", 42.0, "km/h")
        assert result.score == 1.0
        assert result.latest_value == 42.0
        assert result.unit == "km/h"

    def test_component_zero_half_range(self):
        """When min == max (half_range = 0) -> score = 1.0."""
        from unittest.mock import patch

        # Use a real SensorType value but override its thresholds to min==max.
        with patch.dict(DEFAULT_THRESHOLDS, {"coolant_temp": (50.0, 50.0)}):
            result = calculate_component_score("coolant_temp", 50.0, "°C")
            assert result.score == 1.0

    def test_component_returns_correct_fields(self):
        """Verify all fields of the returned ComponentHealth object."""
        result = calculate_component_score("coolant_temp", 82.5, "°C")
        assert isinstance(result, ComponentHealth)
        assert result.sensor_type == "coolant_temp"
        assert result.latest_value == 82.5
        assert result.unit == "°C"
        assert 0.0 <= result.score <= 1.0


# ── Overall score tests ───────────────────────────────────────────────────────


class TestCalculateOverallScore:
    def test_overall_all_perfect(self):
        """All components with score=1.0 -> overall = 1.0."""
        components = [
            ComponentHealth(sensor_type="coolant_temp", score=1.0, latest_value=82.5, unit="°C"),
            ComponentHealth(sensor_type="oil_pressure", score=1.0, latest_value=3.5, unit="bar"),
        ]
        assert calculate_overall_score(components) == 1.0

    def test_overall_weighted_average(self):
        """Manual check of weighted average with known weights."""
        components = [
            ComponentHealth(sensor_type="coolant_temp", score=0.8, latest_value=82.5, unit="°C"),
            ComponentHealth(sensor_type="oil_pressure", score=0.6, latest_value=3.5, unit="bar"),
        ]
        w_cool = HEALTH_WEIGHTS["coolant_temp"]  # 0.20
        w_oil = HEALTH_WEIGHTS["oil_pressure"]  # 0.35
        expected = round((0.8 * w_cool + 0.6 * w_oil) / (w_cool + w_oil), 4)
        assert calculate_overall_score(components) == expected

    def test_overall_empty_components(self):
        """No components -> 0.0."""
        assert calculate_overall_score([]) == 0.0

    def test_overall_unknown_sensor_default_weight(self):
        """Sensor types not in HEALTH_WEIGHTS use default weight of 0.05.

        speed_target is a valid SensorType but has no entry in HEALTH_WEIGHTS.
        """
        assert "speed_target" not in HEALTH_WEIGHTS
        components = [
            ComponentHealth(sensor_type="speed_target", score=0.5, latest_value=1.0, unit="km/h"),
        ]
        # Only one component: result = 0.5 * 0.05 / 0.05 = 0.5
        assert calculate_overall_score(components) == 0.5
