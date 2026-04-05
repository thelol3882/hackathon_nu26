"""PostgreSQL connection pool for CRUD operations.

API Gateway connects ONLY to PostgreSQL (auth, fleet registry, reports,
health config). All telemetry queries go through Analytics Service via gRPC.
"""

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

    from api_gateway.models.base import AppBase
    from api_gateway.models.health_config_entity import HealthThreshold  # noqa: F401
    from api_gateway.models.locomotive_entity import Locomotive  # noqa: F401
    from api_gateway.models.report_entity import Report  # noqa: F401
    from api_gateway.models.user_entity import User  # noqa: F401

    async with _app_engine.begin() as conn:
        await conn.run_sync(AppBase.metadata.create_all)


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
