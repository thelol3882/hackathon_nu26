"""Report request service — publishes tasks to RabbitMQ, queries via gRPC.

API Gateway does NOT own the generated_reports table.  It publishes
report generation tasks to RabbitMQ and queries Report Service via gRPC
for status, listing, and downloads.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

from fastapi import HTTPException

from api_gateway.core.rabbitmq import publish_report_job
from shared.grpc_client import ReportClient
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


async def create_report_job(request: ReportRequest) -> ReportResponse:
    """Publish a report generation task to RabbitMQ and return job_id.

    Report Service will consume the message, create the DB record,
    generate the report, and update the status.
    """
    report_id = generate_id()
    now = datetime.now(UTC)

    job = ReportJobMessage(
        report_id=report_id,
        locomotive_id=request.locomotive_id,
        report_type=request.report_type,
        format=request.format,
        date_range=request.date_range,
        requested_at=now,
    )

    task = asyncio.create_task(_publish_report_job_safe(job))
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)

    return ReportResponse(
        report_id=report_id,
        locomotive_id=request.locomotive_id,
        report_type=request.report_type,
        format=request.format,
        status=ReportStatus.PENDING,
        created_at=now,
        data=None,
    )


async def _publish_report_job_safe(job: ReportJobMessage) -> None:
    try:
        await publish_report_job(job.model_dump(mode="json"))
    except Exception:
        logger.exception("Failed to publish report job to RabbitMQ", report_id=str(job.report_id))


async def get_report(client: ReportClient, report_id: str) -> ReportResponse:
    """Get report status and data via gRPC."""
    result = await client.get_report(report_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Report not found")
    return _dict_to_response(result)


async def list_reports(
    client: ReportClient,
    *,
    locomotive_id: str | None = None,
    status: str | None = None,
    offset: int = 0,
    limit: int = 20,
) -> list[ReportResponse]:
    """List reports via gRPC."""
    result = await client.list_reports(
        locomotive_id=locomotive_id or "",
        status=status or "",
        offset=offset,
        limit=limit,
    )
    return [_dict_to_response(r) for r in result["reports"]]


def _dict_to_response(d: dict) -> ReportResponse:
    return ReportResponse(
        report_id=d["report_id"],
        locomotive_id=d.get("locomotive_id"),
        report_type=d["report_type"],
        format=d["format"],
        status=d["status"],
        created_at=d["created_at"],
        data=d.get("data"),
    )
