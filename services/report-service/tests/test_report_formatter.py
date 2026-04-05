"""Tests for report_service.services.report_formatter."""

import base64

from report_service.services.report_formatter import _to_local, format_report
from shared.schemas.report import ReportFormat

# ── JSON format tests ─────────────────────────────────────────────────────────


class TestFormatJson:
    def test_json_returns_data_unchanged(self, sample_report_data, sample_job):
        result = format_report(sample_report_data, ReportFormat.JSON, sample_job)
        # _format_json enriches with human-readable names, so check key data is preserved
        for key in sample_report_data:
            assert key in result


# ── CSV format tests ──────────────────────────────────────────────────────────


class TestFormatCsv:
    def test_csv_has_rows_and_summary(self, sample_report_data, sample_job):
        result = format_report(sample_report_data, ReportFormat.CSV, sample_job)
        assert "rows" in result
        assert "summary" in result

    def test_csv_sensor_stats_rows(self, sample_report_data, sample_job):
        result = format_report(sample_report_data, ReportFormat.CSV, sample_job)
        sensor_rows = [r for r in result["rows"] if r["section"] == "sensor_stats"]
        assert len(sensor_rows) == len(sample_report_data["sensor_stats"])
        for row in sensor_rows:
            assert "sensor_type" in row
            assert "avg" in row

    def test_csv_alert_rows(self, sample_report_data, sample_job):
        result = format_report(sample_report_data, ReportFormat.CSV, sample_job)
        alert_rows = [r for r in result["rows"] if r["section"] == "alert"]
        assert len(alert_rows) == len(sample_report_data["alerts"])
        for row in alert_rows:
            assert row["severity"] != ""
            assert row["message"] != ""

    def test_csv_empty_data(self, sample_job):
        result = format_report({}, ReportFormat.CSV, sample_job)
        assert result["rows"] == []
        assert result["summary"] == {}


# ── PDF format tests ──────────────────────────────────────────────────────────


class TestFormatPdf:
    def test_to_local_converts_utc_to_almaty(self):
        assert _to_local("2026-01-01T00:00:00+00:00") == "2026-01-01 05:00:00"

    def test_pdf_returns_base64(self, sample_report_data, sample_job):
        result = format_report(sample_report_data, ReportFormat.PDF, sample_job)
        assert "pdf_base64" in result
        assert isinstance(result["pdf_base64"], str)

    def test_pdf_valid_bytes(self, sample_report_data, sample_job, tmp_path):
        result = format_report(sample_report_data, ReportFormat.PDF, sample_job)
        pdf_bytes = base64.b64decode(result["pdf_base64"])
        pdf_file = tmp_path / "report.pdf"
        pdf_file.write_bytes(pdf_bytes)
        assert pdf_bytes[:5] == b"%PDF-"

    def test_pdf_empty_data(self, sample_job):
        """Empty data dict should still produce a valid PDF without crashing."""
        result = format_report({}, ReportFormat.PDF, sample_job)
        assert "pdf_base64" in result
        pdf_bytes = base64.b64decode(result["pdf_base64"])
        assert pdf_bytes[:5] == b"%PDF-"

    def test_pdf_long_alert_no_crash(self, sample_job):
        """Alert message >60 chars is truncated in PDF, no exception."""
        data = {
            "alerts": [
                {
                    "sensor_type": "coolant_temp",
                    "severity": "warning",
                    "value": 94.5,
                    "message": "A" * 200,  # very long message
                    "timestamp": "2026-01-01T12:00:00+00:00",
                }
            ],
            "alert_summary": {"total": 1, "by_severity": {"warning": 1}},
        }
        result = format_report(data, ReportFormat.PDF, sample_job)
        assert "pdf_base64" in result


# ── Unknown format test ───────────────────────────────────────────────────────


class TestFormatUnknown:
    def test_unknown_format_returns_data(self, sample_report_data, sample_job):
        """A format value not matching JSON/CSV/PDF falls through and returns data."""
        # ReportFormat is a StrEnum so we can't easily pass a bad value,
        # but the function has a final `return data` fallback.
        # We test by calling the function with a string that isn't a ReportFormat member.
        result = format_report(sample_report_data, "xml", sample_job)
        assert result is sample_report_data
