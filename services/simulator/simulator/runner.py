"""Simulation runner — orchestrates fleet ticks, batching, and HTTP delivery."""

from __future__ import annotations

import asyncio
import random
import time
from collections import deque
from datetime import UTC, datetime

from shared.enums import LocomotiveType
from shared.observability import get_logger
from shared.schemas.telemetry import GPSCoordinate, SensorPayload, TelemetryReading
from simulator.core.client import close_client, post_batch
from simulator.core.config import settings
from simulator.generators.kz8a import generate_kz8a
from simulator.generators.te33a import generate_te33a
from simulator.models.fleet import generate_fleet
from simulator.models.locomotive_state import (
    LocomotiveState,
    get_gps,
    tick,
)
from simulator.scenarios.degradation import apply_degradation
from simulator.scenarios.degradation import reset as reset_degradation
from simulator.scenarios.driving import apply_driving
from simulator.scenarios.emergency import apply_emergency
from simulator.scenarios.emergency import reset as reset_emergency
from simulator.scenarios.highload import apply_highload
from simulator.scenarios.highspeed import apply_highspeed
from simulator.scenarios.normal import apply_normal

logger = get_logger(__name__)

SCENARIO_HANDLERS = {
    "normal": apply_normal,
    "driving": apply_driving,
    "highspeed": apply_highspeed,
    "highload": apply_highload,
    "degradation": apply_degradation,
    "emergency": apply_emergency,
}

BUFFER_MAX = 10_000


class SimulationRunner:
    def __init__(self) -> None:
        self.fleet: list[LocomotiveState] = []
        self.scenario: str = settings.scenario
        self.tick_count: int = 0
        self.events_sent: int = 0
        self.errors: int = 0
        self.buffer: deque[dict] = deque(maxlen=BUFFER_MAX)
        self.running: bool = False
        self._burst_multiplier: float = settings.burst_multiplier
        self._burst_until: float = 0.0  # timestamp when burst expires
        self._last_log_time: float = 0.0
        self._events_since_log: int = 0

    def init_fleet(self) -> None:
        random.seed(settings.seed)
        self.fleet = generate_fleet(settings.fleet_size, gateway_url=settings.gateway_url)
        logger.info("Fleet initialized: %d locomotives", len(self.fleet))

    def resize_fleet(self, n: int) -> None:
        random.seed(settings.seed)
        self.fleet = generate_fleet(n, gateway_url=settings.gateway_url)
        logger.info("Fleet resized to %d locomotives", n)

    def switch_scenario(self, name: str) -> None:
        if name not in SCENARIO_HANDLERS:
            raise ValueError(f"Unknown scenario: {name}")
        self.scenario = name
        self.tick_count = 0
        # Reset scenario state
        reset_degradation()
        reset_emergency()
        for loco in self.fleet:
            loco.igbt_override = None
            loco.brake_override = None
        logger.info("Scenario switched to: %s", name)

    def set_burst(self, multiplier: float, duration: float) -> None:
        self._burst_multiplier = multiplier
        self._burst_until = time.monotonic() + duration
        logger.info("Burst started: x%.1f for %.0fs", multiplier, duration)

    @property
    def effective_multiplier(self) -> float:
        if time.monotonic() < self._burst_until:
            return self._burst_multiplier
        return settings.burst_multiplier

    def get_metrics(self) -> dict:
        return {
            "tick_count": self.tick_count,
            "fleet_size": len(self.fleet),
            "scenario": self.scenario,
            "events_sent": self.events_sent,
            "errors": self.errors,
            "buffer_size": len(self.buffer),
            "burst_multiplier": self.effective_multiplier,
            "running": self.running,
        }

    def sample_fleet(self, n: int = 5) -> list[dict]:
        sample = random.sample(self.fleet, min(n, len(self.fleet)))
        return [
            {
                "id": str(s.id),
                "type": s.loco_type.value,
                "mode": s.mode.value,
                "speed": round(s.speed, 1),
                "route": s.route.name,
                "progress": round(s.route_progress, 4),
            }
            for s in sample
        ]

    async def run(self) -> None:
        self.running = True
        self._last_log_time = time.monotonic()
        logger.info(
            "Runner started: scenario=%s, fleet=%d, tick=%.2fs",
            self.scenario,
            len(self.fleet),
            settings.tick_interval,
        )

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
                        "[SIMULATOR] tick=%d | events_sent=%d | errors=%d | buffer=%d | events/s=%.0f",
                        self.tick_count,
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
        handler = SCENARIO_HANDLERS.get(self.scenario, apply_normal)
        handler(self.fleet, self.tick_count)

        readings: list[dict] = []
        now = datetime.now(UTC)

        for loco in self.fleet:
            tick(loco)
            sensors = _generate_sensors(loco)
            lat, lon = get_gps(loco)

            reading = TelemetryReading(
                locomotive_id=loco.id,
                locomotive_type=loco.loco_type,
                timestamp=now,
                sample_rate_hz=1.0 * self.effective_multiplier,
                gps=GPSCoordinate(latitude=lat, longitude=lon),
                sensors=sensors,
            )
            readings.append(reading.model_dump(mode="json"))

        batch_size = settings.batch_size
        if self.effective_multiplier > 1:
            batch_size = 200  # larger batches for highload

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
        """Try to send buffered readings."""
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

    def stop(self) -> None:
        self.running = False


def _generate_sensors(loco: LocomotiveState) -> list[SensorPayload]:
    if loco.loco_type == LocomotiveType.TE33A:
        return generate_te33a(loco)
    return generate_kz8a(loco)


# Singleton runner instance
runner = SimulationRunner()
