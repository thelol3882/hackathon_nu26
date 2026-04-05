"""RabbitMQ message handler: consume report jobs and execute the generation pipeline."""

from __future__ import annotations

import json
import traceback

import aio_pika
import structlog
from opentelemetry import trace

from report_service.core.database import get_db_session
from report_service.repositories import report_repository
from report_service.services.report_formatter import format_report
from report_service.services.report_generator import generate_report_data
from shared.log_codes import REPORT_COMPLETED, REPORT_FAILED, REPORT_PROCESSING
from shared.observability import get_logger
from shared.observability.prometheus import reports_generated_total
from shared.schemas.report import ReportJobMessage, ReportStatus

logger = get_logger(__name__)
tracer = trace.get_tracer(__name__)

# Analytics gRPC client is set from lifespan via set_analytics_client()
_analytics = None


def set_analytics_client(client) -> None:
    global _analytics
    _analytics = client


async def process_report_job(message: aio_pika.abc.AbstractIncomingMessage) -> None:
    """Process a single report generation job from RabbitMQ."""
    async with message.process():
        body = json.loads(message.body.decode())
        job = ReportJobMessage.model_validate(body)

        structlog.contextvars.bind_contextvars(
            report_id=str(job.report_id),
            report_type=job.report_type,
            report_format=str(job.format),
            locomotive_id=job.locomotive_id,
        )

        try:
            await _execute_job(job)
        finally:
            structlog.contextvars.clear_contextvars()


async def _execute_job(job: ReportJobMessage) -> None:
    """Run the report pipeline inside an OTEL span."""
    with tracer.start_as_current_span(
        "report.generate",
        attributes={
            "report.id": str(job.report_id),
            "report.type": job.report_type,
            "report.format": str(job.format),
            "locomotive.id": job.locomotive_id or "fleet",
        },
    ):
        logger.info("Processing report job", code=REPORT_PROCESSING)

        # DB session for report status updates (PostgreSQL)
        async for session in get_db_session():
            await report_repository.update_status(session, job.report_id, ReportStatus.PROCESSING)

            try:
                with tracer.start_as_current_span("report.query_data"):
                    # Analytics queries go via gRPC, not direct DB
                    data = await generate_report_data(_analytics, job)

                with tracer.start_as_current_span("report.format"):
                    formatted = format_report(data, job.format, job)

                await report_repository.update_status(session, job.report_id, ReportStatus.COMPLETED, data=formatted)

                reports_generated_total.labels(format=str(job.format), status="completed").inc()
                logger.info("Report completed", code=REPORT_COMPLETED)

            except Exception as exc:
                span = trace.get_current_span()
                span.set_status(trace.StatusCode.ERROR, str(exc))
                span.record_exception(exc)

                reports_generated_total.labels(format=str(job.format), status="failed").inc()
                logger.error(
                    "Report generation failed",
                    code=REPORT_FAILED,
                    error=str(exc),
                    traceback=traceback.format_exc(),
                )
                await session.rollback()
                await report_repository.update_status(
                    session, job.report_id, ReportStatus.FAILED, data={"error": str(exc)}
                )
