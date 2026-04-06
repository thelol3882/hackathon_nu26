"""Simulation runner — orchestrates per-locomotive ticks and telemetry delivery.

The runner used to manage a single global "scenario" knob applied to a
flat list of 1700 locomotives. After the rewrite, it manages an
operator-built dict of locomotives, each carrying its own scenario,
mode and route sub-segment. There is no fleet-wide scenario any more.

Operators interact through ``services/simulator/main.py`` which calls
``add_locomotive`` / ``update_locomotive`` / ``remove_locomotive`` on
this runner instance.
"""

from __future__ import annotations

import asyncio
import time
from collections import deque
from collections.abc import Iterable
from datetime import UTC, datetime
from uuid import UUID

from shared.enums import LocomotiveType
from shared.observability import get_logger
from shared.route_geometry import Route, get_route
from shared.schemas.telemetry import GPSCoordinate, SensorPayload, TelemetryReading
from simulator.core.client import close_client, post_batch
from simulator.core.config import settings
from simulator.generators.kz8a import generate_kz8a
from simulator.generators.te33a import generate_te33a
from simulator.models.locomotive_state import (
    LocomotiveMode,
    LocomotiveScenario,
    LocomotiveState,
    OnArrival,
    get_gps,
    tick,
)

logger = get_logger(__name__)

BUFFER_MAX = 10_000


class LocomotiveNotFoundError(KeyError):
    """Raised when an operator references a UUID that isn't in the fleet."""


class SimulationRunner:
    """Owns the live fleet and the tick loop.

    Mutating methods (``add_locomotive``, ``update_locomotive``,
    ``remove_locomotive``) are safe to call from HTTP handlers running
    on the same event loop as ``run()`` — Python's GIL plus
    asyncio's cooperative scheduling means a tick is atomic w.r.t.
    HTTP requests. No locks needed for a pet project at this scale.
    """

    def __init__(self) -> None:
        # UUID-keyed for O(1) lookup. Order is preserved (insertion
        # order) so list-style iteration in the tick loop is stable.
        self.fleet: dict[UUID, LocomotiveState] = {}
        self.tick_count: int = 0
        self.events_sent: int = 0
        self.errors: int = 0
        self.buffer: deque[dict] = deque(maxlen=BUFFER_MAX)
        self.running: bool = False
        self._burst_multiplier: float = settings.burst_multiplier
        self._burst_until: float = 0.0  # timestamp when burst expires
        self._last_log_time: float = 0.0
        self._events_since_log: int = 0

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def init_fleet(self) -> None:
        """Boot empty. Operators add locomotives via the HTTP API.

        We deliberately do *not* call the legacy ``generate_fleet``
        helper here — it built a load-test fleet of 1700 random
        locomotives, which is the wrong shape for the new game-like
        model. The dashboard creates the fleet by hand instead.
        """
        self.fleet = {}
        logger.info("Simulator booted with empty fleet (operator-managed)")

    def stop(self) -> None:
        self.running = False

    # ------------------------------------------------------------------
    # CRUD — operator-driven
    # ------------------------------------------------------------------

    def add_locomotive(
        self,
        *,
        loco_id: UUID,
        loco_type: LocomotiveType,
        route_name: str,
        name: str = "",
        start_km: float = 0.0,
        end_km: float | None = None,
        mode: LocomotiveMode = LocomotiveMode.DEPOT,
        scenario: LocomotiveScenario = LocomotiveScenario.NORMAL,
        on_arrival: OnArrival = OnArrival.LOOP,
        auto_mode: bool = False,
        initial_speed_kmh: float = 0.0,
    ) -> LocomotiveState:
        """Materialise a new ``LocomotiveState`` and register it.

        Position bounds are passed in as kilometres-from-start because
        that's what the dashboard knows about (it picks station km
        from /routes), but stored internally in metres for the
        kinematics. Looking the route up by name keeps the request
        body small and stable across container restarts.
        """
        route = get_route(route_name)
        if route is None:
            raise ValueError(f"Unknown route: {route_name!r}")
        end_km_resolved = route.length_m / 1000.0 if end_km is None else end_km
        # Normalise + clamp into the route. The state's __post_init__
        # also clamps as a safety net but doing it here too gives the
        # caller a clean validated value back.
        start_m = max(0.0, min(start_km, route.length_m / 1000.0)) * 1000.0
        end_m = max(start_m / 1000.0, min(end_km_resolved, route.length_m / 1000.0)) * 1000.0

        if loco_id in self.fleet:
            raise ValueError(f"Locomotive {loco_id} already in simulator")

        state = LocomotiveState(
            id=loco_id,
            loco_type=loco_type,
            route=route,
            name=name,
            mode=mode,
            scenario=scenario,
            auto_mode=auto_mode,
            speed=initial_speed_kmh,
            distance_m=start_m,
            start_distance_m=start_m,
            end_distance_m=end_m,
            on_arrival=on_arrival,
            forward=True,
        )
        self.fleet[loco_id] = state
        logger.info(
            "Added locomotive",
            id=str(loco_id),
            type=loco_type.value,
            route=route_name,
            mode=mode.value,
            scenario=scenario.value,
        )
        return state

    def update_locomotive(
        self,
        loco_id: UUID,
        *,
        route_name: str | None = None,
        start_km: float | None = None,
        end_km: float | None = None,
        mode: LocomotiveMode | None = None,
        scenario: LocomotiveScenario | None = None,
        on_arrival: OnArrival | None = None,
        auto_mode: bool | None = None,
        speed_kmh: float | None = None,
        name: str | None = None,
    ) -> LocomotiveState:
        """Apply a partial update to an existing locomotive.

        Any field left as ``None`` is preserved. Changing the route
        rebuilds the position bounds (the locomotive is snapped to the
        new route's start). Changing scenario resets the scenario
        tick counter so the degradation/emergency ramp starts fresh.
        """
        state = self.fleet.get(loco_id)
        if state is None:
            raise LocomotiveNotFoundError(loco_id)

        if route_name is not None:
            new_route = get_route(route_name)
            if new_route is None:
                raise ValueError(f"Unknown route: {route_name!r}")
            state.route = new_route
            state.start_distance_m = 0.0
            state.end_distance_m = new_route.length_m
            state.distance_m = 0.0

        if start_km is not None:
            state.start_distance_m = max(0.0, min(start_km * 1000.0, state.route.length_m))
        if end_km is not None:
            state.end_distance_m = max(state.start_distance_m, min(end_km * 1000.0, state.route.length_m))
        # Re-clamp position into the (possibly new) sub-segment.
        state.distance_m = max(state.start_distance_m, min(state.distance_m, state.end_distance_m))

        if mode is not None:
            state.mode = mode
            state.mode_ticks = 0
        if scenario is not None and scenario != state.scenario:
            state.scenario = scenario
            state.scenario_tick = 0
            # Re-arming a normal scenario clears any leftover overrides
            # immediately rather than waiting for the next tick.
            if scenario == LocomotiveScenario.NORMAL:
                state.igbt_override = None
                state.brake_override = None
        if on_arrival is not None:
            state.on_arrival = on_arrival
        if auto_mode is not None:
            state.auto_mode = auto_mode
        if speed_kmh is not None:
            state.speed = max(0.0, speed_kmh)
        if name is not None:
            state.name = name

        # Refresh cached pose so the next telemetry frame already
        # reflects the operator's edits without waiting for a tick.
        state.lat, state.lon, state.bearing_deg = state.route.position_at(state.distance_m)
        return state

    def remove_locomotive(self, loco_id: UUID) -> None:
        if loco_id not in self.fleet:
            raise LocomotiveNotFoundError(loco_id)
        del self.fleet[loco_id]
        logger.info("Removed locomotive", id=str(loco_id))

    def get_locomotive(self, loco_id: UUID) -> LocomotiveState:
        state = self.fleet.get(loco_id)
        if state is None:
            raise LocomotiveNotFoundError(loco_id)
        return state

    def list_locomotives(self) -> Iterable[LocomotiveState]:
        return self.fleet.values()

    # ------------------------------------------------------------------
    # Burst multiplier (kept from the old simulator for load-testing)
    # ------------------------------------------------------------------

    def set_burst(self, multiplier: float, duration: float) -> None:
        self._burst_multiplier = multiplier
        self._burst_until = time.monotonic() + duration
        logger.info("Burst started: x%.1f for %.0fs", multiplier, duration)

    @property
    def effective_multiplier(self) -> float:
        if time.monotonic() < self._burst_until:
            return self._burst_multiplier
        return settings.burst_multiplier

    # ------------------------------------------------------------------
    # Status / introspection
    # ------------------------------------------------------------------

    def get_metrics(self) -> dict:
        return {
            "tick_count": self.tick_count,
            "fleet_size": len(self.fleet),
            "events_sent": self.events_sent,
            "errors": self.errors,
            "buffer_size": len(self.buffer),
            "burst_multiplier": self.effective_multiplier,
            "running": self.running,
        }

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------

    async def run(self) -> None:
        self.running = True
        self._last_log_time = time.monotonic()
        logger.info("Runner started: tick=%.2fs", settings.tick_interval)

        try:
            while self.running:
                tick_start = time.monotonic()
                await self._do_tick()
                self.tick_count += 1

                now = time.monotonic()
                if now - self._last_log_time >= 5.0:
                    elapsed = now - self._last_log_time
                    rate = self._events_since_log / elapsed if elapsed > 0 else 0
                    logger.info(
                        "[SIMULATOR] tick=%d | fleet=%d | events_sent=%d | errors=%d | buffer=%d | events/s=%.0f",
                        self.tick_count,
                        len(self.fleet),
                        self.events_sent,
                        self.errors,
                        len(self.buffer),
                        rate,
                    )
                    self._last_log_time = now
                    self._events_since_log = 0

                elapsed = time.monotonic() - tick_start
                interval = settings.tick_interval / self.effective_multiplier
                sleep_time = max(0, interval - elapsed)
                if sleep_time > 0:
                    await asyncio.sleep(sleep_time)
        finally:
            await close_client()
            self.running = False

    async def _do_tick(self) -> None:
        if not self.fleet:
            return  # nothing to simulate yet — operator hasn't created any

        readings: list[dict] = []
        now = datetime.now(UTC)

        # Snapshot first because tick() may set `arrived` and we want
        # to drop those at the end of the loop without mutating the
        # dict mid-iteration.
        for loco in list(self.fleet.values()):
            tick(loco)
            sensors = _generate_sensors(loco)
            lat, lon = get_gps(loco)

            reading = TelemetryReading(
                locomotive_id=loco.id,
                locomotive_type=loco.loco_type,
                timestamp=now,
                sample_rate_hz=1.0 * self.effective_multiplier,
                gps=GPSCoordinate(
                    latitude=lat,
                    longitude=lon,
                    bearing_deg=loco.bearing_deg,
                ),
                sensors=sensors,
                route_name=loco.route.name,
            )
            readings.append(reading.model_dump(mode="json"))

        # Drop locomotives that finished a one-shot REMOVE trip.
        for lid, loco in list(self.fleet.items()):
            if loco.arrived and loco.on_arrival == OnArrival.REMOVE:
                logger.info("Locomotive %s arrived → removing", lid)
                del self.fleet[lid]

        if not readings:
            return

        batch_size = settings.batch_size
        if self.effective_multiplier > 1:
            batch_size = 200

        batches = [readings[i : i + batch_size] for i in range(0, len(readings), batch_size)]
        results = await asyncio.gather(*[post_batch(b) for b in batches], return_exceptions=True)
        for batch, result in zip(batches, results, strict=True):
            if result is not None and not isinstance(result, BaseException):
                self.events_sent += len(batch)
                self._events_since_log += len(batch)
            else:
                self.errors += 1
                for r in batch:
                    self.buffer.append(r)

        if self.buffer:
            await self._flush_buffer(batch_size)

    async def _flush_buffer(self, batch_size: int) -> None:
        retries = min(3, len(self.buffer) // batch_size + 1)
        for _ in range(retries):
            if not self.buffer:
                break
            batch = [self.buffer.popleft() for _ in range(min(batch_size, len(self.buffer)))]
            result = await post_batch(batch)
            if result is not None:
                self.events_sent += len(batch)
                self._events_since_log += len(batch)
            else:
                for r in reversed(batch):
                    self.buffer.appendleft(r)
                break


# Singleton runner instance
runner = SimulationRunner()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _generate_sensors(loco: LocomotiveState) -> list[SensorPayload]:
    if loco.loco_type == LocomotiveType.TE33A:
        return generate_te33a(loco)
    return generate_kz8a(loco)


__all__ = [
    "LocomotiveNotFoundError",
    "Route",  # re-exported for convenience
    "SimulationRunner",
    "runner",
]
