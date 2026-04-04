from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from api_gateway.core.config import get_settings

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
        raise RuntimeError("DB not initialized. Call init_db_pool() first.")
    return _session_factory


async def get_db_session() -> AsyncGenerator[AsyncSession]:
    if _session_factory is None:
        raise RuntimeError("DB not initialized. Call init_db_pool() first.")
    async with _session_factory() as session:
        yield session
