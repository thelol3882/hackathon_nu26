"""Tests for api_gateway.services.report_request_service."""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from shared.schemas.report import (
    DateRange,
    ReportFormat,
    ReportRequest,
    ReportResponse,
    ReportStatus,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_NOW = datetime.now(UTC)


def _make_report_entity(**overrides):
    defaults = {
        "id": uuid.uuid4(),
        "locomotive_id": uuid.uuid4(),
        "report_type": "health_summary",
        "format": ReportFormat.JSON,
        "status": ReportStatus.PENDING,
        "data": {},
        "created_at": _NOW,
    }
    defaults.update(overrides)
    obj = MagicMock()
    for k, v in defaults.items():
        setattr(obj, k, v)
    return obj


def _scalar_one_result(entity):
    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = entity
    return result_mock


def _scalars_result(entities):
    scalars_mock = MagicMock()
    scalars_mock.all.return_value = entities
    result_mock = MagicMock()
    result_mock.scalars.return_value = scalars_mock
    return result_mock


# ---------------------------------------------------------------------------
# create_report_job
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@patch("api_gateway.services.report_request_service.publish_report_job", new_callable=AsyncMock)
async def test_create_report_job_success(mock_publish, mock_session):
    entity = _make_report_entity()

    async def _refresh(e):
        for attr in ("id", "locomotive_id", "report_type", "format", "status", "created_at"):
            setattr(e, attr, getattr(entity, attr))

    mock_session.refresh.side_effect = _refresh

    request = ReportRequest(
        locomotive_id=str(entity.locomotive_id),
        report_type="health_summary",
        format=ReportFormat.JSON,
        date_range=DateRange(start=_NOW, end=_NOW),
    )

    with patch("api_gateway.services.report_request_service.generate_id", return_value=entity.id):
        from api_gateway.services.report_request_service import create_report_job

        result = await create_report_job(mock_session, request)

    # Let the background publish task run
    await asyncio.sleep(0)

    assert isinstance(result, ReportResponse)
    mock_session.add.assert_called_once()
    mock_session.commit.assert_awaited_once()
    mock_publish.assert_awaited_once()


# ---------------------------------------------------------------------------
# get_report
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_report_found(mock_session):
    entity = _make_report_entity(status=ReportStatus.PENDING)
    mock_session.execute.return_value = _scalar_one_result(entity)

    from api_gateway.services.report_request_service import get_report

    result = await get_report(mock_session, str(entity.id))

    assert isinstance(result, ReportResponse)
    # data should be None because status is PENDING
    assert result.data is None


@pytest.mark.asyncio
async def test_get_report_completed_includes_data(mock_session):
    entity = _make_report_entity(
        status=ReportStatus.COMPLETED,
        data={"summary": "all good"},
    )
    mock_session.execute.return_value = _scalar_one_result(entity)

    from api_gateway.services.report_request_service import get_report

    result = await get_report(mock_session, str(entity.id))

    assert result.data == {"summary": "all good"}


@pytest.mark.asyncio
async def test_get_report_not_found_404(mock_session):
    mock_session.execute.return_value = _scalar_one_result(None)

    from api_gateway.services.report_request_service import get_report

    with pytest.raises(HTTPException) as exc_info:
        await get_report(mock_session, str(uuid.uuid4()))

    assert exc_info.value.status_code == 404


# ---------------------------------------------------------------------------
# list_reports
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_reports_with_filters(mock_session):
    entities = [_make_report_entity() for _ in range(2)]
    mock_session.execute.return_value = _scalars_result(entities)

    from api_gateway.services.report_request_service import list_reports

    result = await list_reports(
        mock_session,
        locomotive_id=str(uuid.uuid4()),
        status="pending",
    )

    assert len(result) == 2
    assert all(isinstance(r, ReportResponse) for r in result)


@pytest.mark.asyncio
async def test_list_reports_empty(mock_session):
    mock_session.execute.return_value = _scalars_result([])

    from api_gateway.services.report_request_service import list_reports

    result = await list_reports(mock_session)

    assert result == []
