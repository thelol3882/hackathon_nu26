"""Tests for report_service.services.fleet_analytics_service."""

from unittest.mock import AsyncMock

import pytest

from report_service.services.fleet_analytics_service import (
    get_fleet_summary,
    get_utilization_stats,
)

# ── Helpers ───────────────────────────────────────────────────────────────────


def _mock_analytics(**overrides):
    """Create a mock AnalyticsClient with async methods."""
    client = AsyncMock()
    for k, v in overrides.items():
        setattr(client, k, AsyncMock(return_value=v))
    return client


# ── Fleet summary tests ───────────────────────────────────────────────────────


class TestGetFleetSummary:
    @pytest.mark.asyncio
    async def test_fleet_summary_success(self):
        """Multiple locomotives produce correct totals and averages."""
        analytics = _mock_analytics(
            get_fleet_latest_snapshots=[
                {"locomotive_id": "loco-1", "locomotive_type": "TE33A", "score": 90.0, "category": "Норма"},
                {"locomotive_id": "loco-2", "locomotive_type": "KZ8A", "score": 60.0, "category": "Внимание"},
                {"locomotive_id": "loco-3", "locomotive_type": "TE33A", "score": 30.0, "category": "Критично"},
            ]
        )

        summary = await get_fleet_summary(analytics)
        assert summary["total_locomotives"] == 3
        assert summary["by_category"] == {"Норма": 1, "Внимание": 1, "Критично": 1}
        assert summary["avg_health_score"] == round((90.0 + 60.0 + 30.0) / 3, 2)

    @pytest.mark.asyncio
    async def test_fleet_summary_empty(self):
        """No health rows -> total=0, avg=0.0."""
        analytics = _mock_analytics(get_fleet_latest_snapshots=[])

        summary = await get_fleet_summary(analytics)
        assert summary["total_locomotives"] == 0
        assert summary["by_category"] == {}
        assert summary["avg_health_score"] == 0.0

    @pytest.mark.asyncio
    async def test_fleet_summary_single_loco(self):
        """Single locomotive returns its score as the average."""
        analytics = _mock_analytics(
            get_fleet_latest_snapshots=[
                {"locomotive_id": "loco-1", "locomotive_type": "TE33A", "score": 75.0, "category": "Внимание"},
            ]
        )

        summary = await get_fleet_summary(analytics)
        assert summary["total_locomotives"] == 1
        assert summary["avg_health_score"] == 75.0


# ── Utilization stats tests ───────────────────────────────────────────────────


class TestGetUtilizationStats:
    @pytest.mark.asyncio
    async def test_utilization_stats_success(self):
        """Mix of active and idle readings produces correct rate."""
        analytics = _mock_analytics(
            get_utilization={"total_readings": 100, "active_readings": 75, "avg_speed": 45.0, "max_speed": 80.0}
        )

        stats = await get_utilization_stats(analytics)
        assert stats["utilization_rate"] == 0.75
        assert stats["avg_speed_kmh"] == 45.0
        assert stats["total_readings"] == 100

    @pytest.mark.asyncio
    async def test_utilization_no_data(self):
        """No readings -> rate=0.0, total=0."""
        analytics = _mock_analytics(
            get_utilization={"total_readings": 0, "active_readings": 0, "avg_speed": 0.0, "max_speed": 0.0}
        )

        stats = await get_utilization_stats(analytics)
        assert stats["utilization_rate"] == 0.0
        assert stats["avg_speed_kmh"] == 0.0
        assert stats["total_readings"] == 0

    @pytest.mark.asyncio
    async def test_utilization_all_active(self):
        """All readings have speed > 0 -> rate = 1.0."""
        analytics = _mock_analytics(
            get_utilization={"total_readings": 200, "active_readings": 200, "avg_speed": 60.0, "max_speed": 90.0}
        )

        stats = await get_utilization_stats(analytics)
        assert stats["utilization_rate"] == 1.0

    @pytest.mark.asyncio
    async def test_utilization_with_loco_filter(self):
        """Passing locomotive_id still works."""
        analytics = _mock_analytics(
            get_utilization={"total_readings": 50, "active_readings": 25, "avg_speed": 30.0, "max_speed": 50.0}
        )

        stats = await get_utilization_stats(analytics, locomotive_id="loco-1")
        assert stats["utilization_rate"] == 0.5
        assert stats["total_readings"] == 50
