"""Emergency scenario — brake pipe rupture on one locomotive."""

from __future__ import annotations

from simulator.models.locomotive_state import LocomotiveState

# Brake pipe drops 5.1 → 1.8 bar over 10 seconds
_BRAKE_START = 5.1
_BRAKE_END = 1.8
_DURATION_TICKS = 10
_TARGET_LOCO_IDX: int | None = None


def apply_emergency(fleet: list[LocomotiveState], tick_count: int) -> None:
    """Drop brake pipe pressure on a selected locomotive over 10 seconds."""
    global _TARGET_LOCO_IDX

    if _TARGET_LOCO_IDX is None:
        # Pick first locomotive with speed > 50 km/h
        for i, loco in enumerate(fleet):
            if loco.speed > 50:
                _TARGET_LOCO_IDX = i
                break
        if _TARGET_LOCO_IDX is None:
            return

    loco = fleet[_TARGET_LOCO_IDX]
    if tick_count <= _DURATION_TICKS:
        progress = tick_count / _DURATION_TICKS
        loco.brake_override = _BRAKE_START + (_BRAKE_END - _BRAKE_START) * progress
    else:
        # Stay at emergency level
        loco.brake_override = _BRAKE_END


def reset() -> None:
    global _TARGET_LOCO_IDX
    _TARGET_LOCO_IDX = None
