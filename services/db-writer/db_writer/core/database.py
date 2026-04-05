"""Database pool, schema creation, and TimescaleDB retention policies.

Moved from the processor service — the db-writer is now the sole owner
of TimescaleDB schema management.
"""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from db_writer.core.config import get_settings
from shared.observability import get_logger

logger = get_logger(__name__)

_engine = None
_session_factory: async_sessionmaker[AsyncSession] | None = None

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

    # Regular tables — use DELETE instead of retention policy
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


# Each tuple: (view_name, bucket_interval, refresh_start_offset,
#               refresh_end_offset, refresh_schedule_interval)
_CONTINUOUS_AGGREGATES = [
    ("telemetry_1min", "1 minute", "10 minutes", "30 seconds", "30 seconds"),
    ("telemetry_15min", "15 minutes", "1 hour", "1 minute", "5 minutes"),
    ("telemetry_1hour", "1 hour", "2 hours", "5 minutes", "15 minutes"),
]


async def _setup_continuous_aggregates(conn) -> None:
    """Create TimescaleDB Continuous Aggregates for historical query optimization.

    Three materialized views collapse raw_telemetry into progressively coarser
    resolutions (1 min, 15 min, 1 hour).  The API gateway auto-selects the
    optimal level based on the requested time range:

        < 15 min   -> raw_telemetry   (every second)
        15m - 2h   -> telemetry_1min  (one row per minute)
        2h - 24h   -> telemetry_15min (one row per 15 min)
        24h - 72h  -> telemetry_1hour (one row per hour)

    All views use WITH NO DATA on creation so the migration is instant.
    Refresh policies populate them going forward.
    """
    for view_name, bucket, start_off, end_off, schedule in _CONTINUOUS_AGGREGATES:
        try:
            # Check if the view already exists to avoid "already exists" errors.
            exists = await conn.execute(
                text("SELECT 1 FROM timescaledb_information.continuous_aggregates WHERE view_name = :vn"),
                {"vn": view_name},
            )
            if exists.fetchone() is not None:
                logger.debug("Continuous aggregate %s already exists, skipping", view_name)
                continue

            await conn.execute(
                text(f"""
                    CREATE MATERIALIZED VIEW {view_name}
                    WITH (timescaledb.continuous) AS
                    SELECT
                        time_bucket('{bucket}', time) AS bucket,
                        locomotive_id,
                        locomotive_type,
                        sensor_type,
                        avg(value) AS avg_value,
                        min(value) AS min_value,
                        max(value) AS max_value,
                        last(value, time) AS last_value,
                        last(filtered_value, time) AS last_filtered_value,
                        max(unit) AS unit,
                        last(latitude, time) AS latitude,
                        last(longitude, time) AS longitude
                    FROM raw_telemetry
                    GROUP BY bucket, locomotive_id, locomotive_type, sensor_type
                    WITH NO DATA
                """)
            )
            await conn.execute(
                text(f"""
                    SELECT add_continuous_aggregate_policy('{view_name}',
                        start_offset    => INTERVAL '{start_off}',
                        end_offset      => INTERVAL '{end_off}',
                        schedule_interval => INTERVAL '{schedule}',
                        if_not_exists   => TRUE
                    )
                """)
            )
            logger.info("Continuous aggregate created: %s (bucket=%s)", view_name, bucket)
        except Exception as e:
            logger.warning("Could not create continuous aggregate %s: %s", view_name, e)


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

    import db_writer.models  # noqa: F401 — ensure all models are registered
    from db_writer.models.base import Base

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
        await _setup_continuous_aggregates(conn)

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
