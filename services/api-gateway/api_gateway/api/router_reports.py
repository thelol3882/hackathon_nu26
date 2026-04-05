import grpc.aio
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response

from api_gateway.api.dependencies import Reports
from api_gateway.services.report_request_service import (
    create_report_job,
    get_report,
    list_reports,
)
from shared.schemas.report import ReportRequest, ReportResponse

router = APIRouter()


@router.post("/generate", status_code=201, response_model=ReportResponse)
async def generate_report(request: ReportRequest):
    """Submit a report generation job. Poll GET /reports/{id} for status."""
    return await create_report_job(request)


@router.get("/", response_model=list[ReportResponse])
async def get_reports(
    client: Reports,
    locomotive_id: str | None = Query(None),
    status: str | None = Query(None),
    offset: int = 0,
    limit: int = 20,
):
    """List reports with optional filters."""
    return await list_reports(client, locomotive_id=locomotive_id, status=status, offset=offset, limit=limit)


@router.get("/{report_id}", response_model=ReportResponse)
async def get_report_status(report_id: str, client: Reports):
    """Get report status and data. Poll until status is 'completed'."""
    return await get_report(client, report_id)


@router.get("/{report_id}/download")
async def download_report(report_id: str, client: Reports):
    """Download a completed report as a file."""
    try:
        result = await client.download_report(report_id)
    except grpc.aio.AioRpcError as e:
        if e.code() == grpc.StatusCode.NOT_FOUND:
            raise HTTPException(status_code=404, detail=e.details()) from None
        if e.code() == grpc.StatusCode.FAILED_PRECONDITION:
            raise HTTPException(status_code=409, detail=e.details()) from None
        raise

    return Response(
        content=result["content"],
        media_type=result["content_type"],
        headers={"Content-Disposition": f'attachment; filename="{result["filename"]}"'},
    )
