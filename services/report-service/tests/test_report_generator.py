"""Tests for report_service.services.report_generator."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from report_service.services.report_generator import _summarize_alerts, generate_report_data
from shared.schemas.report import DateRange, ReportFormat, ReportJobMessage

# ── Helpers ───────────────────────────────────────────────────────────────────


def _make_job(locomotive_id: str | None = "00000000-0000-0000-0000-000000000001") -> ReportJobMessage:
    return ReportJobMessage(
        report_id=uuid4(),
        locomotive_id=locomotive_id,
        report_type="health_summary",
        format=ReportFormat.JSON,
        date_range=DateRange(
            start=datetime(2026, 1, 1, tzinfo=UTC),
            end=datetime(2026, 1, 2, tzinfo=UTC),
        ),
        requested_at=datetime.now(UTC),
    )


def _make_sensor_stat(sensor_type="coolant_temp", unit="°C", avg=82.0, min_v=70.0, max_v=95.0, stddev=3.5, count=100):
    return {
        "sensor_type": sensor_type,
        "unit": unit,
        "avg": avg,
        "min": min_v,
        "max": max_v,
        "stddev": stddev,
        "samples": count,
    }


def _make_health_trend_point(t=None, avg=85.0, min_s=80.0, max_s=90.0):
    return {
        "time": (t or datetime(2026, 1, 1, 0, 0, tzinfo=UTC)).isoformat(),
        "avg_score": avg,
        "min_score": min_s,
        "max_score": max_s,
    }


def _make_latest_health(avg=85.0, min_s=75.0, max_s=92.0, category="Норма", damage_penalty=0.002):
    return {
        "avg_score": avg,
        "min_score": min_s,
        "max_score": max_s,
        "category": category,
        "damage_penalty": damage_penalty,
        "top_factors": [],
    }


def _make_alert(sensor_type="coolant_temp", severity="warning", value=94.5):
    return {
        "sensor_type": sensor_type,
        "severity": severity,
        "value": value,
        "threshold_min": 70.0,
        "threshold_max": 95.0,
        "message": "High temp",
        "timestamp": datetime(2026, 1, 1, 12, 0, tzinfo=UTC).isoformat(),
        "acknowledged": False,
    }


def _make_anomaly_row(sensor_type="coolant_temp", filtered_value=82.0, time=None):
    return {
        "sensor_type": sensor_type,
        "filtered_value": filtered_value,
        "time": (time or datetime(2026, 1, 1, 6, 0, tzinfo=UTC)).isoformat(),
    }


def _build_mock_analytics(
    sensor_stats=None,
    locomotive_type="TE33A",
    health_trend=None,
    latest_health=None,
    alerts=None,
    anomaly_rows=None,
    fleet_health=None,
    fleet_alerts=None,
    worst_locos=None,
):
    """Build a mock AnalyticsClient with pre-configured return values."""
    client = AsyncMock()
    client.get_sensor_stats = AsyncMock(return_value={"stats": sensor_stats or [], "locomotive_type": locomotive_type})
    client.get_health_trend = AsyncMock(return_value=health_trend or [])
    client.get_latest_health = AsyncMock(return_value=latest_health or {})
    client.get_report_alerts = AsyncMock(return_value=alerts or [])
    client.get_raw_for_anomalies = AsyncMock(return_value=anomaly_rows or [])
    client.get_fleet_health = AsyncMock(return_value=fleet_health or [])
    client.get_fleet_alert_summary = AsyncMock(return_value=fleet_alerts or {"total": 0, "by_severity": {}})
    client.get_worst_locomotives = AsyncMock(return_value=worst_locos or [])
    return client


# ── Happy-path tests ──────────────────────────────────────────────────────────


class TestGenerateReportData:
    @pytest.mark.asyncio
    async def test_generate_complete(self):
        """Full generation with data in all sections produces expected keys."""
        analytics = _build_mock_analytics(
            sensor_stats=[_make_sensor_stat()],
            health_trend=[_make_health_trend_point()],
            latest_health=_make_latest_health(),
            alerts=[_make_alert()],
            anomaly_rows=[_make_anomaly_row()],
        )
        result = await generate_report_data(analytics, _make_job())

        expected_keys = {
            "locomotive_id",
            "report_type",
            "date_range",
            "health_overview",
            "sensor_stats",
            "alerts",
            "alert_summary",
            "anomalies",
            "components",
            "generated_at",
        }
        assert expected_keys.issubset(result.keys())
        assert len(result["sensor_stats"]) == 1
        assert len(result["alerts"]) == 1

    @pytest.mark.asyncio
    async def test_with_locomotive_id(self):
        """When locomotive_id is set, the result contains it as a string."""
        loco_id = "00000000-0000-0000-0000-000000000001"
        analytics = _build_mock_analytics(latest_health=_make_latest_health())
        result = await generate_report_data(analytics, _make_job(locomotive_id=loco_id))
        assert result["locomotive_id"] == loco_id

    @pytest.mark.asyncio
    async def test_without_locomotive_id(self):
        """When locomotive_id is None, result locomotive_id is None."""
        analytics = _build_mock_analytics(
            fleet_health=[
                {
                    "avg_score": 80,
                    "min_score": 60,
                    "max_score": 95,
                    "locomotive_count": 10,
                    "healthy_count": 7,
                    "warning_count": 2,
                    "critical_count": 1,
                }
            ]
        )
        result = await generate_report_data(analytics, _make_job(locomotive_id=None))
        assert result["locomotive_id"] is None

    @pytest.mark.asyncio
    async def test_alert_summary_counts_by_severity(self):
        """Alert summary groups by severity correctly."""
        alerts = [
            _make_alert(severity="warning"),
            _make_alert(severity="warning"),
            _make_alert(severity="critical"),
        ]
        analytics = _build_mock_analytics(
            alerts=alerts,
            latest_health=_make_latest_health(),
        )
        result = await generate_report_data(analytics, _make_job())
        summary = result["alert_summary"]
        assert summary["total"] == 3
        assert summary["by_severity"]["warning"] == 2
        assert summary["by_severity"]["critical"] == 1

    @pytest.mark.asyncio
    async def test_no_telemetry(self):
        """All queries return empty -> sections are empty lists/dicts."""
        analytics = _build_mock_analytics()
        result = await generate_report_data(analytics, _make_job())
        assert result["sensor_stats"] == []
        assert result["alerts"] == []
        assert result["anomalies"] == {}

    @pytest.mark.asyncio
    async def test_generated_at_present(self):
        """generated_at is a recent ISO datetime string."""
        analytics = _build_mock_analytics(latest_health=_make_latest_health())
        before = datetime.now(UTC)
        result = await generate_report_data(analytics, _make_job())
        generated = datetime.fromisoformat(result["generated_at"])
        assert generated >= before


# ── _summarize_alerts unit tests ──────────────────────────────────────────────


class TestSummarizeAlerts:
    def test_empty(self):
        assert _summarize_alerts([]) == {"total": 0, "by_severity": {}}

    def test_mixed_severities(self):
        alerts = [
            {"severity": "warning"},
            {"severity": "critical"},
            {"severity": "warning"},
        ]
        result = _summarize_alerts(alerts)
        assert result == {"total": 3, "by_severity": {"warning": 2, "critical": 1}}
