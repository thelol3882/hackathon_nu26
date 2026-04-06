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
STREAM_BATCH_SIZE = 500  # legacy constant, kept for compatibility

# Reader batch sizes — how many messages the db-writer XREADGROUP pulls per
# iteration. Smaller values bound the per-iteration row count so the writer
# can flush and ACK before the next read, which breaks the death-spiral
# feedback loop on the hot telemetry stream. Alerts/health are low volume
# and can use a larger read batch safely.
READER_BATCH_SIZE_TELEMETRY = 50
READER_BATCH_SIZE_DEFAULT = 200

STREAM_BLOCK_MS = 1000  # block timeout in milliseconds

# Approximate per-stream cap.
#
# Each XADD payload is one msgpack-encoded batch that typically holds
# several hundred rows, so messages are ~200-500 KB each. At 500k MAXLEN
# Redis would balloon past 100 GB — don't go there.
#
# The db-writer consumes in real time (XPENDING ~0 under 10× burst), so
# this buffer is pure safety margin for brief writer stalls. 10k messages
# ≈ 4 minutes of baseline traffic or ~1 minute under 10× burst, which is
# more than enough headroom given the writer's processing rate.
STREAM_MAXLEN = 10_000


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
