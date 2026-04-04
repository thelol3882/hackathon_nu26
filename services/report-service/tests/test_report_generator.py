"""Tests for report_service.services.report_generator."""

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

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


def _make_sensor_row(sensor_type="coolant_temp", unit="°C", avg=82.0, min_v=70.0, max_v=95.0, stddev=3.5, count=100):
    return SimpleNamespace(
        sensor_type=sensor_type,
        unit=unit,
        avg_val=avg,
        min_val=min_v,
        max_val=max_v,
        stddev_val=stddev,
        sample_count=count,
    )


def _make_health_trend_row(bucket_time, avg=85.0, min_s=80.0, max_s=90.0):
    return SimpleNamespace(
        bucket=bucket_time,
        avg_score=avg,
        min_score=min_s,
        max_score=max_s,
    )


def _make_agg_row(avg=85.0, min_s=75.0, max_s=92.0):
    return SimpleNamespace(avg_score=avg, min_score=min_s, max_score=max_s)


def _make_latest_row(score=85.0, category="Норма", top_factors=None, damage_penalty=0.002):
    return SimpleNamespace(
        score=score,
        category=category,
        top_factors=top_factors or [],
        damage_penalty=damage_penalty,
    )


def _make_alert_row(
    sensor_type="coolant_temp",
    severity="warning",
    value=94.5,
    threshold_min=70.0,
    threshold_max=95.0,
    message="High temp",
    ts=None,
    acknowledged=False,
):
    return SimpleNamespace(
        sensor_type=sensor_type,
        severity=severity,
        value=value,
        threshold_min=threshold_min,
        threshold_max=threshold_max,
        message=message,
        timestamp=ts or datetime(2026, 1, 1, 12, 0, tzinfo=UTC),
        acknowledged=acknowledged,
    )


def _make_telemetry_row(sensor_type="coolant_temp", filtered_value=82.0, time=None):
    return SimpleNamespace(
        sensor_type=sensor_type,
        filtered_value=filtered_value,
        time=time or datetime(2026, 1, 1, 6, 0, tzinfo=UTC),
    )


def _build_mock_session(
    sensor_rows=None,
    trend_rows=None,
    agg_row=None,
    latest_row=None,
    alert_rows=None,
    telemetry_rows=None,
    has_locomotive_id: bool = True,
):
    """Build an AsyncSession mock with side_effect for sequential execute calls.

    Call order in generate_report_data:
      0. _query_locomotive_type -> fetchone
      1. _query_sensor_stats  -> fetchall
      2. _query_health_trend  -> fetchall
      3. _query_latest_health (agg) -> fetchone
      4. _query_latest_health (latest) -> fetchone
      5. _query_alerts         -> fetchall
      6. _detect_anomalies     -> fetchall
    """
    results = []

    # 0 - locomotive_type (only when locomotive_id is provided)
    if has_locomotive_id:
        r0 = MagicMock()
        r0.fetchone.return_value = SimpleNamespace(locomotive_type="TE33A")
        results.append(r0)

    # 1 - sensor_stats
    r1 = MagicMock()
    r1.fetchall.return_value = sensor_rows or []
    results.append(r1)

    # 2 - health_trend
    r2 = MagicMock()
    r2.fetchall.return_value = trend_rows or []
    results.append(r2)

    # 3 - latest_health agg
    r3 = MagicMock()
    r3.fetchone.return_value = agg_row
    results.append(r3)

    # 4 - latest_health latest
    r4 = MagicMock()
    r4.fetchone.return_value = latest_row
    results.append(r4)

    # 5 - alerts
    r5 = MagicMock()
    r5.fetchall.return_value = alert_rows or []
    results.append(r5)

    # 6 - anomalies
    r6 = MagicMock()
    r6.fetchall.return_value = telemetry_rows or []
    results.append(r6)

    session = MagicMock(spec=AsyncSession)
    session.execute = AsyncMock(side_effect=results)
    return session


# ── Happy-path tests ──────────────────────────────────────────────────────────


class TestGenerateReportData:
    @pytest.mark.asyncio
    async def test_generate_complete(self):
        """Full generation with data in all sections produces expected keys."""
        session = _build_mock_session(
            sensor_rows=[_make_sensor_row()],
            trend_rows=[_make_health_trend_row(datetime(2026, 1, 1, 0, 0, tzinfo=UTC))],
            agg_row=_make_agg_row(),
            latest_row=_make_latest_row(),
            alert_rows=[_make_alert_row()],
            telemetry_rows=[_make_telemetry_row()],
        )
        result = await generate_report_data(session, _make_job())

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
        session = _build_mock_session(agg_row=_make_agg_row(), latest_row=_make_latest_row())
        result = await generate_report_data(session, _make_job(locomotive_id=loco_id))
        assert result["locomotive_id"] == loco_id

    @pytest.mark.asyncio
    async def test_without_locomotive_id(self):
        """When locomotive_id is None, result locomotive_id is None."""
        session = _build_mock_session(agg_row=_make_agg_row(), latest_row=_make_latest_row(), has_locomotive_id=False)
        result = await generate_report_data(session, _make_job(locomotive_id=None))
        assert result["locomotive_id"] is None

    @pytest.mark.asyncio
    async def test_alert_summary_counts_by_severity(self):
        """Alert summary groups by severity correctly."""
        alerts = [
            _make_alert_row(severity="warning"),
            _make_alert_row(severity="warning"),
            _make_alert_row(severity="critical"),
        ]
        session = _build_mock_session(
            alert_rows=alerts,
            agg_row=_make_agg_row(),
            latest_row=_make_latest_row(),
        )
        result = await generate_report_data(session, _make_job())
        summary = result["alert_summary"]
        assert summary["total"] == 3
        assert summary["by_severity"]["warning"] == 2
        assert summary["by_severity"]["critical"] == 1

    @pytest.mark.asyncio
    async def test_no_telemetry(self):
        """All queries return empty -> sections are empty lists/dicts."""
        session = _build_mock_session(agg_row=None, latest_row=None)
        result = await generate_report_data(session, _make_job())
        assert result["sensor_stats"] == []
        assert result["alerts"] == []
        assert result["anomalies"] == {}

    @pytest.mark.asyncio
    async def test_generated_at_present(self):
        """generated_at is a recent ISO datetime string."""
        session = _build_mock_session(agg_row=_make_agg_row(), latest_row=_make_latest_row())
        before = datetime.now(UTC)
        result = await generate_report_data(session, _make_job())
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
