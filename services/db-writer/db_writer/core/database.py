"""Database pool for DB Writer.

The writer service does one thing: INSERT. It talks to TimescaleDB via a
raw asyncpg connection pool (no SQLAlchemy ORM) because the hot path uses
``Connection.copy_records_to_table`` which is not exposed by SQLAlchemy.

Schema management (tables, hypertables, continuous aggregates,
retention/compression policies) is owned by Analytics Service and applied
via Alembic migrations. The writer only creates its own per-replica
UNLOGGED staging tables at startup (see main.py).
"""

from __future__ import annotations

import asyncpg

from db_writer.core.config import get_settings
from shared.observability import get_logger

logger = get_logger(__name__)

_pool: asyncpg.Pool | None = None


async def init_db_pool() -> None:
    """Initialize the asyncpg connection pool."""
    global _pool
    settings = get_settings()
    _pool = await asyncpg.create_pool(
        dsn=settings.database_url,
        min_size=settings.db_pool_min,
        max_size=settings.db_pool_max,
        command_timeout=60,
    )
    logger.info(
        "asyncpg pool initialized",
        min_size=settings.db_pool_min,
        max_size=settings.db_pool_max,
    )


async def close_db_pool() -> None:
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None
        logger.info("asyncpg pool closed")


def get_pool() -> asyncpg.Pool:
    if _pool is None:
        raise RuntimeError("DB pool not initialized — call init_db_pool() first")
    return _pool
