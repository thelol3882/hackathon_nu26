"""
Fleet health aggregator — background task that maintains a real-time
overview of all locomotives in the fleet.

HOW IT WORKS:
  1. Subscribes to health:live:* via Redis pattern subscribe
  2. For each incoming HealthIndex, updates an in-memory dict
  3. Every PUBLISH_INTERVAL seconds, computes fleet summary:
     - Count per category (Норма / Внимание / Критично)
     - Average score across fleet
     - Top 10 worst locomotives
     - Locomotives whose category changed since last publish
  4. Publishes summary and changes to Redis Pub/Sub
  5. WS Server picks them up and streams to fleet dashboard

MEMORY USAGE:
  1700 locomotives × ~200 bytes per entry ≈ 340 KB.
  Negligible. Even 100,000 locomotives would be ~20 MB.

WHY IN-MEMORY AND NOT REDIS HASH:
  Reading HGETALL with 1700 keys every second adds unnecessary
  Redis round-trips. In-memory dict is instant. The tradeoff is
  that this task must be a singleton (can't run multiple replicas).

PUBLISH STRATEGY:
  fleet:summary — published every PUBLISH_INTERVAL regardless.
    Contains full fleet stats. Small payload (~500 bytes).
    Frontend uses this for the summary bar (counts, avg score).

  fleet:changes — published only when a locomotive changes category.
    Contains only the changed locomotives. Frontend uses this for
    point updates on the map without re-rendering all 1700 markers.

  This two-channel approach minimizes both network traffic and
  frontend re-renders. Summary is cheap to process (one object),
  changes are sparse (most ticks, nothing changes).

SINGLETON CONSTRAINT:
  This aggregator is stateful — it holds all 1700 locomotive states
  in memory. Running two copies would produce duplicate publishes.
  Currently runs inside Analytics Service as a background task.
  If Analytics needs horizontal scaling, extract this into a
  separate fleet-aggregator container. The code is self-contained
  in this module to make that move trivial.
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

# How often to publish fleet summary (seconds).
# 2 seconds balances real-time feel vs. Redis/WS load.
PUBLISH_INTERVAL = 2.0

_CATEGORY_NORMA = "Норма"
_CATEGORY_VNIMANIE = "Внимание"


class _LocoState:
    """In-memory state for one locomotive. Uses __slots__ to save memory."""

    __slots__ = ("category", "locomotive_id", "locomotive_type", "score", "updated_at")

    def __init__(self, locomotive_id: str, locomotive_type: str, score: float, category: str) -> None:
        self.locomotive_id = locomotive_id
        self.locomotive_type = locomotive_type
        self.score = score
        self.category = category
        self.updated_at = datetime.now(UTC)


class FleetAggregator:
    """Maintains real-time fleet overview by listening to health:live:*
    and publishing aggregated summaries.

    Usage (in Analytics Service main.py):
        aggregator = FleetAggregator(redis_client)
        task = asyncio.create_task(aggregator.run())
        # ... on shutdown:
        aggregator.stop()
        task.cancel()
    """

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
        """Main loop: listener + publisher running concurrently."""
        listener_task = asyncio.create_task(self._listen_loop(), name="fleet-listener")
        publisher_task = asyncio.create_task(self._publish_loop(), name="fleet-publisher")
        try:
            await asyncio.gather(listener_task, publisher_task)
        except asyncio.CancelledError:
            pass
        finally:
            listener_task.cancel()
            publisher_task.cancel()

    # -- Listener ----------------------------------------------------------

    async def _listen_loop(self) -> None:
        """Subscribe to health:live:* and update in-memory state.

        Pattern subscribe (psubscribe) matches all channels that start
        with "health:live:". Each message contains a wire-encoded
        HealthIndex dict from the processor.

        Reconnects with exponential backoff if Redis connection drops.
        """
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
        """Update in-memory state for one locomotive.

        If the locomotive's category changed (e.g. Норма → Внимание),
        record it in _changes for the next publish cycle.
        """
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

        # Track category transitions for fleet:changes channel
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

    # -- Publisher ----------------------------------------------------------

    async def _publish_loop(self) -> None:
        """Periodically compute and publish fleet summary + changes.

        Uses a Redis pipeline to publish both channels in one round-trip.
        """
        while self._running:
            try:
                await asyncio.sleep(PUBLISH_INTERVAL)

                if not self._fleet:
                    continue

                summary = self._compute_summary()
                changes = self._drain_changes()

                # Publish both in one pipeline (one Redis round-trip)
                pipe = self._redis.pipeline(transaction=False)
                pipe.publish(FLEET_SUMMARY_CHANNEL, wire_encode(summary))
                if changes:
                    pipe.publish(FLEET_CHANGES_CHANNEL, wire_encode({"changes": changes}))
                await pipe.execute()

                # Update Prometheus metrics
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
        """Compute fleet-wide statistics from in-memory state.

        Returns a compact summary for the fleet dashboard:
        - Category counts (how many in each state)
        - Average score across fleet
        - Top 10 worst locomotives (lowest HI score)
        - Fleet size and timestamp

        Iterating 1700 entries takes <1ms in Python — no concern.
        """
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

        # Sort ascending by score, take bottom 10
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
        """Return accumulated changes and clear the buffer.

        Thread-safe because asyncio is single-threaded — no locks needed.
        """
        changes = self._changes
        self._changes = []
        return changes
