"""Tests for api_gateway.services.telemetry_query_service."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

import pytest

from api_gateway.repositories.telemetry_repository import pick_level
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
# pick_level — auto-select aggregate resolution
# ---------------------------------------------------------------------------


class TestPickLevel:
    def test_none_start_returns_raw(self):
        level = pick_level(None, _NOW)
        assert level.source_table == "raw_telemetry"

    def test_none_end_returns_raw(self):
        level = pick_level(_NOW, None)
        assert level.source_table == "raw_telemetry"

    def test_short_range_returns_raw(self):
        """Under 15 minutes -> raw_telemetry."""
        start = _NOW - timedelta(minutes=10)
        level = pick_level(start, _NOW)
        assert level.source_table == "raw_telemetry"

    def test_15min_range_returns_1min(self):
        """15 minutes to 2 hours -> telemetry_1min."""
        start = _NOW - timedelta(minutes=30)
        level = pick_level(start, _NOW)
        assert level.source_table == "telemetry_1min"

    def test_3hour_range_returns_15min(self):
        """2 hours to 24 hours -> telemetry_15min."""
        start = _NOW - timedelta(hours=3)
        level = pick_level(start, _NOW)
        assert level.source_table == "telemetry_15min"

    def test_48hour_range_returns_1hour(self):
        """Over 24 hours -> telemetry_1hour."""
        start = _NOW - timedelta(hours=48)
        level = pick_level(start, _NOW)
        assert level.source_table == "telemetry_1hour"

    def test_boundary_exactly_15min(self):
        """Exactly 15 minutes -> still raw (stays in finer level for precision)."""
        start = _NOW - timedelta(minutes=15)
        level = pick_level(start, _NOW)
        assert level.source_table == "raw_telemetry"

    def test_boundary_just_over_15min(self):
        """Just over 15 minutes -> telemetry_1min."""
        start = _NOW - timedelta(minutes=15, seconds=1)
        level = pick_level(start, _NOW)
        assert level.source_table == "telemetry_1min"

    def test_boundary_exactly_2hours(self):
        """Exactly 2 hours -> still 1min (stays in finer level)."""
        start = _NOW - timedelta(hours=2)
        level = pick_level(start, _NOW)
        assert level.source_table == "telemetry_1min"

    def test_boundary_just_over_2hours(self):
        """Just over 2 hours -> telemetry_15min."""
        start = _NOW - timedelta(hours=2, seconds=1)
        level = pick_level(start, _NOW)
        assert level.source_table == "telemetry_15min"

    def test_boundary_exactly_24hours(self):
        """Exactly 24 hours -> still 15min (stays in finer level)."""
        start = _NOW - timedelta(hours=24)
        level = pick_level(start, _NOW)
        assert level.source_table == "telemetry_15min"

    def test_boundary_just_over_24hours(self):
        """Just over 24 hours -> telemetry_1hour."""
        start = _NOW - timedelta(hours=24, seconds=1)
        level = pick_level(start, _NOW)
        assert level.source_table == "telemetry_1hour"


# ---------------------------------------------------------------------------
# query_telemetry_bucketed
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_bucketed_returns_buckets(mock_session):
    mock_session.execute.return_value = MagicMock(fetchall=MagicMock(return_value=[_bucket_row(), _bucket_row()]))

    result, data_source = await query_telemetry_bucketed(
        mock_session,
        locomotive_id=_LOCO,
        sensor_type="coolant_temp",
        start=_NOW,
        end=_NOW,
    )

    assert len(result) == 2
    assert all(isinstance(r, TelemetryBucket) for r in result)
    assert isinstance(data_source, str)


@pytest.mark.asyncio
async def test_bucketed_empty(mock_session):
    mock_session.execute.return_value = MagicMock(fetchall=MagicMock(return_value=[]))

    result, data_source = await query_telemetry_bucketed(mock_session)

    assert result == []
    assert data_source == "raw (1s)"


@pytest.mark.asyncio
async def test_bucketed_selects_1min_for_30min_range(mock_session):
    """A 30-minute range should query telemetry_1min."""
    mock_session.execute.return_value = MagicMock(fetchall=MagicMock(return_value=[_bucket_row()]))
    start = _NOW - timedelta(minutes=30)

    _result, data_source = await query_telemetry_bucketed(
        mock_session,
        start=start,
        end=_NOW,
    )

    assert data_source == "1min aggregate"
    # Verify the SQL references telemetry_1min
    sql_text = str(mock_session.execute.call_args[0][0])
    assert "telemetry_1min" in sql_text


@pytest.mark.asyncio
async def test_bucketed_selects_1hour_for_48h_range(mock_session):
    """A 48-hour range should query telemetry_1hour."""
    mock_session.execute.return_value = MagicMock(fetchall=MagicMock(return_value=[]))
    start = _NOW - timedelta(hours=48)

    _result, data_source = await query_telemetry_bucketed(
        mock_session,
        start=start,
        end=_NOW,
    )

    assert data_source == "1hour aggregate"
    sql_text = str(mock_session.execute.call_args[0][0])
    assert "telemetry_1hour" in sql_text


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
