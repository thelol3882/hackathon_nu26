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

    # Auto-create tables on startup
    from api_gateway.models.alert_entity import AlertRecord  # noqa: F401
    from api_gateway.models.base import Base
    from api_gateway.models.health_config_entity import HealthThreshold  # noqa: F401
    from api_gateway.models.locomotive_entity import Locomotive  # noqa: F401
    from api_gateway.models.report_entity import Report  # noqa: F401
    from api_gateway.models.user_entity import User  # noqa: F401

    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


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
