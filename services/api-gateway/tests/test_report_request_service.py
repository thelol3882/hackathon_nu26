"""Tests for api_gateway.services.report_request_service.

After the separation, API Gateway no longer touches the generated_reports
table.  It publishes tasks to RabbitMQ and queries Report Service via gRPC.
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException

from shared.schemas.report import (
    DateRange,
    ReportFormat,
    ReportRequest,
    ReportResponse,
    ReportStatus,
)

_NOW = datetime.now(UTC)


def _make_report_dict(**overrides):
    defaults = {
        "report_id": str(uuid.uuid4()),
        "locomotive_id": str(uuid.uuid4()),
        "report_type": "health_summary",
        "format": "json",
        "status": "pending",
        "created_at": _NOW.isoformat(),
        "data": None,
    }
    defaults.update(overrides)
    return defaults


# ---------------------------------------------------------------------------
# create_report_job — publishes to RabbitMQ, returns job_id
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@patch("api_gateway.services.report_request_service.publish_report_job", new_callable=AsyncMock)
async def test_create_report_job_success(mock_publish):
    request = ReportRequest(
        locomotive_id=str(uuid.uuid4()),
        report_type="health_summary",
        format=ReportFormat.JSON,
        date_range=DateRange(start=_NOW, end=_NOW),
    )

    from api_gateway.services.report_request_service import create_report_job

    result = await create_report_job(request)

    # Let the background publish task run
    await asyncio.sleep(0)

    assert isinstance(result, ReportResponse)
    assert result.status == ReportStatus.PENDING
    assert result.data is None
    mock_publish.assert_awaited_once()


# ---------------------------------------------------------------------------
# get_report — queries via gRPC
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_report_found():
    client = AsyncMock()
    client.get_report = AsyncMock(return_value=_make_report_dict(status="pending"))

    from api_gateway.services.report_request_service import get_report

    result = await get_report(client, str(uuid.uuid4()))

    assert isinstance(result, ReportResponse)
    assert result.data is None


@pytest.mark.asyncio
async def test_get_report_completed_includes_data():
    client = AsyncMock()
    client.get_report = AsyncMock(return_value=_make_report_dict(status="completed", data={"summary": "all good"}))

    from api_gateway.services.report_request_service import get_report

    result = await get_report(client, str(uuid.uuid4()))

    assert result.data == {"summary": "all good"}


@pytest.mark.asyncio
async def test_get_report_not_found_404():
    client = AsyncMock()
    client.get_report = AsyncMock(return_value=None)

    from api_gateway.services.report_request_service import get_report

    with pytest.raises(HTTPException) as exc_info:
        await get_report(client, str(uuid.uuid4()))

    assert exc_info.value.status_code == 404


# ---------------------------------------------------------------------------
# list_reports — queries via gRPC
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_reports_with_filters():
    client = AsyncMock()
    client.list_reports = AsyncMock(return_value={"reports": [_make_report_dict(), _make_report_dict()], "total": 2})

    from api_gateway.services.report_request_service import list_reports

    result = await list_reports(client, locomotive_id=str(uuid.uuid4()), status="pending")

    assert len(result) == 2
    assert all(isinstance(r, ReportResponse) for r in result)


@pytest.mark.asyncio
async def test_list_reports_empty():
    client = AsyncMock()
    client.list_reports = AsyncMock(return_value={"reports": [], "total": 0})

    from api_gateway.services.report_request_service import list_reports

    result = await list_reports(client)

    assert result == []
