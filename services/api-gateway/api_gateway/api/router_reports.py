import base64
import csv
import io
import json

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response

from api_gateway.api.dependencies import DbSession
from api_gateway.services.report_request_service import (
    create_report_job,
    get_report,
    list_reports,
)
from shared.schemas.report import ReportRequest, ReportResponse, ReportStatus

router = APIRouter()


@router.post("/generate", status_code=201, response_model=ReportResponse)
async def generate_report(request: ReportRequest, db: DbSession):
    """Submit a report generation job. Poll GET /reports/{id} for status."""
    return await create_report_job(db, request)


@router.get("/", response_model=list[ReportResponse])
async def get_reports(
    db: DbSession,
    locomotive_id: str | None = Query(None),
    status: str | None = Query(None),
    offset: int = 0,
    limit: int = 20,
):
    """List reports with optional filters."""
    return await list_reports(db, locomotive_id=locomotive_id, status=status, offset=offset, limit=limit)


@router.get("/{report_id}", response_model=ReportResponse)
async def get_report_status(report_id: str, db: DbSession):
    """Get report status and data. Poll until status is 'completed'."""
    return await get_report(db, report_id)


@router.get("/{report_id}/download")
async def download_report(report_id: str, db: DbSession):
    """Download a completed report as a file."""
    report = await get_report(db, report_id)

    if report.status != ReportStatus.COMPLETED:
        raise HTTPException(
            status_code=409,
            detail=f"Report is not ready yet (status: {report.status})",
        )

    if not report.data:
        raise HTTPException(status_code=404, detail="Report has no data")

    if report.format == "csv":
        output = io.StringIO()
        if isinstance(report.data, dict) and "rows" in report.data:
            rows = report.data["rows"]
            if rows:
                writer = csv.DictWriter(output, fieldnames=rows[0].keys())
                writer.writeheader()
                writer.writerows(rows)
        else:
            output.write(json.dumps(report.data, indent=2, default=str))
        return Response(
            content=output.getvalue(),
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="report_{report_id}.csv"'},
        )

    if report.format == "json":
        return Response(
            content=json.dumps(report.data, indent=2, default=str),
            media_type="application/json",
            headers={"Content-Disposition": f'attachment; filename="report_{report_id}.json"'},
        )

    # PDF: report-service would generate and store as base64 in data["pdf_base64"]
    if report.format == "pdf":
        pdf_b64 = report.data.get("pdf_base64")
        if not pdf_b64:
            raise HTTPException(status_code=404, detail="PDF data not available")
        return Response(
            content=base64.b64decode(pdf_b64),
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="report_{report_id}.pdf"'},
        )

    raise HTTPException(status_code=400, detail=f"Unsupported format: {report.format}")
