"""Fleet health aggregator: in-memory fleet state driven by health:live:*.

Subscribes to per-locomotive HealthIndex pub/sub, keeps latest state in an
in-memory dict, and periodically publishes a compact fleet summary plus a
delta of category changes. Must run as a singleton (stateful). In-memory
is preferred over Redis HGETALL for per-tick reads.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

import redis.asyncio as aioredis

from shared.constants import (
    FLEET_CHANGES_CHANNEL,
    FLEET_SUMMARY_CHANNEL,
    HEALTH_CHANNEL,
)
from shared.observability import get_logger
from shared.observability.prometheus import (
    fleet_aggregator_size,
    fleet_changes_detected,
    fleet_summary_published,
)
from shared.wire import decode as wire_decode
from shared.wire import encode as wire_encode

logger = get_logger(__name__)

# Balances real-time feel vs. Redis/WS load.
PUBLISH_INTERVAL = 2.0

_CATEGORY_NORMA = "Норма"
_CATEGORY_VNIMANIE = "Внимание"


class _LocoState:
    """In-memory state for one locomotive."""

    __slots__ = ("category", "locomotive_id", "locomotive_type", "score", "updated_at")

    def __init__(self, locomotive_id: str, locomotive_type: str, score: float, category: str) -> None:
        self.locomotive_id = locomotive_id
        self.locomotive_type = locomotive_type
        self.score = score
        self.category = category
        self.updated_at = datetime.now(UTC)


class FleetAggregator:
    """Listens to health:live:* and publishes aggregated fleet summaries."""

    def __init__(self, redis_client: aioredis.Redis) -> None:
        self._redis = redis_client
        self._fleet: dict[str, _LocoState] = {}
        self._changes: list[dict] = []
        self._running = True

    @property
    def fleet_size(self) -> int:
        return len(self._fleet)

    def stop(self) -> None:
        self._running = False

    async def run(self) -> None:
        """Run listener and publisher concurrently."""
        listener_task = asyncio.create_task(self._listen_loop(), name="fleet-listener")
        publisher_task = asyncio.create_task(self._publish_loop(), name="fleet-publisher")
        try:
            await asyncio.gather(listener_task, publisher_task)
        except asyncio.CancelledError:
            pass
        finally:
            listener_task.cancel()
            publisher_task.cancel()

    async def _listen_loop(self) -> None:
        """Subscribe to health:live:* and update state; reconnect with backoff."""
        backoff = 1.0
        while self._running:
            pubsub = self._redis.pubsub()
            try:
                await pubsub.psubscribe(f"{HEALTH_CHANNEL}:*")
                backoff = 1.0
                logger.info("Fleet aggregator listener started")

                async for message in pubsub.listen():
                    if not self._running:
                        break
                    if message["type"] != "pmessage":
                        continue
                    try:
                        data = wire_decode(message["data"])
                        self._update_state(data)
                    except Exception:
                        logger.exception("Failed to process health message")

            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("Fleet listener error, reconnecting", backoff_s=backoff)
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 30.0)
            finally:
                try:
                    await pubsub.punsubscribe()
                    await pubsub.aclose()
                except Exception:
                    pass

    def _update_state(self, data: dict) -> None:
        """Update locomotive state and record category transitions."""
        loco_id = str(data.get("locomotive_id", ""))
        if not loco_id:
            return

        new_score = float(data.get("overall_score", 0))
        new_category = str(data.get("category", ""))
        locomotive_type = str(data.get("locomotive_type", ""))

        old_state = self._fleet.get(loco_id)
        old_category = old_state.category if old_state else None

        self._fleet[loco_id] = _LocoState(
            locomotive_id=loco_id,
            locomotive_type=locomotive_type,
            score=new_score,
            category=new_category,
        )

        if old_category is not None and old_category != new_category:
            self._changes.append(
                {
                    "locomotive_id": loco_id,
                    "locomotive_type": locomotive_type,
                    "old_category": old_category,
                    "new_category": new_category,
                    "score": new_score,
                    "timestamp": datetime.now(UTC).isoformat(),
                }
            )

    async def _publish_loop(self) -> None:
        """Periodically publish fleet summary and changes via one pipeline."""
        while self._running:
            try:
                await asyncio.sleep(PUBLISH_INTERVAL)

                if not self._fleet:
                    continue

                summary = self._compute_summary()
                changes = self._drain_changes()

                pipe = self._redis.pipeline(transaction=False)
                pipe.publish(FLEET_SUMMARY_CHANNEL, wire_encode(summary))
                if changes:
                    pipe.publish(FLEET_CHANGES_CHANNEL, wire_encode({"changes": changes}))
                await pipe.execute()

                fleet_aggregator_size.set(len(self._fleet))
                fleet_summary_published.inc()
                if changes:
                    fleet_changes_detected.inc(len(changes))

                logger.debug(
                    "Fleet summary published",
                    fleet_size=len(self._fleet),
                    changes=len(changes),
                )

            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("Fleet publisher error")

    def _compute_summary(self) -> dict:
        """Return compact fleet stats: category counts, avg score, worst 10."""
        norma = 0
        vnimanie = 0
        kritichno = 0
        total_score = 0.0
        worst: list[tuple[float, _LocoState]] = []

        for state in self._fleet.values():
            total_score += state.score
            if state.category == _CATEGORY_NORMA:
                norma += 1
            elif state.category == _CATEGORY_VNIMANIE:
                vnimanie += 1
            else:
                kritichno += 1
            worst.append((state.score, state))

        worst.sort(key=lambda x: x[0])
        top_worst = [
            {
                "locomotive_id": s.locomotive_id,
                "locomotive_type": s.locomotive_type,
                "score": round(s.score, 1),
                "category": s.category,
            }
            for _, s in worst[:10]
        ]

        fleet_size = len(self._fleet)

        return {
            "type": "fleet_summary",
            "fleet_size": fleet_size,
            "avg_score": round(total_score / max(fleet_size, 1), 1),
            "categories": {
                "norma": norma,
                "vnimanie": vnimanie,
                "kritichno": kritichno,
            },
            "worst_10": top_worst,
            "timestamp": datetime.now(UTC).isoformat(),
        }

    def _drain_changes(self) -> list[dict]:
        """Return accumulated changes and clear the buffer."""
        changes = self._changes
        self._changes = []
        return changes
