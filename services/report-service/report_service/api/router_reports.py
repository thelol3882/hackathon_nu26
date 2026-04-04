from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from report_service.api.dependencies import DbSession
from report_service.models.report_entity import Report
from report_service.models.report_params import ReportRequest
from report_service.services.report_formatter import format_report
from report_service.services.report_generator import generate_report_data
from shared.log_codes import REPORT_COMPLETED, REPORT_NOT_FOUND, REPORT_QUEUED
from shared.observability import get_logger
from shared.schemas.report import ReportFormat, ReportJobMessage, ReportResponse, ReportStatus
from shared.utils import generate_id

logger = get_logger(__name__)

router = APIRouter()


@router.post("/generate", status_code=201)
async def generate_report(request: ReportRequest, db: DbSession):
    """Generate a report synchronously (direct path, no RabbitMQ)."""
    report_id = generate_id()

    logger.info(
        "Report generation requested",
        code=REPORT_QUEUED,
        report_type=request.report_type,
        report_id=str(report_id),
    )

    # Create DB record
    entity = Report(
        id=report_id,
        locomotive_id=request.locomotive_id,
        report_type=request.report_type,
        format=request.format,
        status=ReportStatus.PROCESSING,
        data={},
    )
    db.add(entity)
    await db.commit()

    try:
        # Build a job message for the generator
        from datetime import UTC, datetime

        job = ReportJobMessage(
            report_id=report_id,
            locomotive_id=str(request.locomotive_id) if request.locomotive_id else None,
            report_type=request.report_type,
            format=request.format,
            date_range=request.date_range,
            requested_at=datetime.now(UTC),
        )

        data = await generate_report_data(db, job)
        formatted = format_report(data, ReportFormat(request.format), job)

        entity.status = ReportStatus.COMPLETED
        entity.data = formatted
        await db.commit()

        logger.info("Report completed", code=REPORT_COMPLETED, report_id=str(report_id))

        return ReportResponse(
            report_id=report_id,
            locomotive_id=str(request.locomotive_id) if request.locomotive_id else None,
            report_type=request.report_type,
            format=request.format,
            status=ReportStatus.COMPLETED,
            created_at=entity.created_at,
            data=formatted,
        )

    except Exception as exc:
        entity.status = ReportStatus.FAILED
        entity.data = {"error": str(exc)}
        await db.commit()
        raise HTTPException(status_code=500, detail=f"Report generation failed: {exc}") from exc


@router.get("/{report_id}")
async def get_report(report_id: str, db: DbSession):
    """Retrieve a generated report by ID."""
    result = await db.execute(select(Report).where(Report.id == report_id))
    entity = result.scalar_one_or_none()
    if entity is None:
        logger.info("Report not found", code=REPORT_NOT_FOUND, report_id=report_id)
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
