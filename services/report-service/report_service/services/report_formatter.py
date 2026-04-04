"""Format report data as JSON, CSV rows, or PDF (base64)."""

from __future__ import annotations

import base64
import io
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fpdf import FPDF

from shared.schemas.report import ReportFormat, ReportJobMessage

_FONTS_DIR = Path(__file__).resolve().parent.parent / "fonts"

_FONT = "DejaVu"

_SENSOR_NAMES: dict[str, str] = {
    "diesel_rpm": "Обороты дизеля",
    "oil_pressure": "Давление масла",
    "coolant_temp": "Темп. охлаждения",
    "fuel_level": "Уровень топлива",
    "fuel_rate": "Расход топлива",
    "traction_motor_temp": "Темп. тяг. двигателя",
    "crankcase_pressure": "Давл. картера",
    "catenary_voltage": "Напряжение сети",
    "pantograph_current": "Ток пантографа",
    "transformer_temp": "Темп. трансформатора",
    "igbt_temp": "Темп. IGBT",
    "recuperation_current": "Ток рекуперации",
    "dc_link_voltage": "Напряжение DC-звена",
    "speed_actual": "Скорость факт.",
    "speed_target": "Скорость задан.",
    "brake_pipe_pressure": "Давл. торм. магистрали",
    "wheel_slip_ratio": "Коэфф. буксования",
}

_SEVERITY_NAMES: dict[str, str] = {
    "info": "информация",
    "warning": "предупреждение",
    "critical": "критический",
    "emergency": "аварийный",
}

_LOCO_TYPE_NAMES: dict[str, str] = {
    "TE33A": "ТЭ33А (дизель-электрический)",
    "KZ8A": "КЗ8А (электрический)",
}


def _sensor_ru(key: str) -> str:
    return _SENSOR_NAMES.get(key, key)


def _severity_ru(key: str) -> str:
    return _SEVERITY_NAMES.get(key, key)


def _loco_type_ru(key: str) -> str:
    return _LOCO_TYPE_NAMES.get(key, key)


def format_report(data: dict, fmt: ReportFormat, job: ReportJobMessage) -> dict:
    if fmt == ReportFormat.JSON:
        return data
    if fmt == ReportFormat.CSV:
        return _format_csv(data)
    if fmt == ReportFormat.PDF:
        return _format_pdf(data, job)
    return data


def _format_csv(data: dict) -> dict:
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


def _get_almaty_tz():
    """Resolve Asia/Almaty; fall back to fixed UTC+5 when tzdata is unavailable."""
    try:
        return ZoneInfo("Asia/Almaty")
    except ZoneInfoNotFoundError:
        return timezone(timedelta(hours=5), name="Asia/Almaty")


_TZ_ALMATY = _get_almaty_tz()


def _to_local(iso_str: str) -> str:
    if not iso_str:
        return ""
    try:
        dt = datetime.fromisoformat(iso_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        return dt.astimezone(_TZ_ALMATY).strftime("%Y-%m-%d %H:%M:%S")
    except (ValueError, TypeError):
        return iso_str[:19]


def _fmt(val, decimals: int = 2) -> str:
    if isinstance(val, float):
        return f"{val:.{decimals}f}"
    return str(val)


def _create_pdf() -> FPDF:
    """Create a landscape PDF instance with DejaVu Sans (Unicode/Cyrillic support)."""
    pdf = FPDF(orientation="L", format="A4")
    pdf.set_auto_page_break(auto=True, margin=15)

    pdf.add_font(_FONT, "", str(_FONTS_DIR / "DejaVuSans.ttf"))
    pdf.add_font(_FONT, "B", str(_FONTS_DIR / "DejaVuSans-Bold.ttf"))

    return pdf


def _format_pdf(data: dict, job: ReportJobMessage) -> dict:
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
    loco_type = data.get("locomotive_type", "")
    date_range = data.get("date_range", {})
    start = _to_local(date_range.get("start", ""))
    end = _to_local(date_range.get("end", ""))
    generated = _to_local(str(data.get("generated_at", "")))

    type_label = f" — {_loco_type_ru(loco_type)}" if loco_type else ""
    pdf.cell(0, 6, f"Локомотив: {loco_id}{type_label}", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 6, f"Период: {start} — {end} (Алматы)", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 6, f"Сформирован: {generated}", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(6)


def _pdf_health_overview(pdf: FPDF, overview: dict) -> None:
    _section_header(pdf, "Индекс здоровья")
    pdf.set_font(_FONT, "", 10)
    pdf.cell(0, 6, f"Расчётный балл: {_fmt(overview.get('calculated_score', 'N/A'))}", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 6, f"Средний балл: {_fmt(overview.get('avg_score', 'N/A'))}", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(
        0,
        6,
        f"Мин/Макс: {_fmt(overview.get('min_score', 'N/A'))} / {_fmt(overview.get('max_score', 'N/A'))}",
        new_x="LMARGIN",
        new_y="NEXT",
    )
    pdf.cell(0, 6, f"Категория: {overview.get('category', 'N/A')}", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 6, f"Штраф за износ: {_fmt(overview.get('damage_penalty', 0.0), 4)}", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)

    factors = overview.get("top_factors", [])
    if factors:
        _section_header(pdf, "Основные факторы влияния")
        cols = [("Датчик", 55), ("Значение", 30), ("Ед.", 18), ("Штраф", 22), ("Вклад %", 22), ("Откл. %", 22)]
        _table_header(pdf, cols)
        for f in factors[:10]:
            if isinstance(f, dict):
                _table_row(
                    pdf,
                    cols,
                    [
                        _sensor_ru(str(f.get("sensor_type", ""))),
                        _fmt(f.get("value", 0)),
                        str(f.get("unit", "")),
                        _fmt(f.get("penalty", 0), 4),
                        _fmt(f.get("contribution_pct", 0), 1),
                        _fmt(f.get("deviation_pct", 0), 1),
                    ],
                )
        pdf.ln(4)


def _pdf_sensor_stats(pdf: FPDF, stats: list[dict]) -> None:
    if not stats:
        return
    _section_header(pdf, "Статистика датчиков")
    cols = [("Датчик", 55), ("Ед.", 18), ("Среднее", 28), ("Мин.", 28), ("Макс.", 28), ("СКО", 25), ("Кол-во", 20)]
    _table_header(pdf, cols)
    for s in stats:
        _table_row(
            pdf,
            cols,
            [
                _sensor_ru(s["sensor_type"]),
                s["unit"],
                _fmt(s["avg"]),
                _fmt(s["min"]),
                _fmt(s["max"]),
                _fmt(s["stddev"], 4),
                str(s["samples"]),
            ],
        )
    pdf.ln(4)


def _pdf_alerts(pdf: FPDF, alert_summary: dict, alerts: list[dict]) -> None:
    if alert_summary.get("total", 0) > 0:
        _section_header(pdf, "Сводка предупреждений")
        pdf.set_font(_FONT, "", 10)
        pdf.cell(0, 6, f"Всего предупреждений: {alert_summary['total']}", new_x="LMARGIN", new_y="NEXT")
        for sev, count in alert_summary.get("by_severity", {}).items():
            pdf.cell(0, 6, f"  {_severity_ru(sev)}: {count}", new_x="LMARGIN", new_y="NEXT")
        pdf.ln(2)

    if not alerts:
        return
    shown = min(len(alerts), 30)
    _section_header(pdf, f"История предупреждений (показано {shown} из {len(alerts)})")
    cols = [("Время", 40), ("Датчик", 44), ("Уровень", 28), ("Значение", 20), ("Описание", 135)]
    _table_header(pdf, cols)
    for a in alerts[:30]:
        _table_row(
            pdf,
            cols,
            [
                _to_local(a["timestamp"]),
                _sensor_ru(a["sensor_type"]),
                _severity_ru(a["severity"]),
                _fmt(a["value"]),
                a["message"],
            ],
        )
    pdf.ln(4)


def _pdf_anomalies(pdf: FPDF, anomalies: dict) -> None:
    if not anomalies:
        return
    _section_header(pdf, "Обнаруженные аномалии")
    pdf.set_font(_FONT, "", 10)
    for sensor, items in anomalies.items():
        pdf.cell(0, 6, f"  {_sensor_ru(sensor)}: {len(items)} аномалий", new_x="LMARGIN", new_y="NEXT")


def _section_header(pdf: FPDF, title: str) -> None:
    # Ensure section header + at least a few rows fit on current page
    if pdf.get_y() > pdf.h - 40:
        pdf.add_page()
    pdf.set_font(_FONT, "B", 12)
    pdf.cell(0, 8, title, new_x="LMARGIN", new_y="NEXT")
    pdf.line(pdf.l_margin, pdf.get_y(), pdf.w - pdf.r_margin, pdf.get_y())
    pdf.ln(2)


def _table_header(pdf: FPDF, cols: list[tuple[str, int]]) -> None:
    pdf.set_font(_FONT, "B", 8)
    for name, w in cols:
        pdf.cell(w, 6, name, border=1, align="C")
    pdf.ln()


def _table_row(pdf: FPDF, cols: list[tuple[str, int]], values: list[str]) -> None:
    # Prevent row from being split across pages
    if pdf.get_y() + 6 > pdf.h - pdf.b_margin:
        pdf.add_page()
        _table_header(pdf, cols)  # repeat header on new page
    pdf.set_font(_FONT, "", 8)
    for i, ((_, w), v) in enumerate(zip(cols, values, strict=False)):
        is_last = i == len(values) - 1
        # Last column gets more space per char (description/message fields)
        max_chars = int(w * 0.7) if is_last else int(w / 2)
        display = v if len(v) <= max_chars else v[: max_chars - 1] + "…"
        pdf.cell(w, 5, display, border=1)
    pdf.ln()
