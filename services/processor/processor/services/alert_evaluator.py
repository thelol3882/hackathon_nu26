"""Alert evaluator: per-loco threshold specs, TE33A AESS masking, and
contextual cross-parameter checks (e.g. oil_pressure vs diesel_rpm).
"""

from datetime import UTC, datetime

from shared.constants import (
    AESS_MASKED_SENSORS,
    AESS_RPM_THRESHOLD,
    LOCO_SPECS,
    SensorSpec,
)
from shared.enums import AlertSeverity, SensorType, ThresholdType
from shared.log_codes import ALERT_PERSISTED
from shared.observability import get_logger
from shared.schemas.alert import AlertEvent
from shared.schemas.telemetry import TelemetryReading
from shared.utils import generate_id

logger = get_logger(__name__)

# Operator recommendations by sensor type and severity (Russian, user-facing).
RECOMMENDATIONS: dict[str, dict[str, str]] = {
    SensorType.DIESEL_RPM: {
        "warning": "Проверить регулятор оборотов, снизить нагрузку на 1-2 позиции",
        "critical": "Немедленно снизить позицию контроллера, подготовить аварийное торможение",
        "emergency": "СТОП! Заглушить дизель, активировать аварийный протокол",
    },
    SensorType.OIL_PRESSURE: {
        "warning": "Проверить уровень масла, контролировать давление каждые 5 минут",
        "critical": "Снизить обороты дизеля, подготовиться к остановке для осмотра",
        "emergency": "СТОП! Немедленно заглушить дизель — риск заклинивания",
    },
    SensorType.COOLANT_TEMP: {
        "warning": "Проверить работу вентиляторов охлаждения, снизить нагрузку",
        "critical": "Снизить позицию до 3-4, открыть жалюзи радиатора вручную",
        "emergency": "СТОП! Остановить локомотив, заглушить дизель — перегрев",
    },
    SensorType.FUEL_LEVEL: {
        "warning": "Запланировать дозаправку на ближайшей станции",
        "critical": "Связаться с диспетчером, запросить экстренную дозаправку",
        "emergency": "Остановить поезд на ближайшей станции, топливо на исходе",
    },
    SensorType.FUEL_RATE: {
        "warning": "Проверить форсунки, контролировать расход",
        "critical": "Снизить нагрузку, проверить топливную систему на утечки",
        "emergency": "Остановить локомотив, возможна утечка топлива",
    },
    SensorType.TRACTION_MOTOR_TEMP: {
        "warning": "Снизить тяговое усилие, проверить вентиляцию ТЭД",
        "critical": "Переключить на пониженный режим тяги, проверить подшипники",
        "emergency": "СТОП! Отключить тяговые двигатели — риск возгорания обмоток",
    },
    SensorType.CRANKCASE_PRESSURE: {
        "warning": "Контролировать давление, проверить состояние поршневых колец",
        "critical": "Снизить обороты, подготовить аварийную остановку",
        "emergency": "СТОП! Заглушить дизель — риск взрыва картерных газов",
    },
    SensorType.CATENARY_VOLTAGE: {
        "warning": "Контролировать напряжение, снизить потребление тока",
        "critical": "Опустить токоприёмник, связаться с энергодиспетчером",
        "emergency": "СТОП! Немедленно опустить токоприёмник, обесточить ВВК",
    },
    SensorType.PANTOGRAPH_CURRENT: {
        "warning": "Снизить тяговое усилие, проверить контакт токоприёмника",
        "critical": "Снизить скорость, подготовить опускание токоприёмника",
        "emergency": "Опустить токоприёмник, активировать аварийный протокол",
    },
    SensorType.TRANSFORMER_TEMP: {
        "warning": "Проверить вентиляцию трансформатора, снизить ток тяги",
        "critical": "Ограничить мощность до 50%, контролировать каждые 2 минуты",
        "emergency": "СТОП! Отключить тяговый трансформатор — риск пробоя изоляции",
    },
    SensorType.IGBT_TEMP: {
        "warning": "Проверить систему охлаждения преобразователя",
        "critical": "Ограничить мощность, снизить ток тяги",
        "emergency": "Отключить тяговый преобразователь — перегрев IGBT-модулей",
    },
    SensorType.BRAKE_PIPE_PRESSURE: {
        "warning": "Проверить утечки в тормозной магистрали",
        "critical": "Снизить скорость, подготовить экстренное торможение",
        "emergency": "СТОП! Применить экстренное торможение — утечка давления",
    },
    SensorType.WHEEL_SLIP_RATIO: {
        "warning": "Активировать песочницу, снизить тяговое усилие",
        "critical": "Снизить тягу до минимума, контролировать сцепление",
        "emergency": "Отключить тягу, применить песок на рельсы",
    },
    SensorType.SPEED_ACTUAL: {
        "warning": "Снизить скорость до установленного ограничения",
        "critical": "Немедленно применить служебное торможение",
        "emergency": "Применить экстренное торможение — превышение скорости",
    },
    SensorType.DC_LINK_VOLTAGE: {
        "warning": "Контролировать напряжение звена постоянного тока",
        "critical": "Снизить мощность рекуперации, проверить конденсаторы",
        "emergency": "Отключить тяговый инвертор — опасное напряжение",
    },
    SensorType.RECUPERATION_CURRENT: {
        "warning": "Снизить ток рекуперации, проверить нагрузку",
        "critical": "Переключить на реостатное торможение",
        "emergency": "Отключить рекуперацию — перегрузка цепи",
    },
}

_DEFAULT_RECOMMENDATION = {
    "info": "Параметр отклонился от нормы — продолжайте мониторинг",
    "warning": "Проверить параметр, подготовить план действий",
    "critical": "Требуется немедленное вмешательство оператора",
    "emergency": "АВАРИЙНАЯ СИТУАЦИЯ — следуйте аварийному протоколу",
}


def _get_recommendation(sensor_type: str, severity: AlertSeverity) -> str:
    sensor_recs = RECOMMENDATIONS.get(sensor_type, {})
    return sensor_recs.get(severity.value, _DEFAULT_RECOMMENDATION.get(severity.value, ""))


def _is_aess_active(sensor_map: dict[str, float]) -> bool:
    """True when TE33A AESS sleep mode is active (RPM below threshold)."""
    rpm = sensor_map.get(SensorType.DIESEL_RPM.value)
    return rpm is not None and rpm <= AESS_RPM_THRESHOLD


def _threshold_violated(value: float, spec: SensorSpec) -> bool:
    """True if the value has left the safe zone (triggers at least WARNING)."""
    if spec.threshold_type == ThresholdType.BIDIRECTIONAL:
        return abs(value - spec.p_nom) > spec.delta_safe
    if spec.threshold_type == ThresholdType.UPPER_BOUND:
        return value > spec.p_nom + spec.delta_safe
    if spec.threshold_type == ThresholdType.LOWER_BOUND:
        return value < spec.p_nom - spec.delta_safe
    if spec.threshold_type == ThresholdType.EXACT_MATCH:
        return not (abs(value - spec.p_nom) < 1e-6)
    return False


def _severity_from_spec(value: float, spec: SensorSpec) -> AlertSeverity:
    """Severity from normalized deviation into the critical zone (mirrors HI formula)."""
    if spec.threshold_type == ThresholdType.BIDIRECTIONAL:
        dev = abs(value - spec.p_nom)
    elif spec.threshold_type == ThresholdType.UPPER_BOUND:
        dev = max(0.0, value - spec.p_nom)
    elif spec.threshold_type == ThresholdType.LOWER_BOUND:
        dev = max(0.0, spec.p_nom - value)
    else:
        dev = abs(spec.crit_range)

    exceedance = max(0.0, dev - spec.delta_safe)
    normalized = min(1.0, exceedance / spec.crit_range) if spec.crit_range > 0 else 1.0

    if normalized >= 0.9 or spec.weight >= 35:
        return AlertSeverity.EMERGENCY
    if normalized >= 0.6:
        return AlertSeverity.CRITICAL
    if normalized >= 0.3:
        return AlertSeverity.WARNING
    return AlertSeverity.INFO


def evaluate_alerts(reading: TelemetryReading) -> list[AlertEvent]:
    """Evaluate all sensors in a reading; return AlertEvents to persist/publish."""
    specs = LOCO_SPECS.get(reading.locomotive_type.value, {})
    loco_id = reading.locomotive_id
    ts = datetime.now(UTC)

    sensor_map: dict[str, float] = {s.sensor_type.value: s.value for s in reading.sensors}
    sensor_units: dict[str, str] = {s.sensor_type.value: s.unit for s in reading.sensors}

    # AESS sleep suppresses false oil-pressure shutdowns on TE33A.
    aess_active = reading.locomotive_type.value == "TE33A" and _is_aess_active(sensor_map)

    alerts: list[AlertEvent] = []

    for sensor_type_str, spec in specs.items():
        value = sensor_map.get(sensor_type_str)
        if value is None:
            continue

        if aess_active and sensor_type_str in AESS_MASKED_SENSORS:
            # Suppress false low-RPM / low-pressure alerts while engine is asleep.
            continue

        if sensor_type_str == SensorType.OIL_PRESSURE.value:
            rpm = sensor_map.get(SensorType.DIESEL_RPM.value, 0.0)
            _coolant = sensor_map.get(SensorType.COOLANT_TEMP.value, 70.0)
            # Minimum oil pressure scales linearly: ~1.5 bar at idle, ~3.0 bar at Notch 8.
            min_expected = 1.5 + (rpm / 1050.0) * 1.5
            if value >= min_expected:
                continue

        if not _threshold_violated(value, spec):
            continue

        severity = _severity_from_spec(value, spec)

        if spec.threshold_type == ThresholdType.UPPER_BOUND:
            thr_min, thr_max = spec.p_nom - spec.delta_safe, spec.p_crit
        elif spec.threshold_type == ThresholdType.LOWER_BOUND:
            thr_min, thr_max = spec.p_crit, spec.p_nom + spec.delta_safe
        else:
            half = abs(spec.p_crit - spec.p_nom)
            thr_min, thr_max = spec.p_nom - half, spec.p_nom + half

        unit = sensor_units.get(sensor_type_str, "")
        message = (
            f"[{reading.locomotive_type.value}] {sensor_type_str} = {value:.2f} {unit} "
            f"(допустимо: {thr_min:.2f}–{thr_max:.2f} {unit})"
        )

        alerts.append(
            AlertEvent(
                id=generate_id(),
                locomotive_id=loco_id,
                sensor_type=sensor_type_str,  # type: ignore[arg-type]
                severity=severity,
                value=value,
                threshold_min=thr_min,
                threshold_max=thr_max,
                message=message,
                recommendation=_get_recommendation(sensor_type_str, severity),
                timestamp=ts,
                acknowledged=False,
            )
        )

    if alerts:
        logger.warning(
            "Alerts created",
            code=ALERT_PERSISTED,
            locomotive_id=str(loco_id),
            alert_count=len(alerts),
            severities=[a.severity.value for a in alerts],
        )
    return alerts
