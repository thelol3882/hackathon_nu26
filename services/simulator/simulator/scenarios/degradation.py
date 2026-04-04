"""Degradation scenario — gradual IGBT overheating on one KZ8A locomotive."""

from __future__ import annotations

from shared.enums import LocomotiveType
from simulator.models.locomotive_state import LocomotiveState

# IGBT overheating timeline (20 minutes = 1200 ticks at 1 Hz)
_IGBT_START = 57.0  # normal temp
_IGBT_END = 87.0  # emergency level
_DURATION_TICKS = 1200
_TARGET_LOCO_IDX: int | None = None


def apply_degradation(fleet: list[LocomotiveState], tick_count: int) -> None:
    """Linearly increase IGBT temp on a selected KZ8A from 57 to 87 C over 20 min."""
    global _TARGET_LOCO_IDX

    # Select target once: first KZ8A in cruising or any active state
    if _TARGET_LOCO_IDX is None:
        for i, loco in enumerate(fleet):
            if loco.loco_type == LocomotiveType.KZ8A:
                _TARGET_LOCO_IDX = i
                break
        if _TARGET_LOCO_IDX is None:
            return

    loco = fleet[_TARGET_LOCO_IDX]
    progress = min(1.0, tick_count / _DURATION_TICKS)
    loco.igbt_override = _IGBT_START + (_IGBT_END - _IGBT_START) * progress


def reset() -> None:
    global _TARGET_LOCO_IDX
    _TARGET_LOCO_IDX = None
