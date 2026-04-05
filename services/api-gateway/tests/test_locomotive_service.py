"""Tests for api_gateway.services.locomotive_service."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError

from shared.enums import LocomotiveStatus
from shared.schemas.locomotive import LocomotiveCreate, LocomotiveListResponse, LocomotiveRead

# ---------------------------------------------------------------------------
# Helper: build a fake Locomotive entity that model_validate(from_attributes)
# can read via attribute access.
# ---------------------------------------------------------------------------


def _make_entity(**overrides):
    defaults = {
        "id": uuid.uuid4(),
        "serial_number": "SN-001",
        "model": "TE33A",
        "manufacturer": "GE",
        "year_manufactured": 2020,
        "status": LocomotiveStatus.ACTIVE,
        "created_at": datetime.now(UTC),
        "updated_at": datetime.now(UTC),
    }
    defaults.update(overrides)
    obj = MagicMock()
    for k, v in defaults.items():
        setattr(obj, k, v)
    # Make sure __dict__ works for Pydantic from_attributes
    obj.__dict__.update(defaults)
    return obj


# ---------------------------------------------------------------------------
# create_locomotive
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_locomotive_success(mock_session):
    entity = _make_entity()

    # After refresh, the session mock should expose the entity via refresh side-effect
    async def _refresh(e):
        for attr in (
            "id",
            "serial_number",
            "model",
            "manufacturer",
            "year_manufactured",
            "status",
            "created_at",
            "updated_at",
        ):
            setattr(e, attr, getattr(entity, attr))
            e.__dict__[attr] = getattr(entity, attr)

    mock_session.refresh.side_effect = _refresh

    data = LocomotiveCreate(serial_number="SN-001", model="TE33A", manufacturer="GE", year_manufactured=2020)

    with patch("api_gateway.services.locomotive_service.generate_id", return_value=entity.id):
        from api_gateway.services.locomotive_service import create_locomotive

        result = await create_locomotive(mock_session, data)

    assert isinstance(result, LocomotiveRead)
    assert result.serial_number == "SN-001"
    mock_session.add.assert_called_once()
    mock_session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_create_locomotive_duplicate_409(mock_session):
    mock_session.commit.side_effect = IntegrityError("dup", params=None, orig=Exception())

    data = LocomotiveCreate(serial_number="SN-DUP", model="TE33A", manufacturer="GE", year_manufactured=2020)

    from api_gateway.services.locomotive_service import create_locomotive

    with pytest.raises(HTTPException) as exc_info:
        await create_locomotive(mock_session, data)

    assert exc_info.value.status_code == 409
    mock_session.rollback.assert_awaited_once()


# ---------------------------------------------------------------------------
# get_locomotive
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_locomotive_found(mock_session):
    entity = _make_entity()
    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = entity
    mock_session.execute.return_value = result_mock

    from api_gateway.services.locomotive_service import get_locomotive

    result = await get_locomotive(mock_session, str(entity.id))

    assert isinstance(result, LocomotiveRead)
    assert result.id == entity.id


@pytest.mark.asyncio
async def test_get_locomotive_not_found_404(mock_session):
    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = None
    mock_session.execute.return_value = result_mock

    from api_gateway.services.locomotive_service import get_locomotive

    with pytest.raises(HTTPException) as exc_info:
        await get_locomotive(mock_session, str(uuid.uuid4()))

    assert exc_info.value.status_code == 404


# ---------------------------------------------------------------------------
# list_locomotives
# ---------------------------------------------------------------------------


def _mock_list_session(mock_session, entities):
    """Set up mock_session.execute to return count then rows for list_locomotives."""
    count_result = MagicMock()
    count_result.scalar_one.return_value = len(entities)

    scalars_mock = MagicMock()
    scalars_mock.all.return_value = entities
    rows_result = MagicMock()
    rows_result.scalars.return_value = scalars_mock

    mock_session.execute.side_effect = [count_result, rows_result]


@pytest.mark.asyncio
async def test_list_locomotives_returns_list(mock_session):
    entities = [_make_entity(serial_number=f"SN-{i}") for i in range(3)]
    _mock_list_session(mock_session, entities)

    from api_gateway.services.locomotive_service import list_locomotives

    result = await list_locomotives(mock_session, offset=0, limit=50)

    assert isinstance(result, LocomotiveListResponse)
    assert result.total == 3
    assert len(result.items) == 3
    assert all(isinstance(r, LocomotiveRead) for r in result.items)


@pytest.mark.asyncio
async def test_list_locomotives_empty(mock_session):
    _mock_list_session(mock_session, [])

    from api_gateway.services.locomotive_service import list_locomotives

    result = await list_locomotives(mock_session)

    assert isinstance(result, LocomotiveListResponse)
    assert result.total == 0
    assert result.items == []
