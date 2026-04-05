"""Telemetry repository — PostgreSQL bulk inserts only."""

from __future__ import annotations

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from processor.models.telemetry_entity import TelemetryRecord


async def bulk_insert(session: AsyncSession, rows: list[dict]) -> int:
    if not rows:
        return 0
    stmt = pg_insert(TelemetryRecord).values(rows).on_conflict_do_nothing()
    await session.execute(stmt)
    return len(rows)


def bulk_insert_stmt(rows: list[dict]):
    """Return an executable statement for use in batched writers."""
    return pg_insert(TelemetryRecord).values(rows).on_conflict_do_nothing()
