"""Background task: persist alerts from Redis pub/sub to PostgreSQL."""

from __future__ import annotations

import asyncio

import redis.asyncio as redis
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from api_gateway.models.alert_entity import AlertRecord
from api_gateway.repositories import alert_repository
from shared.constants import ALERT_CHANNEL
from shared.log_codes import (
    ALERT_LISTENER_ERROR,
    ALERT_LISTENER_STARTED,
    ALERT_PERSIST_FAILED,
    ALERT_PERSISTED,
)
from shared.observability import get_logger
from shared.schemas.alert import AlertEvent
from shared.wire import decode as wire_decode

logger = get_logger(__name__)

_ALERT_BATCH_WINDOW = 0.2


async def run_alert_persistence(
    redis_client: redis.Redis,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Subscribe to alerts:live and persist alerts to the DB in batches."""
    backoff = 1.0
    while True:
        pubsub = redis_client.pubsub()
        try:
            await pubsub.subscribe(ALERT_CHANNEL)
            backoff = 1.0
            logger.info("Alert persistence listener started", code=ALERT_LISTENER_STARTED)
            batch: list[AlertRecord] = []
            flush_handle: asyncio.TimerHandle | None = None
            loop = asyncio.get_event_loop()

            async def _flush() -> None:
                nonlocal batch
                if not batch:
                    return
                to_flush = batch
                batch = []
                try:
                    async with session_factory() as session:
                        await alert_repository.bulk_insert(session, to_flush)
                        logger.debug(
                            "Alerts persisted",
                            code=ALERT_PERSISTED,
                            count=len(to_flush),
                        )
                except Exception:
                    logger.exception("Failed to persist alerts batch", code=ALERT_PERSIST_FAILED)

            async for message in pubsub.listen():
                msg_type = message.get("type", b"")
                if msg_type not in (b"message", "message"):
                    continue
                try:
                    data = wire_decode(message["data"])
                    alert = AlertEvent.model_validate(data)
                    batch.append(
                        AlertRecord(
                            id=alert.id,
                            locomotive_id=alert.locomotive_id,
                            sensor_type=alert.sensor_type,
                            severity=alert.severity,
                            value=alert.value,
                            threshold_min=alert.threshold_min,
                            threshold_max=alert.threshold_max,
                            message=alert.message,
                            recommendation=alert.recommendation,
                            timestamp=alert.timestamp,
                            acknowledged=alert.acknowledged,
                        )
                    )
                    if flush_handle is None or flush_handle.cancelled():
                        flush_handle = loop.call_later(
                            _ALERT_BATCH_WINDOW,
                            lambda: asyncio.ensure_future(_flush()),
                        )
                except Exception:
                    logger.exception("Failed to parse alert", code=ALERT_PERSIST_FAILED)
        except asyncio.CancelledError:
            break
        except Exception:
            logger.exception("Alert listener error, reconnecting", code=ALERT_LISTENER_ERROR, backoff_s=backoff)
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, 30.0)
        finally:
            try:
                await pubsub.unsubscribe()
                await pubsub.aclose()
            except Exception:
                logger.debug("Failed to close pubsub during cleanup")
