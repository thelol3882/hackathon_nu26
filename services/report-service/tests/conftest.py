"""Shared fixtures for report-service tests."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from shared.schemas.report import DateRange, ReportFormat, ReportJobMessage


@pytest.fixture
def mock_session() -> MagicMock:
    """AsyncSession mock with async execute, commit, and refresh."""
    session = MagicMock(spec=AsyncSession)
    session.execute = AsyncMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    return session


@pytest.fixture
def sample_job() -> ReportJobMessage:
    """Factory-style fixture returning a default ReportJobMessage."""
    return ReportJobMessage(
        report_id=uuid4(),
        locomotive_id="00000000-0000-0000-0000-000000000001",
        report_type="health_summary",
        format=ReportFormat.JSON,
        date_range=DateRange(
            start=datetime(2026, 1, 1, tzinfo=UTC),
            end=datetime(2026, 1, 2, tzinfo=UTC),
        ),
        requested_at=datetime.now(UTC),
    )


@pytest.fixture
def sample_report_data() -> dict:
    """Rich report data dict suitable for formatter and PDF tests."""
    return {
        "locomotive_id": "00000000-0000-0000-0000-000000000001",
        "report_type": "health_summary",
        "date_range": {
            "start": "2026-01-01T00:00:00+00:00",
            "end": "2026-01-02T00:00:00+00:00",
        },
        "health_overview": {
            "calculated_score": 85.0,
            "avg_score": 82.5,
            "min_score": 75.0,
            "max_score": 90.0,
            "category": "Норма",
            "damage_penalty": 0.002,
            "top_factors": [],
            "trend": [],
        },
        "sensor_stats": [
            {
                "sensor_type": "coolant_temp",
                "unit": "°C",
                "avg": 82.0,
                "min": 70.0,
                "max": 95.0,
                "stddev": 3.5,
                "samples": 1000,
            },
            {
                "sensor_type": "oil_pressure",
                "unit": "bar",
                "avg": 3.5,
                "min": 1.8,
                "max": 4.9,
                "stddev": 0.5,
                "samples": 1000,
            },
        ],
        "alerts": [
            {
                "sensor_type": "coolant_temp",
                "severity": "warning",
                "value": 94.5,
                "threshold_min": 70.0,
                "threshold_max": 95.0,
                "message": "Coolant temperature approaching upper threshold",
                "timestamp": "2026-01-01T12:00:00+00:00",
                "acknowledged": False,
            },
            {
                "sensor_type": "oil_pressure",
                "severity": "critical",
                "value": 1.6,
                "threshold_min": 1.5,
                "threshold_max": 5.0,
                "message": "Oil pressure critically low",
                "timestamp": "2026-01-01T14:00:00+00:00",
                "acknowledged": False,
            },
        ],
        "alert_summary": {"total": 2, "by_severity": {"warning": 1, "critical": 1}},
        "anomalies": {"coolant_temp": [{"index": 42, "value": 99.5, "time": "2026-01-01T06:00:00+00:00"}]},
        "components": [],
        "generated_at": "2026-01-01T18:00:00+00:00",
    }
