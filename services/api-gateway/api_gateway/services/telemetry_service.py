"""Telemetry service — business logic, calls repository for DB access."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from api_gateway.repositories import telemetry_repository


class TelemetryBucket(BaseModel):
    bucket: datetime
    locomotive_id: str
    sensor_type: str
    avg_value: float | None = None
    min_value: float | None = None
    max_value: float | None = None
    last_value: float | None = None
    unit: str


class TelemetryRaw(BaseModel):
    time: datetime
    locomotive_id: str
    locomotive_type: str = ""
    sensor_type: str
    value: float
    filtered_value: float | None = None
    unit: str
    latitude: float | None = None
    longitude: float | None = None


class TelemetrySnapshot(BaseModel):
    locomotive_id: str
    locomotive_type: str = ""
    sensor_type: str
    value: float
    filtered_value: float | None = None
    unit: str
    timestamp: datetime
    latitude: float | None = None
    longitude: float | None = None


async def query_telemetry_bucketed(
    session: AsyncSession,
    *,
    locomotive_id: str | None = None,
    sensor_type: str | None = None,
    start: datetime | None = None,
    end: datetime | None = None,
    offset: int = 0,
    limit: int = 500,
) -> tuple[list[TelemetryBucket], str]:
    """Query historical telemetry with automatic resolution selection.

    Returns (buckets, data_source_label) so the router can set X-Data-Source.
    """
    rows, data_source = await telemetry_repository.query_bucketed(
        session,
        locomotive_id=locomotive_id,
        sensor_type=sensor_type,
        start=start,
        end=end,
        offset=offset,
        limit=limit,
    )
    return [TelemetryBucket(**r) for r in rows], data_source


async def query_telemetry_snapshot(
    session: AsyncSession,
    *,
    locomotive_id: str,
    at: datetime,
) -> list[TelemetrySnapshot]:
    rows = await telemetry_repository.query_snapshot(session, locomotive_id=locomotive_id, at=at)
    return [TelemetrySnapshot(**r) for r in rows]


async def query_telemetry_raw(
    session: AsyncSession,
    *,
    locomotive_id: str | None = None,
    sensor_type: str | None = None,
    start: datetime | None = None,
    end: datetime | None = None,
    offset: int = 0,
    limit: int = 200,
) -> list[TelemetryRaw]:
    rows = await telemetry_repository.query_raw(
        session,
        locomotive_id=locomotive_id,
        sensor_type=sensor_type,
        start=start,
        end=end,
        offset=offset,
        limit=limit,
    )
    return [TelemetryRaw(**r) for r in rows]
