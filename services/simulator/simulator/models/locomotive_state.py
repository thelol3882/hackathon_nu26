"""Per-locomotive simulation state, mode state machine, and kinematics.

Auto mode (default) cycles DEPOT -> DEPARTURE -> CRUISING -> ARRIVAL -> DEPOT
and shuttles the train along its route's sub-segment. Manual mode
(``auto_mode = False``) pauses the state machine so the operator drives
``mode``, ``speed`` and ``forward`` via HTTP. The per-loco ``scenario`` flag
tweaks sensor output in both modes without touching kinematics.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID

from shared.enums import LocomotiveType
from shared.route_geometry import Route

# Re-exported so existing imports keep working.
__all__ = [
    "LOCO_TICK_SECONDS",
    "MODE_DURATIONS",
    "LocomotiveMode",
    "LocomotiveScenario",
    "LocomotiveState",
    "OnArrival",
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


class LocomotiveScenario(StrEnum):
    """Operator-facing sensor scenario: normal, slow IGBT degradation, or
    emergency brake-pipe fault. Does not touch kinematics."""

    NORMAL = "normal"
    DEGRADATION = "degradation"
    EMERGENCY = "emergency"


class OnArrival(StrEnum):
    """What happens when the loco reaches ``end_distance_m``."""

    LOOP = "loop"  # reverse direction, shuttle back
    STOP = "stop"  # stay at the destination in DEPOT
    REMOVE = "remove"  # flag for runner to drop the loco


# Duration ranges (seconds) for each mode.
MODE_DURATIONS: dict[LocomotiveMode, tuple[int, int]] = {
    LocomotiveMode.DEPOT: (600, 7200),
    LocomotiveMode.DEPARTURE: (180, 600),
    LocomotiveMode.CRUISING: (1800, 10800),
    LocomotiveMode.ARRIVAL: (180, 600),
    LocomotiveMode.AESS_SLEEP: (300, 1800),
    LocomotiveMode.EMERGENCY: (60, 300),
    LocomotiveMode.RECOVERY: (300, 900),
}


LOCO_TICK_SECONDS: float = 1.0


# IGBT degradation: linear ramp over ~20 minutes at 1 Hz.
_DEGRADATION_DURATION_TICKS = 1200
_DEGRADATION_START_TEMP = 57.0
_DEGRADATION_END_TEMP = 87.0

# Emergency brake-pipe drop curve.
_EMERGENCY_DURATION_TICKS = 10
_BRAKE_NORMAL = 5.1
_BRAKE_FAULT = 1.8


@dataclass
class LocomotiveState:
    id: UUID
    loco_type: LocomotiveType
    route: Route

    name: str = ""

    mode: LocomotiveMode = LocomotiveMode.DEPOT
    scenario: LocomotiveScenario = LocomotiveScenario.NORMAL
    # When False the auto state machine is paused. New locomotives default to
    # manual so they stay in DEPOT until the operator dispatches them.
    auto_mode: bool = False

    speed: float = 0.0  # km/h
    notch: int = 0  # 0..8, TE33A only
    fuel_level: float = 90.0  # %, TE33A only

    # Position along the route polyline, in metres.
    distance_m: float = 0.0
    # Sub-segment bounds. ``end_distance_m == 0.0`` means "use the whole route"
    # so old call sites still work.
    start_distance_m: float = 0.0
    end_distance_m: float = 0.0
    on_arrival: OnArrival = OnArrival.LOOP
    arrived: bool = False  # latched once the trip completes

    # Cached pose, written by _update_gps every tick.
    lat: float = 0.0
    lon: float = 0.0
    bearing_deg: float = 0.0

    # EMA-smoothed thermal state.
    coolant_temp: float = 72.0
    traction_motor_temp: float = 40.0
    igbt_temp: float = 35.0
    transformer_temp: float = 45.0

    mode_ticks: int = 0
    mode_duration: int = 0  # ticks until next transition

    igbt_override: float | None = None
    brake_override: float | None = None
    # Independent of mode_ticks so re-arming a scenario gives a fresh ramp.
    scenario_tick: int = 0

    # True = start -> end, False = end -> start.
    forward: bool = True

    def __post_init__(self) -> None:
        if self.mode_duration == 0:
            lo, hi = MODE_DURATIONS[self.mode]
            self.mode_duration = random.randint(lo, hi)
        if self.end_distance_m <= 0:
            self.end_distance_m = self.route.length_m
        self.start_distance_m = max(0.0, min(self.start_distance_m, self.route.length_m))
        self.end_distance_m = max(self.start_distance_m, min(self.end_distance_m, self.route.length_m))
        self.distance_m = max(self.start_distance_m, min(self.distance_m, self.end_distance_m))
        # Snap pose so brand-new locos don't briefly report (0, 0).
        self.lat, self.lon, self.bearing_deg = self.route.position_at(self.distance_m)

    @property
    def route_progress(self) -> float:
        """Normalised 0..1 position along the full route (back-compat alias)."""
        if self.route.length_m <= 0:
            return 0.0
        return max(0.0, min(1.0, self.distance_m / self.route.length_m))

    @property
    def segment_progress(self) -> float:
        """0..1 progress within the operator-chosen sub-segment."""
        span = self.end_distance_m - self.start_distance_m
        if span <= 0:
            return 0.0
        return max(0.0, min(1.0, (self.distance_m - self.start_distance_m) / span))


def _transition(state: LocomotiveState) -> None:
    """Advance the auto state machine; no-op when auto_mode is off."""
    if not state.auto_mode:
        return

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

            if state.mode_ticks >= state.mode_duration:
                _enter_mode(state, LocomotiveMode.ARRIVAL)

        case LocomotiveMode.ARRIVAL:
            if state.loco_type == LocomotiveType.TE33A:
                state.notch = max(0, state.notch - 1)
            state.speed = max(0.0, state.speed - 0.8)
            if state.mode_ticks >= state.mode_duration:
                state.speed = 0.0
                state.notch = 0
                state.forward = not state.forward
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


def _apply_scenario(state: LocomotiveState) -> None:
    """Translate ``state.scenario`` into sensor overrides for this tick."""
    state.scenario_tick += 1

    if state.scenario == LocomotiveScenario.NORMAL:
        # Clear leftover overrides so toggling back to normal clears the chart.
        state.igbt_override = None
        state.brake_override = None
        return

    if state.scenario == LocomotiveScenario.DEGRADATION:
        progress = min(1.0, state.scenario_tick / _DEGRADATION_DURATION_TICKS)
        state.igbt_override = _DEGRADATION_START_TEMP + (_DEGRADATION_END_TEMP - _DEGRADATION_START_TEMP) * progress
        state.brake_override = None
        return

    if state.scenario == LocomotiveScenario.EMERGENCY:
        if state.scenario_tick <= _EMERGENCY_DURATION_TICKS:
            progress = state.scenario_tick / _EMERGENCY_DURATION_TICKS
            state.brake_override = _BRAKE_NORMAL + (_BRAKE_FAULT - _BRAKE_NORMAL) * progress
        else:
            state.brake_override = _BRAKE_FAULT
        # Snap into EMERGENCY and force a stop regardless of auto/manual mode.
        state.mode = LocomotiveMode.EMERGENCY
        state.speed = max(0.0, state.speed - 2.0)
        state.igbt_override = None


def _update_gps(state: LocomotiveState, dt_seconds: float = LOCO_TICK_SECONDS) -> None:
    """Advance distance_m by speed*dt within the sub-segment, applying on_arrival
    policy when a bound is hit."""
    if state.speed > 0:
        speed_ms = state.speed * 1000.0 / 3600.0
        delta_m = speed_ms * dt_seconds
        if state.forward:
            state.distance_m += delta_m
            if state.distance_m >= state.end_distance_m:
                state.distance_m = state.end_distance_m
                _on_segment_bound_hit(state, at_end=True)
        else:
            state.distance_m -= delta_m
            if state.distance_m <= state.start_distance_m:
                state.distance_m = state.start_distance_m
                _on_segment_bound_hit(state, at_end=False)

    state.lat, state.lon, state.bearing_deg = state.route.position_at(state.distance_m)


def _on_segment_bound_hit(state: LocomotiveState, *, at_end: bool) -> None:
    """Apply the on_arrival policy when a sub-segment bound is touched."""
    if state.on_arrival == OnArrival.LOOP:
        state.forward = not state.forward
        return
    if at_end:
        # STOP/REMOVE only apply at the end bound; hitting start is just
        # where a loop came back to.
        if state.on_arrival == OnArrival.STOP:
            state.speed = 0.0
            state.mode = LocomotiveMode.DEPOT
            state.auto_mode = False
            state.arrived = True
        elif state.on_arrival == OnArrival.REMOVE:
            state.speed = 0.0
            state.arrived = True
    else:
        # Shouldn't normally happen in non-loop mode — stop and let the
        # operator decide what to do.
        state.speed = 0.0
        state.forward = True


def tick(state: LocomotiveState, dt_seconds: float = LOCO_TICK_SECONDS) -> None:
    """Advance one simulation tick (default 1 s)."""
    _transition(state)
    _apply_scenario(state)
    _update_gps(state, dt_seconds)


def get_gps(state: LocomotiveState) -> tuple[float, float]:
    return state.lat, state.lon
