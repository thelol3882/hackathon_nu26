"""Driving scenario — keeps the fleet moving with short depot stops."""

from __future__ import annotations

from simulator.models.locomotive_state import LocomotiveMode, LocomotiveState, _enter_mode

_SHORT_DEPOT_TICKS = 10  # ~10 seconds at 1 Hz before departing again


def apply_driving(fleet: list[LocomotiveState], tick_count: int) -> None:
    """Force locomotives to stay on the move.

    - Locos stuck in DEPOT get a short countdown and depart quickly.
    - Locos in AESS_SLEEP are woken up immediately.
    - On first tick, kick everyone into DEPARTURE so the demo starts moving.
    """
    for loco in fleet:
        if tick_count == 0:
            # First tick: get everyone moving
            if loco.mode == LocomotiveMode.DEPOT:
                _enter_mode(loco, LocomotiveMode.DEPARTURE)
            continue

        if loco.mode == LocomotiveMode.DEPOT:
            remaining = loco.mode_duration - loco.mode_ticks
            if remaining > _SHORT_DEPOT_TICKS:
                loco.mode_duration = loco.mode_ticks + _SHORT_DEPOT_TICKS

        elif loco.mode == LocomotiveMode.AESS_SLEEP:
            _enter_mode(loco, LocomotiveMode.DEPARTURE)
