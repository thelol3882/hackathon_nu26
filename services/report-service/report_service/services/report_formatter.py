"""Format report data as JSON, CSV rows, or PDF (base64)."""

from __future__ import annotations

import base64
import io
from pathlib import Path

from fpdf import FPDF

from shared.schemas.report import ReportFormat, ReportJobMessage

_FONTS_DIR = Path(__file__).resolve().parent.parent / "fonts"

# Font family name used throughout the PDF
_FONT = "DejaVu"


def format_report(data: dict, fmt: ReportFormat, job: ReportJobMessage) -> dict:
    """Format report data according to the requested format."""
    if fmt == ReportFormat.JSON:
        return data
    if fmt == ReportFormat.CSV:
        return _format_csv(data)
    if fmt == ReportFormat.PDF:
        return _format_pdf(data, job)
    return data


def _format_csv(data: dict) -> dict:
    """Flatten report data into rows for CSV export."""
    rows: list[dict] = [
        {
            "section": "sensor_stats",
            "sensor_type": stat["sensor_type"],
            "unit": stat["unit"],
            "avg": stat["avg"],
            "min": stat["min"],
            "max": stat["max"],
            "stddev": stat["stddev"],
            "samples": stat["samples"],
            "severity": "",
            "message": "",
            "timestamp": "",
        }
        for stat in data.get("sensor_stats", [])
    ]

    rows.extend(
        {
            "section": "alert",
            "sensor_type": alert["sensor_type"],
            "unit": "",
            "avg": "",
            "min": "",
            "max": "",
            "stddev": "",
            "samples": "",
            "severity": alert["severity"],
            "message": alert["message"],
            "timestamp": alert["timestamp"],
        }
        for alert in data.get("alerts", [])
    )

    return {
        "rows": rows,
        "summary": data.get("health_overview", {}),
    }


def _create_pdf() -> FPDF:
    """Create a PDF instance with DejaVu Sans (Unicode/Cyrillic support)."""
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)

    # Register DejaVu Sans — supports Latin, Cyrillic, Greek, and more
    pdf.add_font(_FONT, "", str(_FONTS_DIR / "DejaVuSans.ttf"))
    pdf.add_font(_FONT, "B", str(_FONTS_DIR / "DejaVuSans-Bold.ttf"))

    return pdf


def _format_pdf(data: dict, job: ReportJobMessage) -> dict:
    """Generate a PDF report and return as base64."""
    pdf = _create_pdf()
    pdf.add_page()

    _pdf_header(pdf, data)
    _pdf_health_overview(pdf, data.get("health_overview", {}))
    _pdf_sensor_stats(pdf, data.get("sensor_stats", []))
    _pdf_alerts(pdf, data.get("alert_summary", {}), data.get("alerts", []))
    _pdf_anomalies(pdf, data.get("anomalies", {}))

    buf = io.BytesIO()
    pdf.output(buf)
    return {"pdf_base64": base64.b64encode(buf.getvalue()).decode()}


def _pdf_header(pdf: FPDF, data: dict) -> None:
    pdf.set_font(_FONT, "B", 18)
    pdf.cell(0, 12, "Отчёт о состоянии локомотива", new_x="LMARGIN", new_y="NEXT", align="C")
    pdf.ln(4)

    pdf.set_font(_FONT, "", 10)
    loco_id = data.get("locomotive_id", "Весь парк")
    date_range = data.get("date_range", {})
    pdf.cell(0, 6, f"Локомотив: {loco_id}", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(
        0, 6, f"Период: {date_range.get('start', '')} — {date_range.get('end', '')}", new_x="LMARGIN", new_y="NEXT"
    )
    pdf.cell(0, 6, f"Сформирован: {data.get('generated_at', '')}", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(6)


def _pdf_health_overview(pdf: FPDF, overview: dict) -> None:
    _section_header(pdf, "Индекс здоровья")
    pdf.set_font(_FONT, "", 10)
    pdf.cell(0, 6, f"Расчётный балл: {overview.get('calculated_score', 'N/A')}", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 6, f"Средний балл: {overview.get('avg_score', 'N/A')}", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(
        0,
        6,
        f"Мин/Макс: {overview.get('min_score', 'N/A')} / {overview.get('max_score', 'N/A')}",
        new_x="LMARGIN",
        new_y="NEXT",
    )
    pdf.cell(0, 6, f"Категория: {overview.get('category', 'N/A')}", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 6, f"Штраф за износ: {overview.get('damage_penalty', 0.0)}", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)

    factors = overview.get("top_factors", [])
    if factors:
        _section_header(pdf, "Основные факторы влияния")
        pdf.set_font(_FONT, "", 9)
        _table_header(pdf, ["Датчик", "Значение", "Штраф", "Вклад %", "Отклонение %"])
        for f in factors[:10]:
            if isinstance(f, dict):
                _table_row(
                    pdf,
                    [
                        str(f.get("sensor_type", "")),
                        str(f.get("value", "")),
                        str(f.get("penalty", "")),
                        str(f.get("contribution_pct", "")),
                        str(f.get("deviation_pct", "")),
                    ],
                )
        pdf.ln(4)


def _pdf_sensor_stats(pdf: FPDF, stats: list[dict]) -> None:
    if not stats:
        return
    _section_header(pdf, "Статистика датчиков")
    pdf.set_font(_FONT, "", 9)
    _table_header(pdf, ["Датчик", "Ед.", "Сред.", "Мин.", "Макс.", "СКО", "Кол-во"])
    for s in stats:
        _table_row(
            pdf,
            [
                s["sensor_type"],
                s["unit"],
                str(s["avg"]),
                str(s["min"]),
                str(s["max"]),
                str(s["stddev"]),
                str(s["samples"]),
            ],
        )
    pdf.ln(4)


def _pdf_alerts(pdf: FPDF, alert_summary: dict, alerts: list[dict]) -> None:
    if alert_summary.get("total", 0) > 0:
        _section_header(pdf, "Сводка алертов")
        pdf.set_font(_FONT, "", 10)
        pdf.cell(0, 6, f"Всего алертов: {alert_summary['total']}", new_x="LMARGIN", new_y="NEXT")
        for sev, count in alert_summary.get("by_severity", {}).items():
            pdf.cell(0, 6, f"  {sev}: {count}", new_x="LMARGIN", new_y="NEXT")
        pdf.ln(2)

    if not alerts:
        return
    _section_header(pdf, f"История алертов (показано {min(len(alerts), 30)} из {len(alerts)})")
    pdf.set_font(_FONT, "", 8)
    _table_header(pdf, ["Время", "Датчик", "Уровень", "Значение", "Сообщение"])
    for a in alerts[:30]:
        msg = a["message"][:60] + "..." if len(a["message"]) > 60 else a["message"]
        _table_row(pdf, [a["timestamp"][:19], a["sensor_type"], a["severity"], str(a["value"]), msg])
    pdf.ln(4)


def _pdf_anomalies(pdf: FPDF, anomalies: dict) -> None:
    if not anomalies:
        return
    _section_header(pdf, "Обнаруженные аномалии")
    pdf.set_font(_FONT, "", 10)
    for sensor, items in anomalies.items():
        pdf.cell(0, 6, f"  {sensor}: {len(items)} аномалий", new_x="LMARGIN", new_y="NEXT")


def _section_header(pdf: FPDF, title: str) -> None:
    pdf.set_font(_FONT, "B", 12)
    pdf.cell(0, 8, title, new_x="LMARGIN", new_y="NEXT")
    pdf.line(pdf.l_margin, pdf.get_y(), pdf.w - pdf.r_margin, pdf.get_y())
    pdf.ln(2)


def _table_header(pdf: FPDF, headers: list[str]) -> None:
    col_w = (pdf.w - pdf.l_margin - pdf.r_margin) / len(headers)
    pdf.set_font(_FONT, "B", 8)
    for h in headers:
        pdf.cell(col_w, 6, h, border=1, align="C")
    pdf.ln()


def _table_row(pdf: FPDF, values: list[str]) -> None:
    col_w = (pdf.w - pdf.l_margin - pdf.r_margin) / len(values)
    pdf.set_font(_FONT, "", 8)
    for v in values:
        pdf.cell(col_w, 5, v, border=1)
    pdf.ln()
