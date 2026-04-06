"""Per-locomotive simulation state, mode state-machine and kinematics.

Two control models live in here:

1. **Auto mode** (default). The state machine cycles
   ``DEPOT → DEPARTURE → CRUISING → ARRIVAL → DEPOT`` and the train
   shuttles between ``start_distance_m`` and ``end_distance_m`` along
   its route's polyline. Useful for "set and forget" — the operator
   creates a locomotive and leaves it to run.

2. **Manual mode** (``auto_mode = False``). The state machine is
   paused. The operator dictates ``mode``, ``speed`` and ``forward``
   directly via the simulator's HTTP API. Used by the dashboard's
   detail page where you can pin a locomotive to DEPOT, force a
   CRUISING speed, or trip an EMERGENCY by hand.

The same per-locomotive ``scenario`` field plays into both: it tweaks
the sensor outputs of the loco (no override / mild degradation /
emergency) without touching the kinematics.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID

from shared.enums import LocomotiveType
from shared.route_geometry import Route

# Re-export Route so existing imports keep working without touching
# every callsite.
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
    """How the sensor pipeline should colour this locomotive's outputs.

    Doesn't affect kinematics, only the values reported by sensors:

    * ``normal`` — everything within nominal ranges.
    * ``degradation`` — IGBT temperature creeps up over time, mimicking
      thermal damage. Train still runs.
    * ``emergency`` — brake pipe pressure drops to a fault level and
      the locomotive is forced to EMERGENCY mode (zero speed).
    """

    NORMAL = "normal"
    DEGRADATION = "degradation"
    EMERGENCY = "emergency"


class OnArrival(StrEnum):
    """What the locomotive does when it reaches ``end_distance_m``."""

    LOOP = "loop"      # reverse direction, shuttle back to start, repeat
    STOP = "stop"      # stay at the destination in DEPOT
    REMOVE = "remove"  # delete from the simulator (signalled via flag)


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


# How many wall-clock seconds one tick represents.
LOCO_TICK_SECONDS: float = 1.0


# IGBT degradation curve — linear ramp over this many ticks.
_DEGRADATION_DURATION_TICKS = 1200  # 20 min at 1 Hz
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

    # ---- Optional human-friendly metadata (operator-set) ----------
    name: str = ""

    # ---- Mode + scenario controls --------------------------------
    mode: LocomotiveMode = LocomotiveMode.DEPOT
    scenario: LocomotiveScenario = LocomotiveScenario.NORMAL
    # When False the auto state machine is paused — the operator
    # owns `mode` and `speed`. New locomotives default to manual so
    # they sit quietly in DEPOT until the operator sends them off.
    auto_mode: bool = False

    # ---- Kinematics ----------------------------------------------
    speed: float = 0.0  # km/h
    notch: int = 0  # 0–8, TE33A only
    fuel_level: float = 90.0  # % (TE33A only)

    # Position along the route polyline. Stored in metres so the
    # kinematics (speed × dt → distance) need no unit acrobatics.
    distance_m: float = 0.0
    # Sub-segment of the route the locomotive is allowed to traverse.
    # ``end_distance_m == 0.0`` is treated as "the whole route" so old
    # call sites keep working without passing the new arg.
    start_distance_m: float = 0.0
    end_distance_m: float = 0.0
    on_arrival: OnArrival = OnArrival.LOOP
    arrived: bool = False  # latched once the locomotive completes its trip

    # Cached pose written by `_update_gps` each tick.
    lat: float = 0.0
    lon: float = 0.0
    bearing_deg: float = 0.0

    # ---- Thermal state (EMA-smoothed by sensor generators) -------
    coolant_temp: float = 72.0
    traction_motor_temp: float = 40.0
    igbt_temp: float = 35.0
    transformer_temp: float = 45.0

    # ---- Mode-machine timing -------------------------------------
    mode_ticks: int = 0
    mode_duration: int = 0  # ticks until next transition

    # ---- Scenario-driven sensor overrides ------------------------
    igbt_override: float | None = None
    brake_override: float | None = None
    # Per-loco scenario tick counter, independent of `mode_ticks`,
    # so re-arming a scenario gives a fresh ramp.
    scenario_tick: int = 0

    # ---- Direction on route (True = start→end, False = end→start)
    forward: bool = True

    def __post_init__(self) -> None:
        if self.mode_duration == 0:
            lo, hi = MODE_DURATIONS[self.mode]
            self.mode_duration = random.randint(lo, hi)
        # If end_distance_m wasn't set explicitly, default to "use the
        # whole route". Clamp distance_m into the legal sub-segment.
        if self.end_distance_m <= 0:
            self.end_distance_m = self.route.length_m
        self.start_distance_m = max(0.0, min(self.start_distance_m, self.route.length_m))
        self.end_distance_m = max(self.start_distance_m, min(self.end_distance_m, self.route.length_m))
        self.distance_m = max(self.start_distance_m, min(self.distance_m, self.end_distance_m))
        # Snap pose immediately so brand-new locomotives don't report
        # (0, 0) for one frame before the first tick.
        self.lat, self.lon, self.bearing_deg = self.route.position_at(self.distance_m)

    @property
    def route_progress(self) -> float:
        """Backward-compat alias: 0..1 normalised position along the route."""
        if self.route.length_m <= 0:
            return 0.0
        return max(0.0, min(1.0, self.distance_m / self.route.length_m))

    @property
    def segment_progress(self) -> float:
        """0..1 progress within the *operator-chosen sub-segment*.

        Useful for the UI: 0 = at start_station, 1 = at end_station.
        """
        span = self.end_distance_m - self.start_distance_m
        if span <= 0:
            return 0.0
        return max(0.0, min(1.0, (self.distance_m - self.start_distance_m) / span))


def _transition(state: LocomotiveState) -> None:
    """Advance the auto state machine for one tick.

    Skipped entirely if ``state.auto_mode`` is False — manual mode
    leaves ``mode`` and ``speed`` to the operator.
    """
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


def _apply_scenario(state: LocomotiveState) -> None:
    """Translate ``state.scenario`` into sensor overrides for this tick.

    Scenarios used to be fleet-wide handlers picking one target
    locomotive at random. Now each locomotive owns its own scenario
    flag, set by the operator from the dashboard, and we apply it
    inline. The previous global scenario picker is gone.
    """
    state.scenario_tick += 1

    if state.scenario == LocomotiveScenario.NORMAL:
        # Clear any leftover overrides so a "back to normal" toggle
        # actually clears the chart.
        state.igbt_override = None
        state.brake_override = None
        return

    if state.scenario == LocomotiveScenario.DEGRADATION:
        # Linear IGBT temperature ramp over ~20 minutes; clamps at
        # the fault threshold so the chart doesn't keep climbing.
        progress = min(1.0, state.scenario_tick / _DEGRADATION_DURATION_TICKS)
        state.igbt_override = (
            _DEGRADATION_START_TEMP
            + (_DEGRADATION_END_TEMP - _DEGRADATION_START_TEMP) * progress
        )
        state.brake_override = None
        return

    if state.scenario == LocomotiveScenario.EMERGENCY:
        # Brake pipe drops over the first 10 ticks then stays put.
        if state.scenario_tick <= _EMERGENCY_DURATION_TICKS:
            progress = state.scenario_tick / _EMERGENCY_DURATION_TICKS
            state.brake_override = (
                _BRAKE_NORMAL + (_BRAKE_FAULT - _BRAKE_NORMAL) * progress
            )
        else:
            state.brake_override = _BRAKE_FAULT
        # An emergency snaps the locomotive into EMERGENCY mode and
        # forces it to a stop. We do this regardless of auto/manual
        # mode — the whole point of the scenario is "everything broke".
        state.mode = LocomotiveMode.EMERGENCY
        state.speed = max(0.0, state.speed - 2.0)
        state.igbt_override = None


def _update_gps(state: LocomotiveState, dt_seconds: float = LOCO_TICK_SECONDS) -> None:
    """Advance position along the polyline by speed × dt, honouring the
    operator-chosen sub-segment between ``start_distance_m`` and
    ``end_distance_m``.

    On hitting either bound the ``on_arrival`` policy decides what to
    do next:

    * ``LOOP`` — flip direction, head back, do it forever.
    * ``STOP`` — clamp at the bound, set speed to 0, mode to DEPOT.
    * ``REMOVE`` — set ``arrived=True`` so the runner can drop the loco.
    """
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
    """Apply the ``on_arrival`` policy when we touch a sub-segment bound."""
    if state.on_arrival == OnArrival.LOOP:
        state.forward = not state.forward
        return
    if at_end:
        # The end station is the "real" arrival; the start bound is
        # just where a looping run came back to. STOP/REMOVE only
        # apply to reaching `end`.
        if state.on_arrival == OnArrival.STOP:
            state.speed = 0.0
            state.mode = LocomotiveMode.DEPOT
            state.auto_mode = False
            state.arrived = True
        elif state.on_arrival == OnArrival.REMOVE:
            state.speed = 0.0
            state.arrived = True
    else:
        # Reaching the start bound while not in LOOP shouldn't happen
        # under normal play (the loco starts at start), but treat it
        # symmetrically: just stop and let the operator decide.
        state.speed = 0.0
        state.forward = True


def tick(state: LocomotiveState, dt_seconds: float = LOCO_TICK_SECONDS) -> None:
    """Advance one simulation tick (default: 1 second of wall clock)."""
    _transition(state)
    _apply_scenario(state)
    _update_gps(state, dt_seconds)


def get_gps(state: LocomotiveState) -> tuple[float, float]:
    """Return the cached (lat, lon) for the current tick."""
    return state.lat, state.lon
