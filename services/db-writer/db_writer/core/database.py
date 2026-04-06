"""Raw asyncpg pool for DB Writer (uses copy_records_to_table on the hot path).
Schema is owned by Analytics Service via Alembic; writer only creates its own
per-replica UNLOGGED staging tables at startup.
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
