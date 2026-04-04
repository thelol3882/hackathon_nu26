"""Orchestrates report generation: calculate → format → store."""

import asyncpg

from report_service.models.report_params import ReportRequest


async def generate_report(pool: asyncpg.Pool, request: ReportRequest) -> dict:
    """Generate a report based on the request parameters."""
    # TODO: implement calculation pipeline
    return {
        "report_type": request.report_type,
        "format": request.format,
        "status": "generated",
    }
