from fastapi import APIRouter

from report_service.api.dependencies import DbSession
from report_service.models.report_params import ReportRequest
from shared.log_codes import REPORT_QUEUED
from shared.observability import get_logger

logger = get_logger(__name__)

router = APIRouter()


@router.post("/generate", status_code=201)
async def generate_report(request: ReportRequest, db: DbSession):
    """Generate a new report."""
    logger.info(
        "Report generation requested",
        code=REPORT_QUEUED,
        report_type=request.report_type,
    )
    # TODO: implement
    return {"status": "queued"}


@router.get("/{report_id}")
async def get_report(report_id: str, db: DbSession):
    """Retrieve a generated report."""
    logger.info("Report retrieval requested", report_id=report_id)
    # TODO: implement
    return {}
