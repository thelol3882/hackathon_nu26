"""TimescaleDB connection pool — READ ONLY.

Analytics Service is the single reader of TimescaleDB. DB Writer handles
all writes. No create_all needed here — DB Writer owns the schema.
"""

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from analytics.core.config import get_settings

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


async def close_db_pool() -> None:
    global _engine, _session_factory
    if _engine:
        await _engine.dispose()
        _engine = None
        _session_factory = None


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    if _session_factory is None:
        msg = "DB not initialized. Call init_db_pool() first."
        raise RuntimeError(msg)
    return _session_factory
