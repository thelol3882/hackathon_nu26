"""Orchestrates report generation: calculate → format → store."""

import asyncpg

from report_service.models.report_params import ReportRequest
from shared.log_codes import REPORT_QUEUED
from shared.observability import get_logger

logger = get_logger(__name__)


async def generate_report(pool: asyncpg.Pool, request: ReportRequest) -> dict:
    """Generate a report based on the request parameters."""
    logger.info(
        "Report generation started",
        code=REPORT_QUEUED,
        report_type=request.report_type,
        format=request.format,
    )
    # TODO: implement calculation pipeline
    return {
        "report_type": request.report_type,
        "format": request.format,
        "status": "generated",
    }
