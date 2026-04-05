"""
Dual database connections: PostgreSQL (CRUD) + TimescaleDB (telemetry).

PostgreSQL handles auth, fleet registry, reports, and health config.
These are small tables (dozens to thousands of rows) with standard CRUD
and JOINs between business entities.

TimescaleDB handles time-series data: raw telemetry, alerts, health
snapshots, and continuous aggregates. Millions of rows with time-range
queries. API Gateway only reads from TimescaleDB — DB Writer owns writes.

Separating them means a heavy telemetry aggregation doesn't block a
simple user login, and vice versa.
"""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from api_gateway.core.config import get_settings

# --- Application DB (PostgreSQL) ---
_app_engine = None
_app_session_factory: async_sessionmaker[AsyncSession] | None = None

# --- Telemetry DB (TimescaleDB) ---
_ts_engine = None
_ts_session_factory: async_sessionmaker[AsyncSession] | None = None


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

    # Auto-create CRUD tables in PostgreSQL
    from api_gateway.models.base import AppBase
    from api_gateway.models.health_config_entity import HealthThreshold  # noqa: F401
    from api_gateway.models.locomotive_entity import Locomotive  # noqa: F401
    from api_gateway.models.report_entity import Report  # noqa: F401
    from api_gateway.models.user_entity import User  # noqa: F401

    async with _app_engine.begin() as conn:
        await conn.run_sync(AppBase.metadata.create_all)


async def init_ts_db() -> None:
    """Initialize TimescaleDB connection pool for telemetry queries.

    API Gateway only reads from TimescaleDB (historical queries).
    DB Writer handles all writes and owns the schema.
    """
    global _ts_engine, _ts_session_factory
    settings = get_settings()
    url = settings.ts_database_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    _ts_engine = create_async_engine(
        url,
        pool_size=settings.ts_db_pool_max,
        pool_pre_ping=True,
    )
    _ts_session_factory = async_sessionmaker(_ts_engine, expire_on_commit=False)


async def close_all_db() -> None:
    """Shutdown both connection pools."""
    global _app_engine, _app_session_factory, _ts_engine, _ts_session_factory
    if _app_engine:
        await _app_engine.dispose()
        _app_engine = None
        _app_session_factory = None
    if _ts_engine:
        await _ts_engine.dispose()
        _ts_engine = None
        _ts_session_factory = None


def get_app_session_factory() -> async_sessionmaker[AsyncSession]:
    if _app_session_factory is None:
        raise RuntimeError("App DB not initialized. Call init_app_db() first.")
    return _app_session_factory


def get_ts_session_factory() -> async_sessionmaker[AsyncSession]:
    if _ts_session_factory is None:
        raise RuntimeError("Telemetry DB not initialized. Call init_ts_db() first.")
    return _ts_session_factory


async def get_app_db_session() -> AsyncGenerator[AsyncSession]:
    """Dependency for PostgreSQL (CRUD) operations."""
    if _app_session_factory is None:
        raise RuntimeError("App DB not initialized.")
    async with _app_session_factory() as session:
        yield session


async def get_ts_db_session() -> AsyncGenerator[AsyncSession]:
    """Dependency for TimescaleDB (telemetry) queries."""
    if _ts_session_factory is None:
        raise RuntimeError("Telemetry DB not initialized.")
    async with _ts_session_factory() as session:
        yield session
