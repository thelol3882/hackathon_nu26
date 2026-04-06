"""gRPC servicer for report queries (status/list/download).

Job submission goes through RabbitMQ, not gRPC.
"""

from __future__ import annotations

import base64
import csv
import io
import json

import grpc

from report_service.core.database import get_db_session
from report_service.repositories import report_repository
from shared.generated import report_pb2, report_pb2_grpc
from shared.observability import get_logger
from shared.schemas.report import ReportStatus

logger = get_logger(__name__)


def _entity_to_proto(entity, *, include_data: bool = False) -> report_pb2.ReportEntry:
    data = b""
    if include_data and entity.status == ReportStatus.COMPLETED and entity.data:
        data = json.dumps(entity.data, default=str).encode("utf-8")

    return report_pb2.ReportEntry(
        report_id=str(entity.id),
        locomotive_id=str(entity.locomotive_id) if entity.locomotive_id else "",
        report_type=entity.report_type,
        format=entity.format,
        status=entity.status,
        created_at=entity.created_at.isoformat(),
        data=data,
    )


class ReportServicer(report_pb2_grpc.ReportServiceServicer):
    async def GetReport(self, request, context):
        async for session in get_db_session():
            entity = await report_repository.find_by_id(session, request.report_id)
            if entity is None:
                await context.abort(grpc.StatusCode.NOT_FOUND, f"Report {request.report_id} not found")
                return None
            return report_pb2.GetReportResponse(
                report=_entity_to_proto(entity, include_data=True),
            )
        return None

    async def ListReports(self, request, context):
        async for session in get_db_session():
            reports, total = await report_repository.find_many(
                session,
                locomotive_id=request.locomotive_id or None,
                status=request.status or None,
                offset=request.offset,
                limit=request.limit or 20,
            )
            return report_pb2.ListReportsResponse(
                reports=[_entity_to_proto(r, include_data=False) for r in reports],
                total=total,
            )
        return None

    async def DownloadReport(self, request, context):
        async for session in get_db_session():
            entity = await report_repository.find_by_id(session, request.report_id)
            if entity is None:
                await context.abort(grpc.StatusCode.NOT_FOUND, f"Report {request.report_id} not found")
                return None
            if entity.status != ReportStatus.COMPLETED:
                await context.abort(
                    grpc.StatusCode.FAILED_PRECONDITION,
                    f"Report is not ready yet (status: {entity.status})",
                )
                return None
            if not entity.data:
                await context.abort(grpc.StatusCode.NOT_FOUND, "Report has no data")
                return None

            report_id = str(entity.id)
            fmt = entity.format

            if fmt == "csv":
                content, content_type, filename = _format_csv(entity.data, report_id)
            elif fmt == "json":
                content = json.dumps(entity.data, indent=2, default=str).encode("utf-8")
                content_type = "application/json"
                filename = f"report_{report_id}.json"
            elif fmt == "pdf":
                pdf_b64 = entity.data.get("pdf_base64")
                if not pdf_b64:
                    await context.abort(grpc.StatusCode.NOT_FOUND, "PDF data not available")
                    return None
                content = base64.b64decode(pdf_b64)
                content_type = "application/pdf"
                filename = f"report_{report_id}.pdf"
            else:
                await context.abort(grpc.StatusCode.INVALID_ARGUMENT, f"Unsupported format: {fmt}")
                return None

            return report_pb2.DownloadReportResponse(
                format=fmt,
                content=content,
                filename=filename,
                content_type=content_type,
            )
        return None


def _format_csv(data: dict, report_id: str) -> tuple[bytes, str, str]:
    output = io.StringIO()
    if isinstance(data, dict) and "rows" in data:
        rows = data["rows"]
        if rows:
            writer = csv.DictWriter(output, fieldnames=rows[0].keys())
            writer.writeheader()
            writer.writerows(rows)
    else:
        output.write(json.dumps(data, indent=2, default=str))
    return output.getvalue().encode("utf-8"), "text/csv", f"report_{report_id}.csv"
