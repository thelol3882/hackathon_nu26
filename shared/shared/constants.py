# Redis Pub/Sub channels
TELEMETRY_CHANNEL = "telemetry:live"
ALERT_CHANNEL = "alerts:live"

# Default alert thresholds
DEFAULT_THRESHOLDS: dict[str, tuple[float, float]] = {
    "temperature": (0.0, 120.0),         # °C
    "pressure": (0.0, 15.0),             # bar
    "vibration": (0.0, 50.0),            # mm/s
    "fuel_level": (10.0, 100.0),         # %
    "speed": (0.0, 160.0),              # km/h
    "rpm": (0.0, 2500.0),
    "brake_pressure": (2.0, 10.0),       # bar
    "oil_pressure": (1.5, 7.0),          # bar
    "coolant_temp": (60.0, 105.0),       # °C
    "battery_voltage": (22.0, 30.0),     # V
}

# Health index weights per sensor type
HEALTH_WEIGHTS: dict[str, float] = {
    "temperature": 0.15,
    "pressure": 0.10,
    "vibration": 0.15,
    "fuel_level": 0.05,
    "speed": 0.05,
    "rpm": 0.10,
    "brake_pressure": 0.15,
    "oil_pressure": 0.10,
    "coolant_temp": 0.10,
    "battery_voltage": 0.05,
}
