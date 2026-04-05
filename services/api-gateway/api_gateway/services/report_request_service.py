"""Report job creation and status queries."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api_gateway.core.rabbitmq import publish_report_job
from api_gateway.models.report_entity import Report
from shared.observability import get_logger
from shared.schemas.report import (
    ReportJobMessage,
    ReportRequest,
    ReportResponse,
    ReportStatus,
)
from shared.utils import generate_id

logger = get_logger(__name__)

# Store background task references to prevent GC
_background_tasks: set[asyncio.Task] = set()


async def create_report_job(
    session: AsyncSession,
    request: ReportRequest,
) -> ReportResponse:
    """Insert a pending report record and publish job to RabbitMQ."""
    report_id = generate_id()

    now = datetime.now(UTC)
    entity = Report(
        id=report_id,
        locomotive_id=request.locomotive_id,
        report_type=request.report_type,
        format=request.format,
        status=ReportStatus.PENDING,
        data={},
        created_at=now,
    )
    session.add(entity)
    await session.commit()

    # Publish to RabbitMQ in background — don't block the response
    job = ReportJobMessage(
        report_id=report_id,
        locomotive_id=request.locomotive_id,
        report_type=request.report_type,
        format=request.format,
        date_range=request.date_range,
        requested_at=datetime.now(UTC),
    )
    task = asyncio.create_task(_publish_report_job_safe(job))
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)

    return ReportResponse(
        report_id=entity.id,
        locomotive_id=str(entity.locomotive_id) if entity.locomotive_id else None,
        report_type=entity.report_type,
        format=entity.format,
        status=entity.status,
        created_at=entity.created_at,
        data=None,
    )


async def _publish_report_job_safe(job: ReportJobMessage) -> None:
    try:
        await publish_report_job(job.model_dump(mode="json"))
    except Exception:
        logger.exception("Failed to publish report job to RabbitMQ", report_id=str(job.report_id))


async def get_report(session: AsyncSession, report_id: str) -> ReportResponse:
    """Fetch report status and data."""
    result = await session.execute(select(Report).where(Report.id == report_id))
    entity = result.scalar_one_or_none()
    if entity is None:
        raise HTTPException(status_code=404, detail="Report not found")

    return ReportResponse(
        report_id=entity.id,
        locomotive_id=str(entity.locomotive_id) if entity.locomotive_id else None,
        report_type=entity.report_type,
        format=entity.format,
        status=entity.status,
        created_at=entity.created_at,
        data=entity.data if entity.status == ReportStatus.COMPLETED else None,
    )


async def list_reports(
    session: AsyncSession,
    *,
    locomotive_id: str | None = None,
    status: str | None = None,
    offset: int = 0,
    limit: int = 20,
) -> list[ReportResponse]:
    """List reports with optional filters."""
    stmt = select(Report).order_by(Report.created_at.desc())

    if locomotive_id:
        stmt = stmt.where(Report.locomotive_id == locomotive_id)
    if status:
        stmt = stmt.where(Report.status == status)

    stmt = stmt.offset(offset).limit(limit)
    result = await session.execute(stmt)

    return [
        ReportResponse(
            report_id=r.id,
            locomotive_id=str(r.locomotive_id) if r.locomotive_id else None,
            report_type=r.report_type,
            format=r.format,
            status=r.status,
            created_at=r.created_at,
            data=None,
        )
        for r in result.scalars().all()
    ]
