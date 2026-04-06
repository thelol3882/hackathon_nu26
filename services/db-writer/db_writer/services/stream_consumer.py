"""Reader + worker-pool pipeline that bulk-loads a Redis Stream into TimescaleDB.

One reader drains XREADGROUP and pushes decoded batches onto a bounded queue;
N workers each own one asyncpg connection and COPY into a per-worker UNLOGGED
staging table before INSERT ... SELECT ON CONFLICT DO NOTHING into the target.

Reliability:
  - XACK happens only after the write transaction commits; crashes leave
    messages in the PEL and are recovered via XREADGROUP id='0' on restart.
  - Each transaction TRUNCATEs its staging table first to drop leftovers.
  - ON CONFLICT DO NOTHING absorbs at-least-once redelivery.

Staging tables exist because copy_records_to_table has no ON CONFLICT; they're
per (replica, stream, worker) so workers don't serialize on the TRUNCATE lock.
"""

from __future__ import annotations

import asyncio
import json
import uuid
from collections.abc import Callable
from datetime import datetime
from typing import Any

import asyncpg
import redis.asyncio as aioredis
from sqlalchemy import DateTime
from sqlalchemy.dialects.postgresql import JSONB, UUID

from shared.observability import get_logger
from shared.observability.prometheus import (
    stream_consumer_lag,
    stream_messages_consumed,
    stream_rows_written,
    stream_write_errors,
)
from shared.streams import DB_WRITER_GROUP, STREAM_BLOCK_MS, ensure_consumer_group
from shared.wire import decode as wire_decode

logger = get_logger(__name__)


# Per-model cache: (column_names, dict->tuple converter). Tuples are required
# by asyncpg.copy_records_to_table; JSONB must be pre-serialized to a string
# because asyncpg's default JSONB codec is text.
_ADAPTER_CACHE: dict[type, tuple[tuple[str, ...], Callable[[dict], tuple]]] = {}


def _build_adapter(model_class) -> tuple[tuple[str, ...], Callable[[dict], tuple]]:
    """Inspect ORM model once, return (columns, row_to_tuple)."""
    columns: list[str] = []
    converters: list[Callable[[Any], Any]] = []

    def _passthrough(v):
        return v

    def _to_datetime(v):
        if v is None or isinstance(v, datetime):
            return v
        return datetime.fromisoformat(v)

    def _to_uuid(v):
        if v is None or isinstance(v, uuid.UUID):
            return v
        return uuid.UUID(v)

    def _to_jsonb(v):
        if v is None:
            return None
        if isinstance(v, str):
            return v
        return json.dumps(v, default=str)

    for col in model_class.__table__.columns:
        columns.append(col.key)
        col_type = col.type
        if isinstance(col_type, DateTime):
            converters.append(_to_datetime)
        elif isinstance(col_type, UUID):
            converters.append(_to_uuid)
        elif isinstance(col_type, JSONB):
            converters.append(_to_jsonb)
        else:
            converters.append(_passthrough)

    cols = tuple(columns)
    convs = tuple(converters)

    def row_to_tuple(row: dict) -> tuple:
        return tuple(conv(row.get(name)) for name, conv in zip(cols, convs, strict=True))

    return cols, row_to_tuple


def _get_adapter(model_class) -> tuple[tuple[str, ...], Callable[[dict], tuple]]:
    cached = _ADAPTER_CACHE.get(model_class)
    if cached is None:
        cached = _build_adapter(model_class)
        _ADAPTER_CACHE[model_class] = cached
    return cached


class StreamConsumer:
    """Consumes one Redis Stream and bulk-writes to TimescaleDB via COPY+staging."""

    def __init__(
        self,
        redis_client: aioredis.Redis,
        pg_pool: asyncpg.Pool,
        stream: str,
        consumer_name: str,
        model_class,
        *,
        staging_tables: list[str],
        reader_batch_size: int,
        rows_per_flush: int,
        queue_maxsize: int,
    ) -> None:
        self._redis = redis_client
        self._pool = pg_pool
        self._stream = stream
        self._consumer_name = consumer_name
        self._model_class = model_class
        self._target_table = model_class.__tablename__
        self._staging_tables = list(staging_tables)
        self._reader_batch_size = reader_batch_size
        self._rows_per_flush = rows_per_flush
        self._queue: asyncio.Queue[tuple[list[bytes], list[dict]] | None] = asyncio.Queue(
            maxsize=queue_maxsize,
        )
        self._columns, self._row_to_tuple = _get_adapter(model_class)
        self._running = True
        self._worker_count = len(self._staging_tables)

    async def start(self) -> None:
        """Run the reader and N worker coroutines concurrently."""
        await ensure_consumer_group(self._redis, self._stream, DB_WRITER_GROUP)

        workers = [
            asyncio.create_task(
                self._worker_loop(staging_table),
                name=f"writer-{self._stream}-{i}",
            )
            for i, staging_table in enumerate(self._staging_tables)
        ]
        reader = asyncio.create_task(
            self._reader_loop(),
            name=f"reader-{self._stream}",
        )

        try:
            await reader
        except asyncio.CancelledError:
            pass
        finally:
            for _ in workers:
                await self._queue.put(None)
            await asyncio.gather(*workers, return_exceptions=True)

    def stop(self) -> None:
        self._running = False

    async def _reader_loop(self) -> None:
        """Drain pending-on-restart, then pump new messages into the queue."""
        await self._drain_pending()

        while self._running:
            try:
                messages = await self._redis.xreadgroup(
                    groupname=DB_WRITER_GROUP,
                    consumername=self._consumer_name,
                    streams={self._stream: ">"},
                    count=self._reader_batch_size,
                    block=STREAM_BLOCK_MS,
                )
                if not messages:
                    continue
                _, entries = messages[0]
                await self._enqueue_entries(entries)
            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("Reader error", stream=self._stream)
                stream_write_errors.labels(stream=self._stream).inc()
                await asyncio.sleep(1.0)

    async def _drain_pending(self) -> None:
        """Re-process messages still in the PEL for this consumer."""
        while True:
            messages = await self._redis.xreadgroup(
                groupname=DB_WRITER_GROUP,
                consumername=self._consumer_name,
                streams={self._stream: "0"},
                count=self._reader_batch_size,
            )
            if not messages or not messages[0][1]:
                return
            _, entries = messages[0]
            await self._enqueue_entries(entries)

    async def _enqueue_entries(self, entries: list) -> None:
        """Decode and enqueue a batch; malformed messages are ACKed to avoid poison pills."""
        all_rows: list[dict] = []
        message_ids: list[bytes] = []
        poison_ids: list[bytes] = []

        for msg_id, fields in entries:
            try:
                raw = fields.get(b"d") or fields.get("d")
                if raw is None:
                    poison_ids.append(msg_id)
                    continue
                payload = wire_decode(raw)
                rows = payload.get("rows") or []
                all_rows.extend(rows)
                message_ids.append(msg_id)
            except Exception:
                logger.exception(
                    "Failed to decode stream message",
                    stream=self._stream,
                    msg_id=msg_id,
                )
                poison_ids.append(msg_id)

        if poison_ids:
            await self._redis.xack(self._stream, DB_WRITER_GROUP, *poison_ids)
            stream_messages_consumed.labels(stream=self._stream).inc(len(poison_ids))

        if not message_ids:
            return

        # A full queue backpressures the reader so pending grows in Redis, not RAM.
        await self._queue.put((message_ids, all_rows))

    async def _worker_loop(self, staging_table: str) -> None:
        """Dequeue batches and write them through a COPY staging pipeline."""
        while True:
            batch = await self._queue.get()
            if batch is None:
                self._queue.task_done()
                return
            message_ids, rows = batch
            try:
                if rows:
                    await self._write_batch(staging_table, rows)
                await self._redis.xack(self._stream, DB_WRITER_GROUP, *message_ids)
                stream_messages_consumed.labels(stream=self._stream).inc(len(message_ids))
            except Exception:
                stream_write_errors.labels(stream=self._stream).inc()
                logger.exception(
                    "Worker write failed — messages left in PEL for retry",
                    stream=self._stream,
                    staging=staging_table,
                    rows=len(rows),
                )
                # Skip XACK: rows stay in PEL and will be replayed by _drain_pending.
            finally:
                self._queue.task_done()

    async def _write_batch(self, staging_table: str, rows: list[dict]) -> None:
        """Write rows in rows_per_flush chunks; all chunks must commit before ACK."""
        records = [self._row_to_tuple(r) for r in rows]

        total = len(records)
        chunk_size = self._rows_per_flush

        async with self._pool.acquire() as conn:
            for start in range(0, total, chunk_size):
                chunk = records[start : start + chunk_size]
                async with conn.transaction():
                    await conn.execute(f'TRUNCATE TABLE "{staging_table}"')
                    await conn.copy_records_to_table(
                        staging_table,
                        records=chunk,
                        columns=self._columns,
                    )
                    # Target/staging/column names come from ORM metadata,
                    # not request input, so interpolation is safe here.
                    col_list = ", ".join(f'"{c}"' for c in self._columns)
                    insert_sql = f'INSERT INTO "{self._target_table}" ({col_list}) SELECT {col_list} FROM "{staging_table}" ON CONFLICT DO NOTHING'  # noqa: S608, E501
                    await conn.execute(insert_sql)

        stream_rows_written.labels(table=self._target_table).inc(total)
        logger.info(
            "Batch written",
            stream=self._stream,
            staging=staging_table,
            rows=total,
        )

    async def update_lag(self) -> None:
        """Query stream pending count and update the Prometheus gauge."""
        try:
            info = await self._redis.xpending(self._stream, DB_WRITER_GROUP)
            if isinstance(info, dict):
                pending_count = info.get("pending", 0)
            elif info:
                pending_count = info[0]
            else:
                pending_count = 0
            stream_consumer_lag.labels(stream=self._stream).set(pending_count)
        except Exception:
            # Best-effort metric.
            pass
