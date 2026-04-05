"""Tests for api_gateway.services.alert_service."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from shared.enums import AlertSeverity
from shared.schemas.alert import AlertEvent

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_alert_entity(**overrides):
    defaults = {
        "id": uuid.uuid4(),
        "locomotive_id": uuid.uuid4(),
        "sensor_type": "coolant_temp",
        "severity": AlertSeverity.WARNING,
        "value": 98.0,
        "threshold_min": 70.0,
        "threshold_max": 95.0,
        "message": "Coolant temperature high",
        "timestamp": datetime.now(UTC),
        "acknowledged": False,
        "acknowledged_at": None,
        "created_at": datetime.now(UTC),
    }
    defaults.update(overrides)
    obj = MagicMock()
    for k, v in defaults.items():
        setattr(obj, k, v)
    return obj


def _scalars_result(entities):
    scalars_mock = MagicMock()
    scalars_mock.all.return_value = entities
    result_mock = MagicMock()
    result_mock.scalars.return_value = scalars_mock
    return result_mock


def _scalar_one_result(entity):
    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = entity
    return result_mock


def _mappings_result(entity):
    """Build a mock result whose .mappings().first() returns entity fields as a dict."""
    if entity is None:
        row = None
    else:
        row = {
            "id": entity.id,
            "locomotive_id": entity.locomotive_id,
            "sensor_type": entity.sensor_type,
            "severity": entity.severity,
            "value": entity.value,
            "threshold_min": entity.threshold_min,
            "threshold_max": entity.threshold_max,
            "message": entity.message,
            "timestamp": entity.timestamp,
            "acknowledged": entity.acknowledged,
        }
    mappings_mock = MagicMock()
    mappings_mock.first.return_value = row
    result_mock = MagicMock()
    result_mock.mappings.return_value = mappings_mock
    return result_mock


# ---------------------------------------------------------------------------
# list_alerts
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_alerts_no_filters(mock_session):
    entities = [_make_alert_entity() for _ in range(3)]
    mock_session.execute.return_value = _scalars_result(entities)

    from api_gateway.services.alert_service import list_alerts

    result = await list_alerts(mock_session)

    assert len(result) == 3
    assert all(isinstance(r, AlertEvent) for r in result)


@pytest.mark.asyncio
async def test_list_alerts_filter_by_locomotive_id(mock_session):
    loco_id = uuid.uuid4()
    entities = [_make_alert_entity(locomotive_id=loco_id)]
    mock_session.execute.return_value = _scalars_result(entities)

    from api_gateway.services.alert_service import list_alerts

    result = await list_alerts(mock_session, locomotive_id=str(loco_id))

    assert len(result) == 1


@pytest.mark.asyncio
async def test_list_alerts_filter_by_severity(mock_session):
    entities = [_make_alert_entity(severity=AlertSeverity.CRITICAL)]
    mock_session.execute.return_value = _scalars_result(entities)

    from api_gateway.services.alert_service import list_alerts

    result = await list_alerts(mock_session, severity="critical")

    assert len(result) == 1


@pytest.mark.asyncio
async def test_list_alerts_filter_by_acknowledged(mock_session):
    entities = [_make_alert_entity(acknowledged=True)]
    mock_session.execute.return_value = _scalars_result(entities)

    from api_gateway.services.alert_service import list_alerts

    result = await list_alerts(mock_session, acknowledged=True)

    assert len(result) == 1


@pytest.mark.asyncio
async def test_list_alerts_empty(mock_session):
    mock_session.execute.return_value = _scalars_result([])

    from api_gateway.services.alert_service import list_alerts

    result = await list_alerts(mock_session)

    assert result == []


# ---------------------------------------------------------------------------
# get_alert
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_alert_found(mock_session):
    entity = _make_alert_entity()
    mock_session.execute.return_value = _scalar_one_result(entity)

    from api_gateway.services.alert_service import get_alert

    result = await get_alert(mock_session, str(entity.id))

    assert isinstance(result, AlertEvent)
    assert result.id == entity.id


@pytest.mark.asyncio
async def test_get_alert_not_found_404(mock_session):
    mock_session.execute.return_value = _scalar_one_result(None)

    from api_gateway.services.alert_service import get_alert

    with pytest.raises(HTTPException) as exc_info:
        await get_alert(mock_session, str(uuid.uuid4()))

    assert exc_info.value.status_code == 404


# ---------------------------------------------------------------------------
# acknowledge_alert
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_acknowledge_alert_success(mock_session):
    entity = _make_alert_entity(acknowledged=False)
    # execute is called 3 times: 2 UPDATEs + 1 SELECT (mappings)
    update_result = MagicMock()
    mock_session.execute.side_effect = [update_result, update_result, _mappings_result(entity)]

    from api_gateway.services.alert_service import acknowledge_alert

    result = await acknowledge_alert(mock_session, str(entity.id))

    assert isinstance(result, AlertEvent)
    mock_session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_acknowledge_alert_already_acknowledged(mock_session):
    entity = _make_alert_entity(acknowledged=True, acknowledged_at=datetime.now(UTC))
    update_result = MagicMock()
    mock_session.execute.side_effect = [update_result, update_result, _mappings_result(entity)]

    from api_gateway.services.alert_service import acknowledge_alert

    result = await acknowledge_alert(mock_session, str(entity.id))

    # Should succeed idempotently
    assert isinstance(result, AlertEvent)
    mock_session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_acknowledge_alert_not_found_404(mock_session):
    update_result = MagicMock()
    mock_session.execute.side_effect = [update_result, update_result, _mappings_result(None)]

    from api_gateway.services.alert_service import acknowledge_alert

    with pytest.raises(HTTPException) as exc_info:
        await acknowledge_alert(mock_session, str(uuid.uuid4()))

    assert exc_info.value.status_code == 404
