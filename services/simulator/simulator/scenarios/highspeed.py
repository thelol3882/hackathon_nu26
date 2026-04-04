"""High-speed scenario — all locomotives start at cruising speed immediately."""

from __future__ import annotations

from shared.enums import LocomotiveType
from simulator.models.locomotive_state import LocomotiveMode, LocomotiveState, _enter_mode

_SHORT_DEPOT_TICKS = 5


def apply_highspeed(fleet: list[LocomotiveState], tick_count: int) -> None:
    """Start every locomotive at high cruising speed from tick 0.

    - Tick 0: force all locos into CRUISING at 80-100 km/h with high throttle.
    - Ongoing: any loco that enters DEPOT or AESS_SLEEP is kicked back to
      CRUISING immediately with speed restored.
    """
    for loco in fleet:
        if tick_count == 0:
            _force_cruising(loco)
            continue

        if loco.mode in (LocomotiveMode.DEPOT, LocomotiveMode.AESS_SLEEP):
            remaining = loco.mode_duration - loco.mode_ticks
            if remaining > _SHORT_DEPOT_TICKS:
                loco.mode_duration = loco.mode_ticks + _SHORT_DEPOT_TICKS

        # If a loco somehow dropped speed while cruising, bump it back up
        if loco.mode == LocomotiveMode.CRUISING and loco.speed < 60.0:
            loco.speed = 80.0


def _force_cruising(loco: LocomotiveState) -> None:
    """Set a locomotive directly into high-speed cruising."""
    _enter_mode(loco, LocomotiveMode.CRUISING)
    loco.speed = 90.0
    if loco.loco_type == LocomotiveType.TE33A:
        loco.notch = 7  # high throttle → high RPM, fuel burn, temps
