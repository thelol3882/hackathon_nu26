from enum import StrEnum


class LocomotiveStatus(StrEnum):
    ACTIVE = "active"
    IDLE = "idle"
    MAINTENANCE = "maintenance"
    DECOMMISSIONED = "decommissioned"


class SensorType(StrEnum):
    TEMPERATURE = "temperature"
    PRESSURE = "pressure"
    VIBRATION = "vibration"
    FUEL_LEVEL = "fuel_level"
    SPEED = "speed"
    RPM = "rpm"
    BRAKE_PRESSURE = "brake_pressure"
    OIL_PRESSURE = "oil_pressure"
    COOLANT_TEMP = "coolant_temp"
    BATTERY_VOLTAGE = "battery_voltage"


class AlertSeverity(StrEnum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"
    EMERGENCY = "emergency"
