from fastapi import APIRouter

from report_service.api.dependencies import DbSession
from report_service.models.report_params import ReportRequest

router = APIRouter()


@router.post("/generate", status_code=201)
async def generate_report(request: ReportRequest, db: DbSession):
    """Generate a new report."""
    # TODO: implement
    return {"status": "queued"}


@router.get("/{report_id}")
async def get_report(report_id: str, db: DbSession):
    """Retrieve a generated report."""
    # TODO: implement
    return {}
