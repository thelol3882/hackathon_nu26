"""Unit conversions and derived metric calculations."""


def fahrenheit_to_celsius(f: float) -> float:
    return (f - 32) * 5 / 9


def psi_to_bar(psi: float) -> float:
    return psi * 0.0689476


def mph_to_kmh(mph: float) -> float:
    return mph * 1.60934


def calculate_fuel_rate(
    fuel_level_prev: float,
    fuel_level_curr: float,
    elapsed_seconds: float,
) -> float:
    """Fuel consumption rate in %/hour."""
    if elapsed_seconds <= 0:
        return 0.0
    delta = fuel_level_prev - fuel_level_curr
    return (delta / elapsed_seconds) * 3600
