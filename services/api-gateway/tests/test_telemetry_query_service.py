"""Tests for api_gateway.services.telemetry_query_service."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest

from api_gateway.services.telemetry_query_service import (
    TelemetryBucket,
    TelemetryRaw,
    query_telemetry_bucketed,
    query_telemetry_raw,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_NOW = datetime.now(UTC)
_LOCO = str(uuid.uuid4())


def _bucket_row(**overrides):
    defaults = {
        "bucket": _NOW,
        "locomotive_id": _LOCO,
        "sensor_type": "coolant_temp",
        "avg_value": 82.0,
        "min_value": 78.0,
        "max_value": 86.0,
        "last_value": 84.0,
        "unit": "C",
    }
    defaults.update(overrides)
    row = MagicMock()
    for k, v in defaults.items():
        setattr(row, k, v)
    return row


def _raw_row(**overrides):
    defaults = {
        "time": _NOW,
        "locomotive_id": _LOCO,
        "locomotive_type": "TE33A",
        "sensor_type": "coolant_temp",
        "value": 82.0,
        "filtered_value": 81.5,
        "unit": "C",
        "latitude": 51.1,
        "longitude": 71.4,
    }
    defaults.update(overrides)
    row = MagicMock()
    for k, v in defaults.items():
        setattr(row, k, v)
    return row


# ---------------------------------------------------------------------------
# query_telemetry_bucketed
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_bucketed_returns_buckets(mock_session):
    mock_session.execute.return_value = MagicMock(fetchall=MagicMock(return_value=[_bucket_row(), _bucket_row()]))

    result = await query_telemetry_bucketed(
        mock_session,
        locomotive_id=_LOCO,
        sensor_type="coolant_temp",
        start=_NOW,
        end=_NOW,
    )

    assert len(result) == 2
    assert all(isinstance(r, TelemetryBucket) for r in result)


@pytest.mark.asyncio
async def test_bucketed_with_all_filters(mock_session):
    mock_session.execute.return_value = MagicMock(fetchall=MagicMock(return_value=[_bucket_row()]))

    result = await query_telemetry_bucketed(
        mock_session,
        locomotive_id=_LOCO,
        sensor_type="coolant_temp",
        start=_NOW,
        end=_NOW,
        bucket_interval="15 minutes",
        offset=5,
        limit=10,
    )

    assert len(result) == 1
    # Verify the execute call received the correct params
    call_args = mock_session.execute.call_args
    params = call_args[0][1]  # positional arg #1 is the params dict
    assert params["off"] == 5
    assert params["lim"] == 10
    # Interval is inlined into the SQL text, verify it's in the query string
    sql_text = str(call_args[0][0])
    assert "15 minutes" in sql_text


@pytest.mark.asyncio
async def test_bucketed_empty(mock_session):
    mock_session.execute.return_value = MagicMock(fetchall=MagicMock(return_value=[]))

    result = await query_telemetry_bucketed(mock_session)

    assert result == []


@pytest.mark.asyncio
async def test_bucketed_invalid_interval_falls_back(mock_session):
    mock_session.execute.return_value = MagicMock(fetchall=MagicMock(return_value=[]))

    await query_telemetry_bucketed(mock_session, bucket_interval="99 years")

    call_args = mock_session.execute.call_args
    # Invalid interval falls back to "1 minute", inlined in the SQL
    sql_text = str(call_args[0][0])
    assert "1 minute" in sql_text


# ---------------------------------------------------------------------------
# query_telemetry_raw
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_raw_returns_rows(mock_session):
    mock_session.execute.return_value = MagicMock(fetchall=MagicMock(return_value=[_raw_row()]))

    result = await query_telemetry_raw(
        mock_session,
        locomotive_id=_LOCO,
        sensor_type="coolant_temp",
        start=_NOW,
        end=_NOW,
    )

    assert len(result) == 1
    assert isinstance(result[0], TelemetryRaw)
    assert result[0].value == 82.0


@pytest.mark.asyncio
async def test_raw_empty(mock_session):
    mock_session.execute.return_value = MagicMock(fetchall=MagicMock(return_value=[]))

    result = await query_telemetry_raw(mock_session)

    assert result == []
