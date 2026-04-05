"""Report request service — business logic, calls repository for DB access."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from api_gateway.core.rabbitmq import publish_report_job
from api_gateway.models.report_entity import Report
from api_gateway.repositories import report_repository
from shared.observability import get_logger
from shared.schemas.report import (
    ReportJobMessage,
    ReportRequest,
    ReportResponse,
    ReportStatus,
)
from shared.utils import generate_id

logger = get_logger(__name__)

_background_tasks: set[asyncio.Task] = set()


def _entity_to_response(entity: Report, *, include_data: bool = False) -> ReportResponse:
    return ReportResponse(
        report_id=entity.id,
        locomotive_id=str(entity.locomotive_id) if entity.locomotive_id else None,
        report_type=entity.report_type,
        format=entity.format,
        status=entity.status,
        created_at=entity.created_at,
        data=entity.data if include_data and entity.status == ReportStatus.COMPLETED else None,
    )


async def create_report_job(
    session: AsyncSession,
    request: ReportRequest,
) -> ReportResponse:
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
    entity = await report_repository.create(session, entity)

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

    return _entity_to_response(entity)


async def _publish_report_job_safe(job: ReportJobMessage) -> None:
    try:
        await publish_report_job(job.model_dump(mode="json"))
    except Exception:
        logger.exception("Failed to publish report job to RabbitMQ", report_id=str(job.report_id))


async def get_report(session: AsyncSession, report_id: str) -> ReportResponse:
    entity = await report_repository.find_by_id(session, report_id)
    if entity is None:
        raise HTTPException(status_code=404, detail="Report not found")
    return _entity_to_response(entity, include_data=True)


async def list_reports(
    session: AsyncSession,
    *,
    locomotive_id: str | None = None,
    status: str | None = None,
    offset: int = 0,
    limit: int = 20,
) -> list[ReportResponse]:
    entities = await report_repository.find_many(
        session, locomotive_id=locomotive_id, status=status, offset=offset, limit=limit
    )
    return [_entity_to_response(e) for e in entities]
