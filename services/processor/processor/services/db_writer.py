"""Background DB writer — decouples database persistence from the hot path.

Telemetry rows, alert records, and health snapshots are enqueued via `put()`
and flushed to the database in batches by a background asyncio task.
"""

from __future__ import annotations

import asyncio
import contextlib
from dataclasses import dataclass, field

from processor.core.database import get_session_factory
from processor.repositories import alert_repository, health_repository, telemetry_repository
from shared.observability import get_logger

logger = get_logger(__name__)

_FLUSH_INTERVAL = 0.5  # seconds — max time before a partial batch is written
_MAX_BATCH_ROWS = 5000  # flush if telemetry rows exceed this
# asyncpg limits query arguments to 32767.  TelemetryRecord has 10 columns,
# so max rows per INSERT = 32767 // 10 ≈ 3276.  Use 3000 for safety.
_INSERT_CHUNK = 3000


@dataclass
class _WorkItem:
    telemetry_rows: list[dict] = field(default_factory=list)
    alert_records: list = field(default_factory=list)
    health_records: list = field(default_factory=list)


class DbWriter:
    """Async background writer that batches DB inserts."""

    def __init__(self) -> None:
        self._queue: asyncio.Queue[_WorkItem] = asyncio.Queue()
        self._task: asyncio.Task | None = None

    async def start(self) -> None:
        self._task = asyncio.create_task(self._drain_loop(), name="db-writer")

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
            self._task = None
        await self._flush_all()

    def put(
        self,
        telemetry_rows: list[dict],
        alert_records: list,
        health_records: list,
    ) -> None:
        item = _WorkItem(
            telemetry_rows=telemetry_rows,
            alert_records=alert_records,
            health_records=health_records,
        )
        self._queue.put_nowait(item)

    async def _drain_loop(self) -> None:
        while True:
            try:
                item = await self._queue.get()
                all_rows: list[dict] = list(item.telemetry_rows)
                all_alerts: list = list(item.alert_records)
                all_health: list = list(item.health_records)

                deadline = asyncio.get_event_loop().time() + _FLUSH_INTERVAL
                while True:
                    remaining = deadline - asyncio.get_event_loop().time()
                    if remaining <= 0 or len(all_rows) >= _MAX_BATCH_ROWS:
                        break
                    try:
                        item = await asyncio.wait_for(self._queue.get(), timeout=remaining)
                        all_rows.extend(item.telemetry_rows)
                        all_alerts.extend(item.alert_records)
                        all_health.extend(item.health_records)
                    except TimeoutError:
                        break

                await self._flush(all_rows, all_alerts, all_health)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("DbWriter flush error")

    async def _flush_all(self) -> None:
        all_rows: list[dict] = []
        all_alerts: list = []
        all_health: list = []
        while not self._queue.empty():
            try:
                item = self._queue.get_nowait()
                all_rows.extend(item.telemetry_rows)
                all_alerts.extend(item.alert_records)
                all_health.extend(item.health_records)
            except asyncio.QueueEmpty:
                break
        if all_rows or all_alerts or all_health:
            await self._flush(all_rows, all_alerts, all_health)

    async def _flush(
        self,
        telemetry_rows: list[dict],
        alert_records: list,
        health_records: list,
    ) -> None:
        factory = get_session_factory()
        if factory is None:
            logger.error("DbWriter: session factory not available")
            return

        async with factory() as session:
            try:
                for i in range(0, len(telemetry_rows), _INSERT_CHUNK):
                    chunk = telemetry_rows[i : i + _INSERT_CHUNK]
                    stmt = telemetry_repository.bulk_insert_stmt(chunk)
                    await session.execute(stmt)
                for i in range(0, len(alert_records), _INSERT_CHUNK):
                    chunk = alert_records[i : i + _INSERT_CHUNK]
                    stmt = alert_repository.bulk_insert_stmt(chunk)
                    await session.execute(stmt)
                for i in range(0, len(health_records), _INSERT_CHUNK):
                    chunk = health_records[i : i + _INSERT_CHUNK]
                    stmt = health_repository.bulk_insert_stmt(chunk)
                    await session.execute(stmt)
                await session.commit()
                logger.info(
                    "DbWriter flushed",
                    telemetry_rows=len(telemetry_rows),
                    alerts=len(alert_records),
                    health=len(health_records),
                )
            except Exception:
                await session.rollback()
                logger.exception(
                    "DbWriter commit failed",
                    telemetry_rows=len(telemetry_rows),
                    alerts=len(alert_records),
                    health=len(health_records),
                )
