from __future__ import annotations

import random
from dataclasses import dataclass, field
from enum import StrEnum
from uuid import UUID

from shared.enums import LocomotiveType
from shared.route_geometry import Route

# Re-export Route so existing imports (`from ...locomotive_state import Route`)
# keep working without touching every callsite.
__all__ = [
    "LOCO_TICK_SECONDS",
    "MODE_DURATIONS",
    "LocomotiveMode",
    "LocomotiveState",
    "Route",
    "get_gps",
    "tick",
]


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


# How many wall-clock seconds one tick represents. The runner's
# `tick_interval` is what we sleep between calls; with the default of
# 1.0 s, advancing kinematics by 1 s per tick gives correct real-time
# speeds. If the operator dials the runner faster (burst mode), the
# `effective_multiplier` already widens the per-tick wall time too, so
# distance still works out. Kept as a constant rather than sneaking
# back into config so it's obvious to readers.
LOCO_TICK_SECONDS: float = 1.0


@dataclass
class LocomotiveState:
    id: UUID
    loco_type: LocomotiveType
    route: Route
    mode: LocomotiveMode = LocomotiveMode.DEPOT
    speed: float = 0.0  # km/h
    notch: int = 0  # 0–8, TE33A only
    fuel_level: float = 90.0  # % (TE33A only)

    # Position along the route polyline. Stored in metres so the
    # kinematics (speed × dt → distance) need no unit acrobatics. The
    # cached lat/lon/bearing are written by `_update_gps` each tick so
    # `get_gps` is a free lookup.
    distance_m: float = 0.0
    lat: float = 0.0
    lon: float = 0.0
    bearing_deg: float = 0.0

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

    # Direction on route (True = start→end, False = end→start)
    forward: bool = field(default_factory=lambda: random.choice([True, False]))

    def __post_init__(self) -> None:
        if self.mode_duration == 0:
            lo, hi = MODE_DURATIONS[self.mode]
            self.mode_duration = random.randint(lo, hi)
        # Snap to the polyline immediately so brand-new locomotives
        # don't report (0, 0) for one frame before the first tick.
        self.lat, self.lon, self.bearing_deg = self.route.position_at(self.distance_m)

    @property
    def route_progress(self) -> float:
        """Backward-compat alias: 0..1 normalised position along the route.

        Some places (e.g. ``runner.sample_fleet``) still expose this as
        a metric, so we keep it as a derived read-only property instead
        of a stored field. Setters / writers gone — use ``distance_m``.
        """
        if self.route.length_m <= 0:
            return 0.0
        return max(0.0, min(1.0, self.distance_m / self.route.length_m))


def _transition(state: LocomotiveState) -> None:
    """Advance the state machine when mode_duration expires or random events occur."""
    state.mode_ticks += 1

    match state.mode:
        case LocomotiveMode.DEPOT:
            if state.mode_ticks >= state.mode_duration:
                _enter_mode(state, LocomotiveMode.DEPARTURE)

        case LocomotiveMode.DEPARTURE:
            if state.loco_type == LocomotiveType.TE33A:
                target_notch = min(8, state.notch + 1)
                if state.mode_ticks % 20 == 0 and state.notch < target_notch:
                    state.notch = target_notch
            state.speed = min(100.0, state.speed + 0.5)
            if state.mode_ticks >= state.mode_duration:
                _enter_mode(state, LocomotiveMode.CRUISING)

        case LocomotiveMode.CRUISING:
            if state.loco_type == LocomotiveType.TE33A:
                state.notch = random.choice([5, 6, 7])
            state.speed = max(50.0, min(110.0, state.speed + random.gauss(0, 1)))

            if random.random() < 0.0001:
                _enter_mode(state, LocomotiveMode.EMERGENCY)
                return
            if state.loco_type == LocomotiveType.TE33A and random.random() < 0.0005:
                _enter_mode(state, LocomotiveMode.AESS_SLEEP)
                return
            if state.mode_ticks >= state.mode_duration:
                _enter_mode(state, LocomotiveMode.ARRIVAL)

        case LocomotiveMode.ARRIVAL:
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


def _update_gps(state: LocomotiveState, dt_seconds: float = LOCO_TICK_SECONDS) -> None:
    """Advance position along the polyline by speed × dt.

    The kinematics are honest now: speed (km/h) → m/s → distance in
    metres for ``dt_seconds`` of wall clock time. So a locomotive
    cruising at 80 km/h takes ~12 hours of simulation time to cross a
    1000 km route, instead of the previous ~5 minutes. When the train
    reaches an endpoint we flip ``forward`` and start unwinding back
    along the same polyline.

    Caches the new (lat, lon, bearing) on the state so the per-tick
    telemetry envelope can read them without recomputing the polyline
    walk.
    """
    if state.speed > 0:
        speed_ms = state.speed * 1000.0 / 3600.0
        delta_m = speed_ms * dt_seconds
        if state.forward:
            state.distance_m += delta_m
            if state.distance_m >= state.route.length_m:
                state.distance_m = state.route.length_m
                state.forward = False
        else:
            state.distance_m -= delta_m
            if state.distance_m <= 0:
                state.distance_m = 0.0
                state.forward = True

    # Always refresh the cached pose, even when stopped — the route
    # geometry may have been swapped (tests, scenario reload) and we
    # don't want stale lat/lon to leak through.
    state.lat, state.lon, state.bearing_deg = state.route.position_at(state.distance_m)


def tick(state: LocomotiveState, dt_seconds: float = LOCO_TICK_SECONDS) -> None:
    """Advance one simulation tick (default: 1 second of wall clock)."""
    _transition(state)
    _update_gps(state, dt_seconds)


def get_gps(state: LocomotiveState) -> tuple[float, float]:
    """Return the cached (lat, lon) for the current tick.

    Always cheap — the actual polyline walk happens in ``_update_gps``.
    """
    return state.lat, state.lon
