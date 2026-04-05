"""
DB Writer stream consumer — reads from Redis Streams and bulk-inserts into TimescaleDB.

RELIABILITY GUARANTEES:
  1. Messages are acknowledged (XACK) only AFTER successful DB commit.
     If the writer crashes mid-batch, unacked messages will be re-delivered
     on restart via XREADGROUP with id='0' (pending messages check).

  2. All inserts use ON CONFLICT DO NOTHING, so re-processing the same
     message is safe (idempotent). This handles the "at-least-once"
     delivery semantic of Redis Streams.

  3. Messages are batched for efficiency: up to STREAM_BATCH_SIZE messages
     are read at once, then inserted in a single DB transaction.

CONSUMER GROUPS:
  All db-writer replicas join the same consumer group "db-writers".
  Redis automatically distributes messages across consumers in the group.
  Each message goes to exactly one consumer — no duplicates between replicas.

  To scale writes: run multiple db-writer containers with different
  CONSUMER_NAME values (writer-1, writer-2, etc.).

FLOW PER ITERATION:
  1. XREADGROUP — block up to 1 second waiting for new messages
  2. Decode msgpack payloads
  3. Accumulate rows across all messages in the batch
  4. Bulk INSERT into TimescaleDB (chunked to stay under asyncpg param limit)
  5. XACK — confirm all processed messages
  6. Repeat
"""

from __future__ import annotations

import asyncio

import redis.asyncio as aioredis
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from shared.observability import get_logger
from shared.observability.prometheus import (
    stream_consumer_lag,
    stream_messages_consumed,
    stream_rows_written,
    stream_write_errors,
)
from shared.streams import DB_WRITER_GROUP, STREAM_BATCH_SIZE, STREAM_BLOCK_MS, ensure_consumer_group
from shared.wire import decode as wire_decode

logger = get_logger(__name__)

# asyncpg limits query arguments to 32767.  TelemetryRecord has 10 columns,
# so max rows per INSERT = 32767 // 10 ≈ 3276.  Use 3000 for safety.
_INSERT_CHUNK = 3000


class StreamConsumer:
    """Consumes messages from one Redis Stream and writes to TimescaleDB.

    Each instance handles one stream (telemetry, alerts, or health).
    Multiple instances run concurrently as asyncio tasks.
    """

    def __init__(
        self,
        redis_client: aioredis.Redis,
        session_factory: async_sessionmaker[AsyncSession],
        stream: str,
        consumer_name: str,
        model_class,
        batch_size: int = STREAM_BATCH_SIZE,
    ) -> None:
        self._redis = redis_client
        self._session_factory = session_factory
        self._stream = stream
        self._consumer_name = consumer_name
        self._model_class = model_class
        self._batch_size = batch_size
        self._running = True

    async def start(self) -> None:
        """Main consumer loop.  Runs until stop() is called.

        On first start, processes any pending messages (unacked from previous
        run) before reading new ones.  This ensures crash recovery.
        """
        await ensure_consumer_group(self._redis, self._stream, DB_WRITER_GROUP)

        # First: recover any pending messages from a previous crash.
        # id='0' means "give me all messages that were delivered to me
        # but not yet acknowledged".
        await self._process_pending()

        # Then: read new messages (id='>' means "only new, undelivered")
        while self._running:
            try:
                messages = await self._redis.xreadgroup(
                    groupname=DB_WRITER_GROUP,
                    consumername=self._consumer_name,
                    streams={self._stream: ">"},
                    count=self._batch_size,
                    block=STREAM_BLOCK_MS,
                )

                if not messages:
                    continue  # timeout, no new messages, loop again

                # messages = [(stream_name, [(msg_id, {field: value}), ...])]
                _stream_name, entries = messages[0]
                await self._process_entries(entries)

            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("Stream consumer error", stream=self._stream)
                stream_write_errors.labels(stream=self._stream).inc()
                await asyncio.sleep(1.0)

    async def _process_pending(self) -> None:
        """Re-process messages that were delivered but not acknowledged.

        This handles the case where the writer crashed after reading
        but before committing to DB.
        """
        while True:
            messages = await self._redis.xreadgroup(
                groupname=DB_WRITER_GROUP,
                consumername=self._consumer_name,
                streams={self._stream: "0"},  # '0' = pending messages only
                count=self._batch_size,
            )
            if not messages or not messages[0][1]:
                break
            _stream_name, entries = messages[0]
            await self._process_entries(entries)

    async def _process_entries(self, entries: list) -> None:
        """Decode messages, bulk-insert into DB, then acknowledge.

        All-or-nothing: if DB insert fails, messages are NOT acknowledged
        and will be retried on next iteration or after restart.
        """
        all_rows: list[dict] = []
        message_ids: list[bytes] = []

        for msg_id, fields in entries:
            try:
                raw = fields.get(b"d") or fields.get("d")
                if raw is None:
                    message_ids.append(msg_id)  # ack malformed message
                    continue

                payload = wire_decode(raw)
                rows = payload.get("rows", [])
                all_rows.extend(rows)
                message_ids.append(msg_id)
            except Exception:
                logger.exception(
                    "Failed to decode stream message",
                    stream=self._stream,
                    msg_id=msg_id,
                )
                message_ids.append(msg_id)  # ack to prevent infinite retry

        if all_rows:
            await self._bulk_insert(all_rows)

        # Acknowledge ALL messages in one call (efficient)
        if message_ids:
            await self._redis.xack(self._stream, DB_WRITER_GROUP, *message_ids)
            stream_messages_consumed.labels(stream=self._stream).inc(len(message_ids))

    async def _bulk_insert(self, rows: list[dict]) -> None:
        """Insert rows into TimescaleDB in chunks.

        asyncpg limits query parameters to 32767.  With 10 columns per
        telemetry row, max rows per INSERT = 32767 // 10 ~ 3276.
        Using 3000 for safety margin.

        ON CONFLICT DO NOTHING makes this idempotent — safe to retry
        the same batch without duplicate data.
        """
        async with self._session_factory() as session:
            try:
                for i in range(0, len(rows), _INSERT_CHUNK):
                    chunk = rows[i : i + _INSERT_CHUNK]
                    stmt = pg_insert(self._model_class).values(chunk).on_conflict_do_nothing()
                    await session.execute(stmt)
                await session.commit()
                stream_rows_written.labels(table=self._model_class.__tablename__).inc(len(rows))
                logger.info("Batch written", stream=self._stream, rows=len(rows))
            except Exception:
                await session.rollback()
                stream_write_errors.labels(stream=self._stream).inc()
                logger.exception("Batch write failed", stream=self._stream, rows=len(rows))
                raise  # don't ack — messages will be retried

    async def update_lag(self) -> None:
        """Query stream pending count and update the Prometheus gauge."""
        try:
            info = await self._redis.xpending(self._stream, DB_WRITER_GROUP)
            pending_count = info.get("pending", 0) if isinstance(info, dict) else (info[0] if info else 0)
            stream_consumer_lag.labels(stream=self._stream).set(pending_count)
        except Exception:
            pass  # best-effort metric

    def stop(self) -> None:
        self._running = False
