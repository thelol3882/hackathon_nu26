"""Tests for report_service.servicer gRPC handlers."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from shared.schemas.report import ReportStatus

_NOW = datetime.now(UTC)


def _make_report_entity(**overrides):
    defaults = {
        "id": uuid.uuid4(),
        "locomotive_id": uuid.uuid4(),
        "report_type": "health_summary",
        "format": "json",
        "status": ReportStatus.COMPLETED,
        "created_at": _NOW,
        "data": {"summary": "ok"},
    }
    defaults.update(overrides)
    obj = MagicMock()
    for k, v in defaults.items():
        setattr(obj, k, v)
    return obj


def _mock_context():
    ctx = AsyncMock()
    ctx.abort = AsyncMock(side_effect=Exception("aborted"))
    return ctx


@pytest.mark.asyncio
@patch("report_service.servicer.report_repository")
@patch("report_service.servicer.get_db_session")
async def test_get_report_found(mock_get_session, mock_repo):
    entity = _make_report_entity()
    mock_repo.find_by_id = AsyncMock(return_value=entity)

    session = AsyncMock()
    mock_get_session.return_value = _async_gen(session)

    from report_service.servicer import ReportServicer

    servicer = ReportServicer()
    request = MagicMock()
    request.report_id = str(entity.id)

    response = await servicer.GetReport(request, _mock_context())

    assert response.report.report_id == str(entity.id)
    assert response.report.status == ReportStatus.COMPLETED
    assert json.loads(response.report.data) == {"summary": "ok"}


@pytest.mark.asyncio
@patch("report_service.servicer.report_repository")
@patch("report_service.servicer.get_db_session")
async def test_get_report_not_found(mock_get_session, mock_repo):
    mock_repo.find_by_id = AsyncMock(return_value=None)

    session = AsyncMock()
    mock_get_session.return_value = _async_gen(session)

    from report_service.servicer import ReportServicer

    servicer = ReportServicer()
    request = MagicMock()
    request.report_id = str(uuid.uuid4())

    with pytest.raises(Exception, match="aborted"):
        await servicer.GetReport(request, _mock_context())


@pytest.mark.asyncio
@patch("report_service.servicer.report_repository")
@patch("report_service.servicer.get_db_session")
async def test_list_reports(mock_get_session, mock_repo):
    entities = [_make_report_entity(), _make_report_entity()]
    mock_repo.find_many = AsyncMock(return_value=(entities, 2))

    session = AsyncMock()
    mock_get_session.return_value = _async_gen(session)

    from report_service.servicer import ReportServicer

    servicer = ReportServicer()
    request = MagicMock()
    request.locomotive_id = ""
    request.status = ""
    request.offset = 0
    request.limit = 20

    response = await servicer.ListReports(request, _mock_context())

    assert len(response.reports) == 2
    assert response.total == 2


@pytest.mark.asyncio
@patch("report_service.servicer.report_repository")
@patch("report_service.servicer.get_db_session")
async def test_download_report_json(mock_get_session, mock_repo):
    entity = _make_report_entity(format="json", data={"result": 42})
    mock_repo.find_by_id = AsyncMock(return_value=entity)

    session = AsyncMock()
    mock_get_session.return_value = _async_gen(session)

    from report_service.servicer import ReportServicer

    servicer = ReportServicer()
    request = MagicMock()
    request.report_id = str(entity.id)

    response = await servicer.DownloadReport(request, _mock_context())

    assert response.content_type == "application/json"
    assert response.format == "json"
    assert b"42" in response.content


@pytest.mark.asyncio
@patch("report_service.servicer.report_repository")
@patch("report_service.servicer.get_db_session")
async def test_download_report_not_completed(mock_get_session, mock_repo):
    entity = _make_report_entity(status=ReportStatus.PROCESSING)
    mock_repo.find_by_id = AsyncMock(return_value=entity)

    session = AsyncMock()
    mock_get_session.return_value = _async_gen(session)

    from report_service.servicer import ReportServicer

    servicer = ReportServicer()
    request = MagicMock()
    request.report_id = str(entity.id)

    with pytest.raises(Exception, match="aborted"):
        await servicer.DownloadReport(request, _mock_context())


async def _async_gen(value):
    yield value
