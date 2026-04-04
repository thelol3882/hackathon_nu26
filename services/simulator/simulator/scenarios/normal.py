"""Normal scenario — all locomotives at 1 Hz, standard state machine."""

from __future__ import annotations

from simulator.models.locomotive_state import LocomotiveState


def apply_normal(fleet: list[LocomotiveState], tick_count: int) -> None:
    """No-op: normal scenario just runs the standard state machine."""
