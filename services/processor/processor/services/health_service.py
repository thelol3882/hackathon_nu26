"""
Real-time Health Index (HI) calculator.

Formula (non-linear penalty):
    HI(t) = 100 - Σ_i W_i · ( max(0, |P̂_i - P_nom| - δ_safe) / R_i )^k
    clamped to [0, 100]

where:
  P̂_i       = EMA-filtered sensor value
  P_nom      = nominal target value
  δ_safe     = half-width of the safe zone (no penalty inside)
  R_i        = p_crit_range = |P_crit - P_nom| - δ_safe  (normalization)
  k          = exponent (typically 2; higher → steeper near critical)
  W_i        = sensor weight (0–40; ≥35 for fatal parameters)

Damage accumulator (Montsinger's rule for cellulosic insulation):
    aging_rate  = 2^((T - T_ref) / 6)   [doubles every 6 °C above reference]
    damage_incr = (aging_rate - 1.0) × MONTSINGER_BASE_DAMAGE
    Accumulated damage is permanently subtracted from HI to estimate RUL.
"""

import math
from datetime import UTC, datetime

from shared.constants import (
    HI_CATEGORY_NORMAL,
    HI_CATEGORY_WARNING,
    LOCO_SPECS,
    MONTSINGER_BASE_DAMAGE,
    MONTSINGER_DEGREE_STEP,
    SensorSpec,
)
from shared.enums import ThresholdType
from shared.log_codes import HEALTH_COMPUTED, HEALTH_NO_DATA
from shared.observability import get_logger
from shared.schemas.health import HealthFactor, HealthIndex
from shared.schemas.telemetry import SensorPayload, TelemetryReading

logger = get_logger(__name__)

# Damage accumulator: (locomotive_id_str, sensor_type_str) → accumulated penalty
_damage_state: dict[tuple[str, str], float] = {}


def _raw_deviation(value: float, spec: SensorSpec) -> float:
    """Unsigned deviation from nominal, respecting threshold direction."""
    if spec.threshold_type == ThresholdType.BIDIRECTIONAL:
        return abs(value - spec.p_nom)
    if spec.threshold_type == ThresholdType.UPPER_BOUND:
        return max(0.0, value - spec.p_nom)
    if spec.threshold_type == ThresholdType.LOWER_BOUND:
        return max(0.0, spec.p_nom - value)
    if spec.threshold_type == ThresholdType.EXACT_MATCH:
        return 0.0 if math.isclose(value, spec.p_nom, abs_tol=1e-6) else abs(spec.crit_range)
    return 0.0


def _sensor_penalty(value: float, spec: SensorSpec) -> tuple[float, float]:
    """
    Returns (penalty, deviation_pct).

    deviation_pct: how far value has moved from safe zone toward critical, 0–100 %.
    """
    dev = _raw_deviation(value, spec)
    exceedance = max(0.0, dev - spec.delta_safe)
    normalized = min(1.0, exceedance / spec.crit_range)  # 0–1
    penalty = spec.weight * (normalized**spec.k)
    return penalty, normalized * 100.0


def _update_damage(loco_id: str, sensor_type: str, value: float, spec: SensorSpec) -> float:
    """
    Increment damage accumulator using Montsinger's rule and return current total damage.
    Only called for sensors with is_aging_param=True.
    """
    ref = spec.montsinger_ref_temp
    if value <= ref:
        return _damage_state.get((loco_id, sensor_type), 0.0)

    aging_rate = 2.0 ** ((value - ref) / MONTSINGER_DEGREE_STEP)
    increment = (aging_rate - 1.0) * MONTSINGER_BASE_DAMAGE
    key = (loco_id, sensor_type)
    _damage_state[key] = _damage_state.get(key, 0.0) + increment
    return _damage_state[key]


def calculate_health(reading: TelemetryReading) -> HealthIndex:
    """
    Compute the real-time Health Index for one telemetry reading.

    Uses filtered (EMA) sensor values that should already be applied upstream
    (ingestion_service passes filtered_value into each SensorPayload before
    calling this function).
    """
    loco_id = str(reading.locomotive_id)
    specs = LOCO_SPECS.get(reading.locomotive_type.value, {})

    sensor_map: dict[str, SensorPayload] = {s.sensor_type.value: s for s in reading.sensors}

    penalties: list[tuple[str, float, float, float, str]] = []
    # Each entry: (sensor_type, penalty, deviation_pct, value, unit)

    total_damage = 0.0

    for sensor_key, spec in specs.items():
        sensor = sensor_map.get(sensor_key)
        if sensor is None:
            continue  # sensor not present in this reading

        penalty, dev_pct = _sensor_penalty(sensor.value, spec)

        # Montsinger accumulation for aging-sensitive components
        if spec.is_aging_param:
            damage = _update_damage(loco_id, sensor_key, sensor.value, spec)
            penalty += damage
            total_damage += damage

        penalties.append((sensor_key, penalty, dev_pct, sensor.value, sensor.unit))

    penalties.sort(key=lambda x: x[1], reverse=True)

    total_penalty = sum(p[1] for p in penalties)
    raw_score = 100.0 - total_penalty
    score = max(0.0, min(100.0, raw_score))

    if score >= HI_CATEGORY_NORMAL:
        category = "Норма"
    elif score >= HI_CATEGORY_WARNING:
        category = "Внимание"
    else:
        category = "Критично"

    top5 = penalties[:5]
    contribution_base = max(total_penalty, 1e-6)  # avoid division by zero
    top_factors = [
        HealthFactor(
            sensor_type=name,
            value=val,
            unit=unit,
            penalty=round(pen, 4),
            contribution_pct=round(pen / contribution_base * 100.0, 2),
            deviation_pct=round(dev, 2),
        )
        for name, pen, dev, val, unit in top5
    ]

    result = HealthIndex(
        locomotive_id=reading.locomotive_id,
        locomotive_type=reading.locomotive_type.value,
        overall_score=round(score, 2),
        category=category,
        top_factors=top_factors,
        damage_penalty=round(total_damage, 6),
        calculated_at=datetime.now(UTC),
    )

    if penalties:
        logger.info(
            "Health index computed",
            code=HEALTH_COMPUTED,
            locomotive_id=loco_id,
            score=result.overall_score,
            category=category,
            damage_penalty=round(total_damage, 6),
        )
    else:
        logger.debug(
            "Health index computed with no sensor data",
            code=HEALTH_NO_DATA,
            locomotive_id=loco_id,
        )

    return result


def get_damage_state(loco_id: str) -> dict[str, float]:
    """Return accumulated damage per sensor for a locomotive (diagnostic use)."""
    return {sensor: dmg for (lid, sensor), dmg in _damage_state.items() if lid == loco_id}
