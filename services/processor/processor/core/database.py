import logging
from collections.abc import AsyncGenerator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from processor.core.config import get_settings

logger = logging.getLogger(__name__)

_engine = None
_session_factory: async_sessionmaker[AsyncSession] | None = None

# Only raw_telemetry has a time-based composite PK suitable for hypertables.
# health_snapshots and alert_events use UUID PKs with indexed timestamp columns.
_HYPERTABLES = [
    ("raw_telemetry", "time"),
]


async def _setup_retention_policies(conn, settings) -> None:
    """Configure TimescaleDB compression and retention policies."""
    try:
        await conn.execute(
            text(
                "ALTER TABLE raw_telemetry SET ("
                "  timescaledb.compress,"
                "  timescaledb.compress_segmentby = 'locomotive_id, sensor_type',"
                "  timescaledb.compress_orderby = 'time DESC'"
                ")"
            )
        )
        await conn.execute(
            text(
                f"SELECT add_compression_policy('raw_telemetry', "
                f"INTERVAL '{settings.compression_after_hours} hours', if_not_exists => TRUE)"
            )
        )
        logger.info("Compression policy set: compress after %dh", settings.compression_after_hours)
    except Exception as e:
        logger.warning("Could not set compression policy: %s", e)

    try:
        await conn.execute(
            text(
                f"SELECT add_retention_policy('raw_telemetry', "
                f"INTERVAL '{settings.retention_telemetry_hours} hours', if_not_exists => TRUE)"
            )
        )
        logger.info("Retention policy set: drop telemetry after %dh", settings.retention_telemetry_hours)
    except Exception as e:
        logger.warning("Could not set retention policy: %s", e)

    # Regular tables (not hypertables) — use DELETE instead of retention policy
    try:
        await conn.execute(
            text("DELETE FROM alert_events WHERE timestamp < NOW() - make_interval(hours => :h)"),
            {"h": settings.retention_alerts_hours},
        )
        await conn.execute(
            text("DELETE FROM health_snapshots WHERE calculated_at < NOW() - make_interval(hours => :h)"),
            {"h": settings.retention_health_hours},
        )
        logger.info(
            "Cleaned old alerts (>%dh) and health snapshots (>%dh)",
            settings.retention_alerts_hours,
            settings.retention_health_hours,
        )
    except Exception as e:
        logger.warning("Could not clean old records: %s", e)


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

    import processor.models  # noqa: F401 — ensure all models are registered
    from processor.models.base import Base

    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        for table, col in _HYPERTABLES:
            await conn.execute(
                text(
                    f"SELECT create_hypertable('{table}', '{col}', "
                    f"chunk_time_interval => INTERVAL '1 hour', "
                    f"if_not_exists => TRUE, migrate_data => TRUE)"
                )
            )
        await _setup_retention_policies(conn, settings)


async def close_db_pool() -> None:
    global _engine, _session_factory
    if _engine:
        await _engine.dispose()
        _engine = None
        _session_factory = None


def get_session_factory() -> async_sessionmaker[AsyncSession] | None:
    return _session_factory


async def get_db_session() -> AsyncGenerator[AsyncSession]:
    if _session_factory is None:
        raise RuntimeError("DB not initialized. Call init_db_pool() first.")
    async with _session_factory() as session:
        yield session
