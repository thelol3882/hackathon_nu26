"""PostgreSQL async session management for CRUD operations."""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from api_gateway.core.config import get_settings

_app_engine = None
_app_session_factory: async_sessionmaker[AsyncSession] | None = None


async def init_app_db() -> None:
    """Initialize PostgreSQL connection pool for CRUD operations."""
    global _app_engine, _app_session_factory
    settings = get_settings()
    url = settings.app_database_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    _app_engine = create_async_engine(
        url,
        pool_size=settings.app_db_pool_max,
        pool_pre_ping=True,
    )
    _app_session_factory = async_sessionmaker(_app_engine, expire_on_commit=False)


async def close_app_db() -> None:
    """Shutdown PostgreSQL connection pool."""
    global _app_engine, _app_session_factory
    if _app_engine:
        await _app_engine.dispose()
        _app_engine = None
        _app_session_factory = None


def get_app_session_factory() -> async_sessionmaker[AsyncSession]:
    if _app_session_factory is None:
        msg = "App DB not initialized. Call init_app_db() first."
        raise RuntimeError(msg)
    return _app_session_factory


async def get_app_db_session() -> AsyncGenerator[AsyncSession]:
    """Dependency for PostgreSQL (CRUD) operations."""
    if _app_session_factory is None:
        msg = "App DB not initialized."
        raise RuntimeError(msg)
    async with _app_session_factory() as session:
        yield session
