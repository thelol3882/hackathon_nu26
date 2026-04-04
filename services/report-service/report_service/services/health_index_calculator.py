"""Weighted health index scoring across sensor readings."""

from shared.constants import DEFAULT_THRESHOLDS, HEALTH_WEIGHTS
from shared.log_codes import HEALTH_COMPUTED
from shared.observability import get_logger
from shared.schemas.health import ComponentHealth

logger = get_logger(__name__)


def calculate_component_score(
    sensor_type: str,
    value: float,
    unit: str,
) -> ComponentHealth:
    """Score a single component 0.0-1.0 based on how close it is to threshold bounds."""
    bounds = DEFAULT_THRESHOLDS.get(sensor_type)
    if bounds is None:
        return ComponentHealth(sensor_type=sensor_type, score=1.0, latest_value=value, unit=unit)

    min_val, max_val = bounds
    midpoint = (min_val + max_val) / 2
    half_range = (max_val - min_val) / 2

    if half_range == 0:
        score = 1.0
    else:
        deviation = abs(value - midpoint) / half_range
        score = max(0.0, 1.0 - deviation)

    return ComponentHealth(sensor_type=sensor_type, score=round(score, 4), latest_value=value, unit=unit)


def calculate_overall_score(components: list[ComponentHealth]) -> float:
    """Weighted average of component scores."""
    total_weight = 0.0
    weighted_sum = 0.0

    for comp in components:
        weight = HEALTH_WEIGHTS.get(comp.sensor_type, 0.05)
        weighted_sum += comp.score * weight
        total_weight += weight

    if total_weight == 0:
        return 0.0

    score = round(weighted_sum / total_weight, 4)
    logger.info(
        "Overall health score calculated",
        code=HEALTH_COMPUTED,
        component_count=len(components),
        score=score,
    )
    return score
