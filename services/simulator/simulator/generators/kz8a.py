"""KZ8A electric locomotive physics — Alstom Prima II AC model."""

from __future__ import annotations

from shared.enums import SensorType
from shared.schemas.telemetry import SensorPayload
from simulator.generators.noise import add_noise
from simulator.models.locomotive_state import LocomotiveMode, LocomotiveState


def generate_kz8a(state: LocomotiveState) -> list[SensorPayload]:
    sensors: list[SensorPayload] = []
    speed = state.speed

    # Pantograph current — proportional to speed (traction demand)
    pantograph_current = 50 + (speed / 120) * 300

    # Catenary voltage — nominal 25kV with load-dependent sag
    catenary_voltage = 25000 - pantograph_current * 8

    # IGBT temperature — slow thermal inertia
    if state.igbt_override is not None:
        state.igbt_temp = state.igbt_override
    else:
        igbt_target = 35 + (pantograph_current / 400) * 40
        state.igbt_temp += (igbt_target - state.igbt_temp) * 0.05

    # Transformer temperature — even slower
    transformer_target = 45 + (pantograph_current / 400) * 35
    state.transformer_temp += (transformer_target - state.transformer_temp) * 0.03

    dc_link = 2800.0

    # Recuperation current — only during braking (ARRIVAL mode, speed > 20)
    recuperation = 0.0
    if state.mode == LocomotiveMode.ARRIVAL and speed > 20:
        recuperation = (120 - speed) / 120 * 200

    sensors.extend(
        [
            SensorPayload(sensor_type=SensorType.CATENARY_VOLTAGE, value=add_noise(catenary_voltage, 25000), unit="V"),
            SensorPayload(
                sensor_type=SensorType.PANTOGRAPH_CURRENT, value=add_noise(pantograph_current, 200), unit="A"
            ),
            SensorPayload(sensor_type=SensorType.IGBT_TEMP, value=add_noise(state.igbt_temp, 57), unit="C"),
            SensorPayload(
                sensor_type=SensorType.TRANSFORMER_TEMP, value=add_noise(state.transformer_temp, 65), unit="C"
            ),
            SensorPayload(sensor_type=SensorType.DC_LINK_VOLTAGE, value=add_noise(dc_link, 2800), unit="V"),
            SensorPayload(sensor_type=SensorType.RECUPERATION_CURRENT, value=add_noise(recuperation, 100), unit="A"),
        ]
    )

    brake = state.brake_override if state.brake_override is not None else 5.1
    sensors.extend(
        [
            SensorPayload(sensor_type=SensorType.SPEED_ACTUAL, value=add_noise(speed, 60), unit="km/h"),
            SensorPayload(sensor_type=SensorType.SPEED_TARGET, value=add_noise(speed + 5, 60), unit="km/h"),
            SensorPayload(sensor_type=SensorType.BRAKE_PIPE_PRESSURE, value=add_noise(brake, 5.1), unit="bar"),
            SensorPayload(sensor_type=SensorType.WHEEL_SLIP_RATIO, value=add_noise(0.0, 0), unit="ratio"),
        ]
    )

    return sensors
