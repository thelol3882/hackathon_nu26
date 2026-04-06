from enum import StrEnum


class LocomotiveType(StrEnum):
    TE33A = "TE33A"  # GE GEVO12 diesel-electric
    KZ8A = "KZ8A"  # Alstom Prima II AC electric


class LocomotiveStatus(StrEnum):
    ACTIVE = "active"
    IDLE = "idle"
    MAINTENANCE = "maintenance"
    DECOMMISSIONED = "decommissioned"


class SensorType(StrEnum):
    # TE33A — Diesel (GE GEVO12)
    DIESEL_RPM = "diesel_rpm"  # 0–1050 rpm
    OIL_PRESSURE = "oil_pressure"  # 1.5–5.0 bar
    COOLANT_TEMP = "coolant_temp"  # 70–95 °C
    FUEL_LEVEL = "fuel_level"  # 0–6500 L (stored as %)
    FUEL_RATE = "fuel_rate"  # 10–200 L/h
    TRACTION_MOTOR_TEMP = "traction_motor_temp"  # 40–130 °C
    CRANKCASE_PRESSURE = "crankcase_pressure"  # mbar — fatal if high

    # KZ8A — Electric (Alstom)
    CATENARY_VOLTAGE = "catenary_voltage"  # ~25 000 V AC
    PANTOGRAPH_CURRENT = "pantograph_current"  # 0–400 A
    TRANSFORMER_TEMP = "transformer_temp"  # 40–90 °C (aging param)
    IGBT_TEMP = "igbt_temp"  # 30–85 °C (aging param)
    RECUPERATION_CURRENT = "recuperation_current"  # A — regen braking
    DC_LINK_VOLTAGE = "dc_link_voltage"  # ~2800 V DC

    # Common
    SPEED_ACTUAL = "speed_actual"  # 0–120 km/h
    SPEED_TARGET = "speed_target"  # 0–120 km/h (limit)
    BRAKE_PIPE_PRESSURE = "brake_pipe_pressure"  # ~5.0–5.2 kgf/cm²
    WHEEL_SLIP_RATIO = "wheel_slip_ratio"  # 0.0–1.0 (fraction)


class ThresholdType(StrEnum):
    """How a sensor's limits should be interpreted."""

    BIDIRECTIONAL = "bidirectional"  # penalise below and above nominal
    UPPER_BOUND = "upper_bound"  # penalise when exceeding upper limit
    LOWER_BOUND = "lower_bound"  # penalise when falling below lower limit
    EXACT_MATCH = "exact_match"  # must equal nominal exactly


class AlertSeverity(StrEnum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"
    EMERGENCY = "emergency"
