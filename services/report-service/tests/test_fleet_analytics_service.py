"""Tests for report_service.services.fleet_analytics_service."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from report_service.services.fleet_analytics_service import (
    get_fleet_summary,
    get_utilization_stats,
)

# ── Helpers ───────────────────────────────────────────────────────────────────


def _make_health_row(loco_id, loco_type, score, category):
    return SimpleNamespace(
        locomotive_id=loco_id,
        locomotive_type=loco_type,
        score=score,
        category=category,
    )


def _make_utilization_row(total, active, avg_speed):
    return SimpleNamespace(
        total_readings=total,
        active_readings=active,
        avg_speed=avg_speed,
    )


def _mock_session_with_result(result_obj):
    """Create a mock session whose execute returns a single result mock."""
    session = MagicMock(spec=AsyncSession)
    session.execute = AsyncMock(return_value=result_obj)
    return session


# ── Fleet summary tests ───────────────────────────────────────────────────────


class TestGetFleetSummary:
    @pytest.mark.asyncio
    async def test_fleet_summary_success(self):
        """Multiple locomotives produce correct totals and averages."""
        rows = [
            _make_health_row("loco-1", "TE33A", 90.0, "Норма"),
            _make_health_row("loco-2", "KZ8A", 60.0, "Внимание"),
            _make_health_row("loco-3", "TE33A", 30.0, "Критично"),
        ]
        result_mock = MagicMock()
        result_mock.fetchall.return_value = rows
        session = _mock_session_with_result(result_mock)

        summary = await get_fleet_summary(session)
        assert summary["total_locomotives"] == 3
        assert summary["by_category"] == {"Норма": 1, "Внимание": 1, "Критично": 1}
        assert summary["avg_health_score"] == round((90.0 + 60.0 + 30.0) / 3, 2)

    @pytest.mark.asyncio
    async def test_fleet_summary_empty(self):
        """No health rows -> total=0, avg=0.0."""
        result_mock = MagicMock()
        result_mock.fetchall.return_value = []
        session = _mock_session_with_result(result_mock)

        summary = await get_fleet_summary(session)
        assert summary["total_locomotives"] == 0
        assert summary["by_category"] == {}
        assert summary["avg_health_score"] == 0.0

    @pytest.mark.asyncio
    async def test_fleet_summary_single_loco(self):
        """Single locomotive returns its score as the average."""
        rows = [_make_health_row("loco-1", "TE33A", 75.0, "Внимание")]
        result_mock = MagicMock()
        result_mock.fetchall.return_value = rows
        session = _mock_session_with_result(result_mock)

        summary = await get_fleet_summary(session)
        assert summary["total_locomotives"] == 1
        assert summary["avg_health_score"] == 75.0


# ── Utilization stats tests ───────────────────────────────────────────────────


class TestGetUtilizationStats:
    @pytest.mark.asyncio
    async def test_utilization_stats_success(self):
        """Mix of active and idle readings produces correct rate."""
        row = _make_utilization_row(total=100, active=75, avg_speed=45.0)
        result_mock = MagicMock()
        result_mock.fetchone.return_value = row
        session = _mock_session_with_result(result_mock)

        stats = await get_utilization_stats(session)
        assert stats["utilization_rate"] == 0.75
        assert stats["avg_speed_kmh"] == 45.0
        assert stats["total_readings"] == 100

    @pytest.mark.asyncio
    async def test_utilization_no_data(self):
        """No readings -> rate=0.0, total=0."""
        row = _make_utilization_row(total=0, active=0, avg_speed=None)
        result_mock = MagicMock()
        result_mock.fetchone.return_value = row
        session = _mock_session_with_result(result_mock)

        stats = await get_utilization_stats(session)
        assert stats["utilization_rate"] == 0.0
        assert stats["avg_speed_kmh"] == 0.0
        assert stats["total_readings"] == 0

    @pytest.mark.asyncio
    async def test_utilization_all_active(self):
        """All readings have speed > 0 -> rate = 1.0."""
        row = _make_utilization_row(total=200, active=200, avg_speed=60.0)
        result_mock = MagicMock()
        result_mock.fetchone.return_value = row
        session = _mock_session_with_result(result_mock)

        stats = await get_utilization_stats(session)
        assert stats["utilization_rate"] == 1.0

    @pytest.mark.asyncio
    async def test_utilization_with_loco_filter(self):
        """Passing locomotive_id still works (query includes WHERE clause)."""
        row = _make_utilization_row(total=50, active=25, avg_speed=30.0)
        result_mock = MagicMock()
        result_mock.fetchone.return_value = row
        session = _mock_session_with_result(result_mock)

        stats = await get_utilization_stats(session, locomotive_id="loco-1")
        assert stats["utilization_rate"] == 0.5
        assert stats["total_readings"] == 50
