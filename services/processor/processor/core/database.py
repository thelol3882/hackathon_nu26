from collections.abc import AsyncGenerator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from processor.core.config import get_settings

_engine = None
_session_factory: async_sessionmaker[AsyncSession] | None = None

# Hypertables to create after DDL (table_name, time_column)
# Only raw_telemetry has a time-based composite PK suitable for hypertables.
# health_snapshots and alert_events use UUID PKs with indexed timestamp columns.
_HYPERTABLES = [
    ("raw_telemetry", "time"),
]


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

    # Auto-create tables and hypertables on startup
    import processor.models  # noqa: F401 — ensure all models are registered
    from processor.models.base import Base

    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        for table, col in _HYPERTABLES:
            await conn.execute(
                text(f"SELECT create_hypertable('{table}', '{col}', if_not_exists => TRUE, migrate_data => TRUE)")
            )


async def close_db_pool() -> None:
    global _engine, _session_factory
    if _engine:
        await _engine.dispose()
        _engine = None
        _session_factory = None


async def get_db_session() -> AsyncGenerator[AsyncSession]:
    if _session_factory is None:
        raise RuntimeError("DB not initialized. Call init_db_pool() first.")
    async with _session_factory() as session:
        yield session
