"""Alert service — business logic, calls repository for DB access."""

from __future__ import annotations

from datetime import datetime

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from api_gateway.repositories import alert_repository
from shared.log_codes import ALERT_ACKNOWLEDGED
from shared.observability import get_logger
from shared.schemas.alert import AlertEvent

logger = get_logger(__name__)


def _row_to_event(r: dict) -> AlertEvent:
    return AlertEvent(
        id=r["id"],
        locomotive_id=r["locomotive_id"],
        sensor_type=r["sensor_type"],
        severity=r["severity"],
        value=float(r["value"]),
        threshold_min=float(r["threshold_min"]),
        threshold_max=float(r["threshold_max"]),
        message=r["message"],
        recommendation=r.get("recommendation", ""),
        timestamp=r["timestamp"],
        acknowledged=r["acknowledged"],
    )


async def list_alerts(
    session: AsyncSession,
    *,
    locomotive_id: str | None = None,
    severity: str | None = None,
    acknowledged: bool | None = None,
    start: datetime | None = None,
    end: datetime | None = None,
    offset: int = 0,
    limit: int = 50,
) -> list[AlertEvent]:
    rows = await alert_repository.find_many(
        session,
        locomotive_id=locomotive_id,
        severity=severity,
        acknowledged=acknowledged,
        start=start,
        end=end,
        offset=offset,
        limit=limit,
    )
    return [_row_to_event(r) for r in rows]


async def get_alert(session: AsyncSession, alert_id: str) -> AlertEvent:
    row = await alert_repository.find_by_id(session, alert_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Alert not found")
    return _row_to_event(row)


async def acknowledge_alert(session: AsyncSession, alert_id: str) -> AlertEvent:
    row = await alert_repository.acknowledge(session, alert_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Alert not found")
    logger.info("Alert acknowledged", code=ALERT_ACKNOWLEDGED, alert_id=alert_id)
    return _row_to_event(row)
