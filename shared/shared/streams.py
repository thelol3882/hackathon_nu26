"""Redis Streams constants and helpers for durable message passing.

Streams carry batched rows (msgpack-encoded) from the processor to the
db-writer service.  Each message contains a single field ``"d"`` whose
value is ``wire.encode({"rows": [<list of row dicts>]})``.

Consumer groups guarantee at-least-once delivery: the db-writer
acknowledges messages only after a successful DB commit.
"""

from __future__ import annotations

import redis.asyncio as aioredis

from shared.wire import encode as wire_encode

# ── Stream names ──────────────────────────────────────────────────────
TELEMETRY_STREAM = "stream:telemetry"
ALERTS_STREAM = "stream:alerts"
HEALTH_STREAM = "stream:health"

# ── Consumer group shared by all db-writer replicas ───────────────────
DB_WRITER_GROUP = "db-writers"

# ── Tuning knobs ──────────────────────────────────────────────────────
STREAM_BATCH_SIZE = 500   # max messages per XREADGROUP call
STREAM_BLOCK_MS = 1000    # block timeout in milliseconds
STREAM_MAXLEN = 100_000   # approximate cap per stream (~ safety valve)


async def ensure_consumer_group(
    redis: aioredis.Redis,
    stream: str,
    group: str = DB_WRITER_GROUP,
) -> None:
    """Create a consumer group idempotently.

    Uses ``MKSTREAM`` so the stream is auto-created if it does not
    exist yet.  Silently ignores ``BUSYGROUP`` (group already exists).
    """
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
    """Publish a batch of row dicts to a Redis Stream.

    Returns the auto-generated message ID, or *None* when *rows* is
    empty (nothing to publish).
    """
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
