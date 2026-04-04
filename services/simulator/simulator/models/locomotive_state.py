from __future__ import annotations

import random
from dataclasses import dataclass, field
from enum import StrEnum
from uuid import UUID

from shared.enums import LocomotiveType


class LocomotiveMode(StrEnum):
    DEPOT = "depot"
    DEPARTURE = "departure"
    CRUISING = "cruising"
    ARRIVAL = "arrival"
    AESS_SLEEP = "aess_sleep"
    EMERGENCY = "emergency"
    RECOVERY = "recovery"


# Duration ranges (seconds) for each mode
MODE_DURATIONS: dict[LocomotiveMode, tuple[int, int]] = {
    LocomotiveMode.DEPOT: (600, 7200),  # 10–120 min
    LocomotiveMode.DEPARTURE: (180, 600),  # 3–10 min
    LocomotiveMode.CRUISING: (1800, 10800),  # 30–180 min
    LocomotiveMode.ARRIVAL: (180, 600),  # 3–10 min
    LocomotiveMode.AESS_SLEEP: (300, 1800),  # 5–30 min
    LocomotiveMode.EMERGENCY: (60, 300),  # 1–5 min
    LocomotiveMode.RECOVERY: (300, 900),  # 5–15 min
}


@dataclass
class Route:
    name: str
    lat_start: float
    lon_start: float
    lat_end: float
    lon_end: float
    electrified: bool


@dataclass
class LocomotiveState:
    id: UUID
    loco_type: LocomotiveType
    route: Route
    mode: LocomotiveMode = LocomotiveMode.DEPOT
    route_progress: float = 0.0  # 0.0 → 1.0
    speed: float = 0.0  # km/h
    notch: int = 0  # 0–8, TE33A only
    fuel_level: float = 90.0  # % (TE33A only)

    # Thermal state (EMA-smoothed internally)
    coolant_temp: float = 72.0
    traction_motor_temp: float = 40.0
    igbt_temp: float = 35.0
    transformer_temp: float = 45.0

    # Mode timing
    mode_ticks: int = 0
    mode_duration: int = 0  # ticks until next transition

    # Scenario overrides (set by degradation/emergency scenarios)
    igbt_override: float | None = None
    brake_override: float | None = None

    # Direction on route (True = forward, False = returning)
    forward: bool = field(default_factory=lambda: random.choice([True, False]))

    def __post_init__(self) -> None:
        if self.mode_duration == 0:
            lo, hi = MODE_DURATIONS[self.mode]
            self.mode_duration = random.randint(lo, hi)


def _transition(state: LocomotiveState) -> None:
    """Advance the state machine when mode_duration expires or random events occur."""
    state.mode_ticks += 1

    match state.mode:
        case LocomotiveMode.DEPOT:
            if state.mode_ticks >= state.mode_duration:
                _enter_mode(state, LocomotiveMode.DEPARTURE)

        case LocomotiveMode.DEPARTURE:
            # Ramp up notch/speed
            if state.loco_type == LocomotiveType.TE33A:
                target_notch = min(8, state.notch + 1)
                if state.mode_ticks % 20 == 0 and state.notch < target_notch:
                    state.notch = target_notch
            state.speed = min(100.0, state.speed + 0.5)
            if state.mode_ticks >= state.mode_duration:
                _enter_mode(state, LocomotiveMode.CRUISING)

        case LocomotiveMode.CRUISING:
            # Maintain cruising speed with slight variation
            if state.loco_type == LocomotiveType.TE33A:
                state.notch = random.choice([5, 6, 7])
            state.speed = max(50.0, min(110.0, state.speed + random.gauss(0, 1)))

            # Random events
            if random.random() < 0.0001:
                _enter_mode(state, LocomotiveMode.EMERGENCY)
                return
            if state.loco_type == LocomotiveType.TE33A and random.random() < 0.0005:
                _enter_mode(state, LocomotiveMode.AESS_SLEEP)
                return
            if state.mode_ticks >= state.mode_duration:
                _enter_mode(state, LocomotiveMode.ARRIVAL)

        case LocomotiveMode.ARRIVAL:
            # Slow down
            if state.loco_type == LocomotiveType.TE33A:
                state.notch = max(0, state.notch - 1)
            state.speed = max(0.0, state.speed - 0.8)
            if state.mode_ticks >= state.mode_duration:
                state.speed = 0.0
                state.notch = 0
                state.forward = not state.forward  # reverse direction
                _enter_mode(state, LocomotiveMode.DEPOT)

        case LocomotiveMode.AESS_SLEEP:
            state.speed = 0.0
            state.notch = 0
            if state.mode_ticks >= state.mode_duration:
                _enter_mode(state, LocomotiveMode.DEPARTURE)

        case LocomotiveMode.EMERGENCY:
            state.speed = max(0.0, state.speed - 2.0)
            if state.mode_ticks >= state.mode_duration:
                _enter_mode(state, LocomotiveMode.RECOVERY)

        case LocomotiveMode.RECOVERY:
            # Gradually return to normal
            state.speed = min(60.0, state.speed + 0.3)
            if state.loco_type == LocomotiveType.TE33A:
                state.notch = min(4, state.notch + (1 if state.mode_ticks % 30 == 0 else 0))
            if state.mode_ticks >= state.mode_duration:
                _enter_mode(state, LocomotiveMode.CRUISING)


def _enter_mode(state: LocomotiveState, mode: LocomotiveMode) -> None:
    state.mode = mode
    state.mode_ticks = 0
    lo, hi = MODE_DURATIONS[mode]
    state.mode_duration = random.randint(lo, hi)


def _update_gps(state: LocomotiveState) -> None:
    """Advance GPS position along route based on speed."""
    if state.speed <= 0:
        return
    # Approximate: 1 km/h ≈ progress of 0.001 per tick on ~1000 km route
    delta = state.speed * 0.000001
    if state.forward:
        state.route_progress = min(1.0, state.route_progress + delta)
        if state.route_progress >= 1.0:
            state.forward = False
    else:
        state.route_progress = max(0.0, state.route_progress - delta)
        if state.route_progress <= 0.0:
            state.forward = True


def tick(state: LocomotiveState) -> None:
    """Advance one simulation tick (1 second at normal rate)."""
    _transition(state)
    _update_gps(state)


def get_gps(state: LocomotiveState) -> tuple[float, float]:
    """Interpolate current GPS position along the route."""
    r = state.route
    p = state.route_progress
    lat = r.lat_start + (r.lat_end - r.lat_start) * p
    lon = r.lon_start + (r.lon_end - r.lon_start) * p
    return lat, lon
