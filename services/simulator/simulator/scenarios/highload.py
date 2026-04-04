"""Highload scenario — burst multiplier reduces tick interval."""

from __future__ import annotations

from simulator.models.locomotive_state import LocomotiveState


def apply_highload(fleet: list[LocomotiveState], tick_count: int) -> None:
    """Highload is handled at the runner level via burst_multiplier config.
    No per-loco overrides needed — all locos just tick faster."""
