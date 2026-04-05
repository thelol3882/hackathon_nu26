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

# Font family name used throughout the PDF
_FONT = "DejaVu"

_CLR_PRIMARY = (3, 136, 230)
_CLR_PRIMARY_DARK = (9, 81, 115)
_CLR_GOLD = (254, 198, 4)
_CLR_WHITE = (255, 255, 255)
_CLR_LIGHT_BG = (245, 247, 250)
_CLR_DARK_TEXT = (26, 27, 30)
_CLR_SECONDARY_TEXT = (73, 80, 87)
_CLR_BORDER = (222, 226, 230)
_CLR_TABLE_HEADER = (15, 32, 53)
_CLR_TABLE_STRIPE = (240, 243, 247)

_CLR_HEALTHY = (34, 197, 94)
_CLR_WARNING = (245, 158, 11)
_CLR_CRITICAL = (239, 68, 68)

_SEVERITY_COLORS: dict[str, tuple[int, int, int]] = {
    "info": (3, 136, 230),
    "warning": (245, 158, 11),
    "critical": (239, 68, 68),
    "emergency": (127, 29, 29),
}

# Localized display names for PDF/JSON output (Russian for KTZ reports)
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
    """Format report data according to the requested format."""
    if fmt == ReportFormat.JSON:
        return _format_json(data)
    if fmt == ReportFormat.CSV:
        return _format_csv(data)
    if fmt == ReportFormat.PDF:
        return _format_pdf(data, job)
    return data


def _format_json(data: dict) -> dict:
    """Clean up JSON output — translate sensor names for readability."""
    result = dict(data)
    for stat in result.get("sensor_stats", []):
        stat["sensor_name"] = _sensor_ru(stat.get("sensor_type", ""))
    for alert in result.get("alerts", []):
        alert["sensor_name"] = _sensor_ru(alert.get("sensor_type", ""))
        alert["severity_name"] = _severity_ru(alert.get("severity", ""))
    overview = result.get("health_overview", {})
    for loco in overview.get("worst_locomotives", []):
        loco["locomotive_type_name"] = _loco_type_ru(loco.get("locomotive_type", ""))
    return result


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
            "locomotive_id": "",
            "avg_score": "",
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
            "locomotive_id": "",
            "avg_score": "",
        }
        for alert in data.get("alerts", [])
    )

    overview = data.get("health_overview", {})
    worst = overview.get("worst_locomotives", [])
    rows.extend(
        {
            "section": "worst_locomotive",
            "sensor_type": "",
            "unit": "",
            "avg": "",
            "min": loco.get("min_score", ""),
            "max": loco.get("max_score", ""),
            "stddev": "",
            "samples": "",
            "severity": "",
            "message": loco.get("locomotive_type", ""),
            "timestamp": "",
            "locomotive_id": loco.get("locomotive_id", ""),
            "avg_score": loco.get("avg_score", ""),
        }
        for loco in worst
    )

    summary = dict(overview)
    fleet_stats = overview.get("fleet_stats")
    if fleet_stats:
        summary["fleet_total"] = fleet_stats.get("total_locomotives", 0)
        summary["fleet_healthy"] = fleet_stats.get("healthy_count", 0)
        summary["fleet_warning"] = fleet_stats.get("warning_count", 0)
        summary["fleet_critical"] = fleet_stats.get("critical_count", 0)

    return {
        "rows": rows,
        "summary": summary,
    }


def _get_almaty_tz():
    """Resolve Asia/Almaty; fall back to fixed UTC+5 when tzdata is unavailable."""
    try:
        return ZoneInfo("Asia/Almaty")
    except ZoneInfoNotFoundError:
        return timezone(timedelta(hours=5), name="Asia/Almaty")


_TZ_ALMATY = _get_almaty_tz()


def _to_local(iso_str: str) -> str:
    """Convert ISO timestamp string to Asia/Almaty local time for display."""
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
    """Round numeric values for display."""
    if isinstance(val, float):
        return f"{val:.{decimals}f}"
    return str(val)


def _create_pdf() -> FPDF:
    """Create a landscape PDF instance with DejaVu Sans (Unicode/Cyrillic support)."""
    pdf = FPDF(orientation="L", format="A4")
    pdf.set_auto_page_break(auto=True, margin=18)

    pdf.add_font(_FONT, "", str(_FONTS_DIR / "DejaVuSans.ttf"))
    pdf.add_font(_FONT, "B", str(_FONTS_DIR / "DejaVuSans-Bold.ttf"))

    return pdf


def _set_color(pdf: FPDF, color: tuple[int, int, int]) -> None:
    """Set text color."""
    pdf.set_text_color(*color)


def _set_draw(pdf: FPDF, color: tuple[int, int, int]) -> None:
    """Set draw color."""
    pdf.set_draw_color(*color)


def _set_fill(pdf: FPDF, color: tuple[int, int, int]) -> None:
    """Set fill color."""
    pdf.set_fill_color(*color)


def _health_color(score) -> tuple[int, int, int]:
    """Get color based on health score."""
    if not isinstance(score, (int, float)):
        return _CLR_SECONDARY_TEXT
    if score >= 80:
        return _CLR_HEALTHY
    if score >= 50:
        return _CLR_WARNING
    return _CLR_CRITICAL


def _format_pdf(data: dict, job: ReportJobMessage) -> dict:
    """Generate a beautiful PDF report and return as base64."""
    pdf = _create_pdf()
    pdf.add_page()

    _pdf_cover_header(pdf, data)
    _pdf_health_overview(pdf, data.get("health_overview", {}))

    fleet_stats = data.get("health_overview", {}).get("fleet_stats")
    if fleet_stats:
        _pdf_fleet_stats(pdf, fleet_stats)
        worst = data.get("health_overview", {}).get("worst_locomotives", [])
        if worst:
            _pdf_worst_locomotives(pdf, worst)
    else:
        _pdf_top_factors(pdf, data.get("health_overview", {}))

    _pdf_sensor_stats(pdf, data.get("sensor_stats", []))
    _pdf_alerts(pdf, data.get("alert_summary", {}), data.get("alerts", []))
    _pdf_anomalies(pdf, data.get("anomalies", {}))
    _pdf_footer(pdf)

    buf = io.BytesIO()
    pdf.output(buf)
    return {"pdf_base64": base64.b64encode(buf.getvalue()).decode()}


def _pdf_cover_header(pdf: FPDF, data: dict) -> None:
    """Render branded header with KTZ colors."""
    _set_fill(pdf, _CLR_PRIMARY)
    pdf.rect(pdf.l_margin, pdf.get_y(), pdf.w - pdf.l_margin - pdf.r_margin, 28, "F")

    pdf.set_font(_FONT, "B", 20)
    _set_color(pdf, _CLR_WHITE)
    pdf.set_y(pdf.get_y() + 3)
    pdf.cell(0, 12, "Отчёт о состоянии локомотива", new_x="LMARGIN", new_y="NEXT", align="C")

    pdf.set_font(_FONT, "", 10)
    pdf.cell(0, 8, "Система мониторинга КТЖ — Цифровой двойник", new_x="LMARGIN", new_y="NEXT", align="C")

    pdf.ln(6)

    _set_color(pdf, _CLR_DARK_TEXT)
    pdf.set_font(_FONT, "", 10)

    loco_id = data.get("locomotive_id", "Весь парк")
    loco_type = data.get("locomotive_type", "")
    date_range = data.get("date_range", {})
    start = _to_local(date_range.get("start", ""))
    end = _to_local(date_range.get("end", ""))
    generated = _to_local(str(data.get("generated_at", "")))

    col_w = (pdf.w - pdf.l_margin - pdf.r_margin) / 2
    y = pdf.get_y()

    _set_fill(pdf, _CLR_LIGHT_BG)
    pdf.rect(pdf.l_margin, y, pdf.w - pdf.l_margin - pdf.r_margin, 22, "F")
    pdf.set_y(y + 2)

    pdf.set_font(_FONT, "B", 9)
    _set_color(pdf, _CLR_SECONDARY_TEXT)
    pdf.cell(col_w, 5, "ЛОКОМОТИВ", new_x="LEFT", new_y="NEXT")
    pdf.set_font(_FONT, "", 10)
    _set_color(pdf, _CLR_DARK_TEXT)
    type_label = f"  ({_loco_type_ru(loco_type)})" if loco_type else ""
    pdf.cell(col_w, 6, f"  {loco_id}{type_label}", new_x="LEFT", new_y="NEXT")

    pdf.set_xy(pdf.l_margin + col_w, y + 2)
    pdf.set_font(_FONT, "B", 9)
    _set_color(pdf, _CLR_SECONDARY_TEXT)
    pdf.cell(col_w, 5, "ПЕРИОД", new_x="LEFT", new_y="NEXT")
    pdf.set_x(pdf.l_margin + col_w)
    pdf.set_font(_FONT, "", 10)
    _set_color(pdf, _CLR_DARK_TEXT)
    pdf.cell(col_w, 6, f"  {start}  —  {end}", new_x="LMARGIN", new_y="NEXT")

    pdf.set_y(y + 24)
    pdf.set_font(_FONT, "", 8)
    _set_color(pdf, _CLR_SECONDARY_TEXT)
    pdf.cell(0, 5, f"Сформирован: {generated} (Алматы)", new_x="LMARGIN", new_y="NEXT", align="R")
    pdf.ln(4)


def _pdf_health_overview(pdf: FPDF, overview: dict) -> None:
    """Render health index as a prominent visual block."""
    _section_header(pdf, "Индекс здоровья", _CLR_PRIMARY)

    score = overview.get("calculated_score")
    avg_score = overview.get("avg_score")
    min_score = overview.get("min_score")
    max_score = overview.get("max_score")
    category = overview.get("category", "N/A")
    damage = overview.get("damage_penalty", 0.0)

    y_start = pdf.get_y()
    color = _health_color(score)

    _set_fill(pdf, color)
    box_x = pdf.l_margin + 5
    pdf.rect(box_x, y_start, 50, 30, "F")
    pdf.set_font(_FONT, "B", 28)
    _set_color(pdf, _CLR_WHITE)
    pdf.set_xy(box_x, y_start + 2)
    pdf.cell(50, 18, _fmt(score) if isinstance(score, (int, float)) else "N/A", align="C")
    pdf.set_font(_FONT, "", 10)
    pdf.set_xy(box_x, y_start + 19)
    pdf.cell(50, 8, category, align="C")

    stats_x = box_x + 60
    pdf.set_xy(stats_x, y_start + 2)
    _set_color(pdf, _CLR_DARK_TEXT)
    pdf.set_font(_FONT, "", 10)

    bar_y = y_start + 4
    bar_w = 100
    bar_h = 6
    _set_fill(pdf, _CLR_BORDER)
    pdf.rect(stats_x, bar_y, bar_w, bar_h, "F")
    if isinstance(score, (int, float)):
        fill_w = max(1, bar_w * score / 100)
        _set_fill(pdf, color)
        pdf.rect(stats_x, bar_y, fill_w, bar_h, "F")

    pdf.set_xy(stats_x, bar_y + bar_h + 2)
    pdf.set_font(_FONT, "", 9)
    _set_color(pdf, _CLR_SECONDARY_TEXT)

    pdf.cell(50, 5, f"Средний: {_fmt(avg_score)}", new_x="LEFT", new_y="NEXT")
    pdf.set_x(stats_x)
    pdf.cell(50, 5, f"Мин: {_fmt(min_score)}  /  Макс: {_fmt(max_score)}", new_x="LEFT", new_y="NEXT")
    pdf.set_x(stats_x)
    pdf.cell(50, 5, f"Штраф за износ: {_fmt(damage, 4)}", new_x="LMARGIN", new_y="NEXT")

    pdf.set_y(y_start + 34)
    pdf.ln(2)


def _pdf_top_factors(pdf: FPDF, overview: dict) -> None:
    """Render top contributing factors with visual bars."""
    factors = overview.get("top_factors", [])
    if not factors:
        return

    _section_header(pdf, "Основные факторы влияния", _CLR_PRIMARY_DARK)

    cols = [("Датчик", 55), ("Значение", 30), ("Ед.", 18), ("Штраф", 22), ("Вклад", 22), ("Откл.", 22), ("", 60)]
    _table_header_colored(pdf, cols)

    for f in factors[:10]:
        if not isinstance(f, dict):
            continue
        contrib = f.get("contribution_pct", 0)
        values = [
            _sensor_ru(str(f.get("sensor_type", ""))),
            _fmt(f.get("value", 0)),
            str(f.get("unit", "")),
            _fmt(f.get("penalty", 0), 4),
            f"{_fmt(contrib, 1)}%",
            f"{_fmt(f.get('deviation_pct', 0), 1)}%",
        ]
        _table_row_colored(pdf, cols, values, bar_col=6, bar_pct=min(100, abs(contrib)))

    pdf.ln(4)


def _pdf_sensor_stats(pdf: FPDF, stats: list[dict]) -> None:
    if not stats:
        return
    _section_header(pdf, "Статистика датчиков", _CLR_PRIMARY)

    cols = [("Датчик", 55), ("Ед.", 18), ("Среднее", 30), ("Мин.", 30), ("Макс.", 30), ("СКО", 28), ("Кол-во", 22)]
    _table_header_colored(pdf, cols)

    for i, s in enumerate(stats):
        _table_row_colored(
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
            stripe=(i % 2 == 0),
        )
    pdf.ln(4)


def _pdf_alerts(pdf: FPDF, alert_summary: dict, alerts: list[dict]) -> None:
    if alert_summary.get("total", 0) > 0:
        _section_header(pdf, "Сводка предупреждений", _CLR_CRITICAL)

        pdf.set_font(_FONT, "B", 10)
        _set_color(pdf, _CLR_DARK_TEXT)
        pdf.cell(0, 7, f"Всего предупреждений: {alert_summary['total']}", new_x="LMARGIN", new_y="NEXT")

        x = pdf.l_margin
        y = pdf.get_y()
        for sev, count in alert_summary.get("by_severity", {}).items():
            sev_color = _SEVERITY_COLORS.get(sev, _CLR_SECONDARY_TEXT)
            _set_fill(pdf, sev_color)
            _set_color(pdf, _CLR_WHITE)
            pdf.set_font(_FONT, "B", 8)
            label = f" {_severity_ru(sev)}: {count} "
            w = pdf.get_string_width(label) + 6
            pdf.set_xy(x, y)
            pdf.cell(w, 7, label, new_x="RIGHT", new_y="TOP", fill=True)
            x += w + 3
        pdf.set_y(y + 10)
        _set_color(pdf, _CLR_DARK_TEXT)

    if not alerts:
        return

    shown = min(len(alerts), 30)
    _section_header(pdf, f"История предупреждений ({shown} из {len(alerts)})", _CLR_WARNING)

    cols = [("Время", 40), ("Датчик", 44), ("Уровень", 28), ("Значение", 22), ("Описание", 130)]
    _table_header_colored(pdf, cols)

    for i, a in enumerate(alerts[:30]):
        sev = a.get("severity", "info")
        sev_color = _SEVERITY_COLORS.get(sev, _CLR_SECONDARY_TEXT)
        _table_row_colored(
            pdf,
            cols,
            [
                _to_local(a["timestamp"]),
                _sensor_ru(a["sensor_type"]),
                _severity_ru(sev),
                _fmt(a["value"]),
                a["message"],
            ],
            stripe=(i % 2 == 0),
            accent_col=2,
            accent_color=sev_color,
        )
    pdf.ln(4)


def _pdf_fleet_stats(pdf: FPDF, fleet_stats: dict) -> None:
    """Render fleet overview stats with colored category counts."""
    _section_header(pdf, "Состояние парка", _CLR_PRIMARY)

    total = fleet_stats.get("total_locomotives", 0)
    healthy = fleet_stats.get("healthy_count", 0)
    warning = fleet_stats.get("warning_count", 0)
    critical = fleet_stats.get("critical_count", 0)

    pdf.set_font(_FONT, "B", 10)
    _set_color(pdf, _CLR_DARK_TEXT)
    pdf.cell(0, 7, f"Всего локомотивов: {total}", new_x="LMARGIN", new_y="NEXT")

    y = pdf.get_y()
    x = pdf.l_margin
    for label, count, color in [
        ("Норма", healthy, _CLR_HEALTHY),
        ("Внимание", warning, _CLR_WARNING),
        ("Критично", critical, _CLR_CRITICAL),
    ]:
        _set_fill(pdf, color)
        _set_color(pdf, _CLR_WHITE)
        pdf.set_font(_FONT, "B", 9)
        text = f" {label}: {count} "
        w = pdf.get_string_width(text) + 8
        pdf.set_xy(x, y)
        pdf.cell(w, 8, text, fill=True)
        x += w + 4

    pdf.set_y(y + 12)
    bar_x = pdf.l_margin
    bar_w = 180
    bar_h = 8
    if total > 0:
        hw = bar_w * healthy / total
        ww = bar_w * warning / total
        cw = bar_w * critical / total
        if hw > 0:
            _set_fill(pdf, _CLR_HEALTHY)
            pdf.rect(bar_x, pdf.get_y(), hw, bar_h, "F")
        if ww > 0:
            _set_fill(pdf, _CLR_WARNING)
            pdf.rect(bar_x + hw, pdf.get_y(), ww, bar_h, "F")
        if cw > 0:
            _set_fill(pdf, _CLR_CRITICAL)
            pdf.rect(bar_x + hw + ww, pdf.get_y(), cw, bar_h, "F")
    pdf.set_y(pdf.get_y() + bar_h + 4)
    _set_color(pdf, _CLR_DARK_TEXT)
    pdf.ln(2)


def _pdf_worst_locomotives(pdf: FPDF, worst: list[dict]) -> None:
    """Render table of worst-performing locomotives."""
    _section_header(pdf, "Локомотивы с наихудшими показателями", _CLR_CRITICAL)

    cols = [("Локомотив", 80), ("Тип", 55), ("Ср. балл", 30), ("Мин.", 30), ("Макс.", 30)]
    _table_header_colored(pdf, cols)

    for i, loco in enumerate(worst):
        score = loco.get("avg_score", 0)
        color = _health_color(score)
        _table_row_colored(
            pdf,
            cols,
            [
                loco.get("serial_number", str(loco.get("locomotive_id", ""))[:12]),
                _loco_type_ru(loco.get("locomotive_type", "")),
                _fmt(score),
                _fmt(loco.get("min_score", 0)),
                _fmt(loco.get("max_score", 0)),
            ],
            stripe=(i % 2 == 0),
            accent_col=2,
            accent_color=color,
        )
    pdf.ln(4)


def _pdf_anomalies(pdf: FPDF, anomalies: dict) -> None:
    if not anomalies:
        return
    _section_header(pdf, "Обнаруженные аномалии", _CLR_WARNING)
    pdf.set_font(_FONT, "", 10)
    _set_color(pdf, _CLR_DARK_TEXT)

    for sensor, items in anomalies.items():
        count = len(items) if isinstance(items, list) else items
        if isinstance(count, int) and count > 10:
            _set_color(pdf, _CLR_CRITICAL)
        elif isinstance(count, int) and count > 3:
            _set_color(pdf, _CLR_WARNING)
        else:
            _set_color(pdf, _CLR_DARK_TEXT)
        pdf.cell(0, 6, f"  {_sensor_ru(sensor)}: {count} аномалий", new_x="LMARGIN", new_y="NEXT")

    _set_color(pdf, _CLR_DARK_TEXT)


def _pdf_footer(pdf: FPDF) -> None:
    """Add footer to all pages."""
    total_pages = pdf.pages_count
    for i in range(1, total_pages + 1):
        pdf.page = i
        pdf.set_y(-15)
        _set_draw(pdf, _CLR_BORDER)
        pdf.line(pdf.l_margin, pdf.get_y(), pdf.w - pdf.r_margin, pdf.get_y())
        pdf.set_font(_FONT, "", 7)
        _set_color(pdf, _CLR_SECONDARY_TEXT)
        pdf.cell(0, 8, f"КТЖ — Цифровой двойник локомотива  |  Стр. {i}/{total_pages}", align="C")


def _section_header(pdf: FPDF, title: str, color: tuple[int, int, int] = _CLR_PRIMARY) -> None:
    """Section header with colored left accent bar."""
    if pdf.get_y() > pdf.h - 45:
        pdf.add_page()

    y = pdf.get_y()
    _set_fill(pdf, color)
    pdf.rect(pdf.l_margin, y, 4, 10, "F")

    pdf.set_font(_FONT, "B", 12)
    _set_color(pdf, color)
    pdf.set_x(pdf.l_margin + 8)
    pdf.cell(0, 10, title, new_x="LMARGIN", new_y="NEXT")

    _set_draw(pdf, _CLR_BORDER)
    pdf.line(pdf.l_margin, pdf.get_y(), pdf.w - pdf.r_margin, pdf.get_y())
    pdf.ln(3)
    _set_color(pdf, _CLR_DARK_TEXT)


def _table_header_colored(pdf: FPDF, cols: list[tuple[str, int]]) -> None:
    """Table header with dark background."""
    _set_fill(pdf, _CLR_TABLE_HEADER)
    _set_color(pdf, _CLR_WHITE)
    pdf.set_font(_FONT, "B", 8)
    for name, w in cols:
        pdf.cell(w, 7, name, border=0, align="C", fill=True)
    pdf.ln()
    _set_color(pdf, _CLR_DARK_TEXT)


def _table_row_colored(
    pdf: FPDF,
    cols: list[tuple[str, int]],
    values: list[str],
    stripe: bool = False,
    bar_col: int | None = None,
    bar_pct: float = 0,
    accent_col: int | None = None,
    accent_color: tuple[int, int, int] | None = None,
) -> None:
    """Table row with optional striping, bar visualization, and accent coloring."""
    if pdf.get_y() + 6 > pdf.h - pdf.b_margin:
        pdf.add_page()
        _table_header_colored(pdf, cols)

    row_h = 6

    if stripe:
        _set_fill(pdf, _CLR_TABLE_STRIPE)
        pdf.rect(pdf.l_margin, pdf.get_y(), sum(w for _, w in cols), row_h, "F")

    pdf.set_font(_FONT, "", 8)

    for i, ((_, w), v) in enumerate(zip(cols, values, strict=False)):
        if i == bar_col:
            bar_x = pdf.get_x() + 2
            bar_y = pdf.get_y() + 1.5
            bar_w = w - 4
            bar_h = 3
            _set_fill(pdf, _CLR_BORDER)
            pdf.rect(bar_x, bar_y, bar_w, bar_h, "F")
            if bar_pct > 0:
                _set_fill(pdf, _CLR_PRIMARY)
                pdf.rect(bar_x, bar_y, bar_w * bar_pct / 100, bar_h, "F")
            pdf.cell(w, row_h, "", border=0)
            continue

        if accent_col is not None and i == accent_col and accent_color:
            _set_color(pdf, accent_color)
            pdf.set_font(_FONT, "B", 8)

        max_chars = int(w * 0.6)
        display = v if len(v) <= max_chars else v[: max_chars - 1] + "…"
        pdf.cell(w, row_h, display, border=0)

        if accent_col is not None and i == accent_col:
            _set_color(pdf, _CLR_DARK_TEXT)
            pdf.set_font(_FONT, "", 8)

    pdf.ln()
