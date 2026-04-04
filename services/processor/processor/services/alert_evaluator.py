"""
Alert evaluator with:
  - Per-locomotive-type threshold specs (bidirectional / upper / lower / exact_match)
  - AESS masking for TE33A (sleep mode suppresses RPM and oil-pressure alerts)
  - Contextual cross-parameter validation (oil_pressure vs diesel_rpm)
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


def _is_aess_active(sensor_map: dict[str, float]) -> bool:
    """
    Detect TE33A Auto Engine Start/Stop sleep mode.
    Returns True when engine is considered stopped (RPM below threshold).
    """
    rpm = sensor_map.get(SensorType.DIESEL_RPM.value)
    return rpm is not None and rpm <= AESS_RPM_THRESHOLD


def _threshold_violated(value: float, spec: SensorSpec) -> bool:
    """
    Check whether the value has LEFT the safe zone (triggers at least a WARNING).

    Alert levels:
      - Leaving safe zone (> p_nom ± delta_safe) → WARNING or higher
      - Crossing p_crit                           → CRITICAL / EMERGENCY
    """
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
    """
    Derive severity based on how far into the critical zone the value is.
    Uses the same normalized deviation as the HI formula.
    """

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
    """
    Evaluate all sensors in a TelemetryReading against per-type specs.

    Returns a (possibly empty) list of AlertEvent objects to persist and publish.
    """
    specs = LOCO_SPECS.get(reading.locomotive_type.value, {})
    loco_id = reading.locomotive_id
    ts = datetime.now(UTC)

    sensor_map: dict[str, float] = {s.sensor_type.value: s.value for s in reading.sensors}
    sensor_units: dict[str, str] = {s.sensor_type.value: s.unit for s in reading.sensors}

    # TE33A: detect AESS sleep mode to avoid false oil-pressure shutdowns
    aess_active = reading.locomotive_type.value == "TE33A" and _is_aess_active(sensor_map)

    alerts: list[AlertEvent] = []

    for sensor_type_str, spec in specs.items():
        value = sensor_map.get(sensor_type_str)
        if value is None:
            continue

        # ── AESS masking ────────────────────────────────────────────────
        if aess_active and sensor_type_str in AESS_MASKED_SENSORS:
            continue  # suppress false low-RPM / low-pressure alerts during sleep

        # ── Contextual masking: oil pressure needs RPM context ──────────
        if sensor_type_str == SensorType.OIL_PRESSURE.value:
            rpm = sensor_map.get(SensorType.DIESEL_RPM.value, 0.0)
            _coolant = sensor_map.get(SensorType.COOLANT_TEMP.value, 70.0)
            # At low RPM (idle, Notch 0–1) minimum oil pressure is ~1.5 bar — normal
            # At high RPM (Notch 8) minimum expectation is ~3.0 bar
            min_expected = 1.5 + (rpm / 1050.0) * 1.5  # scales linearly with load
            if value >= min_expected:
                continue  # contextually acceptable — skip alert

        if not _threshold_violated(value, spec):
            continue

        severity = _severity_from_spec(value, spec)

        # Determine readable threshold bounds for the alert message
        if spec.threshold_type == ThresholdType.UPPER_BOUND:
            thr_min, thr_max = spec.p_nom - spec.delta_safe, spec.p_crit
        elif spec.threshold_type == ThresholdType.LOWER_BOUND:
            thr_min, thr_max = spec.p_crit, spec.p_nom + spec.delta_safe
        else:  # BIDIRECTIONAL / EXACT_MATCH
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
