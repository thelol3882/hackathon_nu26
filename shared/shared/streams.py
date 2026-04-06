"""Redis Streams helpers for durable processor -> db-writer delivery.

Each message has a single field ``"d"`` = ``wire.encode({"rows": [...]})``.
Consumer groups give at-least-once delivery: db-writer acks only after commit.
"""

from __future__ import annotations

import redis.asyncio as aioredis

from shared.wire import encode as wire_encode

TELEMETRY_STREAM = "stream:telemetry"
ALERTS_STREAM = "stream:alerts"
HEALTH_STREAM = "stream:health"

DB_WRITER_GROUP = "db-writers"

STREAM_BATCH_SIZE = 500  # legacy, kept for compatibility

# XREADGROUP batch sizes. Telemetry is kept small so the writer can flush
# and ACK before the next read — this breaks a death-spiral feedback loop
# on the hot stream. Alerts/health are low volume and safe to read larger.
READER_BATCH_SIZE_TELEMETRY = 50
READER_BATCH_SIZE_DEFAULT = 200

STREAM_BLOCK_MS = 1000

# Per-stream cap. Messages are ~200-500 KB each (one msgpack batch of
# ~hundreds of rows), so 500k MAXLEN would balloon past 100 GB. 10k is
# ~4 min of baseline or ~1 min under 10× burst — ample headroom for
# brief writer stalls while the writer normally keeps XPENDING near 0.
STREAM_MAXLEN = 10_000


async def ensure_consumer_group(
    redis: aioredis.Redis,
    stream: str,
    group: str = DB_WRITER_GROUP,
) -> None:
    """Idempotently create a consumer group (auto-creates stream, ignores BUSYGROUP)."""
    try:
        await redis.xgroup_create(
            name=stream,
            groupname=group,
            id="0",
            mkstream=True,
        )
    except aioredis.ResponseError as exc:
        if "BUSYGROUP" not in str(exc):
            raise


async def xadd_rows(
    redis: aioredis.Redis,
    stream: str,
    rows: list[dict],
) -> str | None:
    """Publish a batch of row dicts; returns the message ID or None if empty."""
    if not rows:
        return None
    payload = wire_encode({"rows": rows})
    msg_id: bytes = await redis.xadd(
        name=stream,
        fields={"d": payload},
        maxlen=STREAM_MAXLEN,
        approximate=True,
    )
    return msg_id.decode() if isinstance(msg_id, bytes) else msg_id
