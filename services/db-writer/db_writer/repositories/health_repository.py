"""Health snapshot repository — PostgreSQL bulk inserts only."""

from __future__ import annotations

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from db_writer.models.health_entity import HealthSnapshotRecord


async def bulk_insert(session: AsyncSession, records: list[dict]) -> int:
    if not records:
        return 0
    stmt = pg_insert(HealthSnapshotRecord).values(records).on_conflict_do_nothing()
    await session.execute(stmt)
    return len(records)


def bulk_insert_stmt(records: list[dict]):
    """Return an executable statement for use in batched writers."""
    return pg_insert(HealthSnapshotRecord).values(records).on_conflict_do_nothing()
