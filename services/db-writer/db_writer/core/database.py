"""Database pool for DB Writer.

This service is a write-only pipe — it receives dicts from Redis Streams
and does INSERT.  Schema management (tables, hypertables, continuous
aggregates, retention/compression policies) is owned by Analytics Service
and applied via Alembic migrations.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from db_writer.core.config import get_settings
from shared.observability import get_logger

logger = get_logger(__name__)

_engine = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


async def init_db_pool() -> None:
    global _engine, _session_factory
    settings = get_settings()
    url = settings.database_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    _engine = create_async_engine(
        url,
        pool_size=settings.db_pool_max,
        pool_pre_ping=True,
    )
    _session_factory = async_sessionmaker(_engine, expire_on_commit=False)
    logger.info("DB pool initialized", pool_size=settings.db_pool_max)


async def close_db_pool() -> None:
    global _engine, _session_factory
    if _engine:
        await _engine.dispose()
        _engine = None
        _session_factory = None
        logger.info("DB pool closed")


def get_session_factory() -> async_sessionmaker[AsyncSession] | None:
    return _session_factory
