"""TE33A diesel locomotive physics — GE GEVO12 8-notch model."""

from __future__ import annotations

from shared.enums import SensorType
from shared.schemas.telemetry import SensorPayload
from simulator.generators.noise import add_noise
from simulator.models.locomotive_state import LocomotiveMode, LocomotiveState


def generate_te33a(state: LocomotiveState) -> list[SensorPayload]:
    """Generate sensor readings for a TE33A diesel locomotive."""
    sensors: list[SensorPayload] = []
    n = state.notch  # 0..8

    if state.mode == LocomotiveMode.AESS_SLEEP:
        # Engine shut down in AESS mode.
        sensors.extend(
            [
                SensorPayload(sensor_type=SensorType.DIESEL_RPM, value=add_noise(0, 300), unit="RPM"),
                SensorPayload(sensor_type=SensorType.OIL_PRESSURE, value=add_noise(0, 3.5), unit="bar"),
                SensorPayload(sensor_type=SensorType.FUEL_RATE, value=0.0, unit="L/h"),
            ]
        )
        state.coolant_temp += (35.0 - state.coolant_temp) * 0.01
        sensors.append(
            SensorPayload(sensor_type=SensorType.COOLANT_TEMP, value=add_noise(state.coolant_temp, 82), unit="C")
        )
        state.traction_motor_temp += (30.0 - state.traction_motor_temp) * 0.01
        sensors.append(
            SensorPayload(
                sensor_type=SensorType.TRACTION_MOTOR_TEMP,
                value=add_noise(state.traction_motor_temp, 85),
                unit="C",
            )
        )
    else:
        diesel_rpm = 300 + n * 93.75
        fuel_rate = 15 + (n / 8) ** 1.5 * 165
        oil_pressure = 1.5 + (diesel_rpm / 1050) * 3.0

        # Thermal inertia (EMA)
        coolant_target = 72 + n * 2.5
        state.coolant_temp += (coolant_target - state.coolant_temp) * 0.05

        motor_target = 40 + (n / 8) * 70
        state.traction_motor_temp += (motor_target - state.traction_motor_temp) * 0.03

        state.fuel_level = max(0.0, state.fuel_level - fuel_rate / 3600)

        sensors.extend(
            [
                SensorPayload(sensor_type=SensorType.DIESEL_RPM, value=add_noise(diesel_rpm, 700), unit="RPM"),
                SensorPayload(sensor_type=SensorType.OIL_PRESSURE, value=add_noise(oil_pressure, 3.5), unit="bar"),
                SensorPayload(sensor_type=SensorType.COOLANT_TEMP, value=add_noise(state.coolant_temp, 82), unit="C"),
                SensorPayload(sensor_type=SensorType.FUEL_RATE, value=add_noise(fuel_rate, 80), unit="L/h"),
                SensorPayload(
                    sensor_type=SensorType.TRACTION_MOTOR_TEMP,
                    value=add_noise(state.traction_motor_temp, 85),
                    unit="C",
                ),
            ]
        )

    sensors.append(SensorPayload(sensor_type=SensorType.FUEL_LEVEL, value=add_noise(state.fuel_level, 50), unit="%"))
    sensors.append(SensorPayload(sensor_type=SensorType.CRANKCASE_PRESSURE, value=add_noise(2.0, 0), unit="mbar"))

    sensors.extend(_common_sensors(state))
    return sensors


def _common_sensors(state: LocomotiveState) -> list[SensorPayload]:
    brake = state.brake_override if state.brake_override is not None else 5.1
    return [
        SensorPayload(sensor_type=SensorType.SPEED_ACTUAL, value=add_noise(state.speed, 60), unit="km/h"),
        SensorPayload(sensor_type=SensorType.SPEED_TARGET, value=add_noise(state.speed + 5, 60), unit="km/h"),
        SensorPayload(sensor_type=SensorType.BRAKE_PIPE_PRESSURE, value=add_noise(brake, 5.1), unit="bar"),
        SensorPayload(sensor_type=SensorType.WHEEL_SLIP_RATIO, value=add_noise(0.0, 0), unit="ratio"),
    ]
