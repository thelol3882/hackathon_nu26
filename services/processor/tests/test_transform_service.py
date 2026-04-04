"""Tests for processor.services.transform_service (unit conversions)."""

import pytest

from processor.services.transform_service import (
    calculate_fuel_rate,
    fahrenheit_to_celsius,
    mph_to_kmh,
    psi_to_bar,
)

# ── Fahrenheit to Celsius ───────────────────────────────────────────────────


class TestFahrenheitToCelsius:
    def test_boiling_point(self):
        assert fahrenheit_to_celsius(212.0) == pytest.approx(100.0)

    def test_freezing_point(self):
        assert fahrenheit_to_celsius(32.0) == pytest.approx(0.0)

    def test_body_temp(self):
        assert fahrenheit_to_celsius(98.6) == pytest.approx(37.0, abs=0.01)

    def test_minus_40_same_in_both(self):
        assert fahrenheit_to_celsius(-40.0) == pytest.approx(-40.0)


# ── PSI to Bar ──────────────────────────────────────────────────────────────


class TestPsiToBar:
    def test_14_5_psi_approx_1_bar(self):
        assert psi_to_bar(14.5) == pytest.approx(1.0, abs=0.01)

    def test_zero_psi(self):
        assert psi_to_bar(0.0) == 0.0


# ── MPH to KMH ─────────────────────────────────────────────────────────────


class TestMphToKmh:
    def test_60_mph(self):
        assert mph_to_kmh(60.0) == pytest.approx(96.5604, abs=0.01)

    def test_zero_mph(self):
        assert mph_to_kmh(0.0) == 0.0


# ── Fuel rate ───────────────────────────────────────────────────────────────


class TestCalculateFuelRate:
    def test_normal_consumption(self):
        # 5% drop over 1 hour -> 5 %/h
        assert calculate_fuel_rate(80.0, 75.0, 3600.0) == pytest.approx(5.0)

    def test_no_change(self):
        assert calculate_fuel_rate(50.0, 50.0, 3600.0) == pytest.approx(0.0)

    def test_negative_delta_refuel(self):
        # Fuel went up (refueling) -> negative rate
        result = calculate_fuel_rate(50.0, 60.0, 3600.0)
        assert result < 0.0

    def test_zero_elapsed_returns_zero(self):
        assert calculate_fuel_rate(80.0, 75.0, 0.0) == 0.0

    def test_negative_elapsed_returns_zero(self):
        assert calculate_fuel_rate(80.0, 75.0, -10.0) == 0.0

    def test_tiny_elapsed(self):
        # Very short interval -> high rate but should not error
        result = calculate_fuel_rate(80.0, 79.999, 0.001)
        expected = (0.001 / 0.001) * 3600.0
        assert result == pytest.approx(expected)
