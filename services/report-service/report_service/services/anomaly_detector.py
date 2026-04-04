"""Statistical anomaly detection on time-series sensor data."""

from shared.observability import get_logger

logger = get_logger(__name__)


def detect_zscore_anomalies(
    values: list[float],
    threshold: float = 3.0,
) -> list[int]:
    """Return indices of values that are > threshold standard deviations from mean."""
    if len(values) < 2:
        return []

    mean = sum(values) / len(values)
    variance = sum((v - mean) ** 2 for v in values) / len(values)
    std = variance**0.5

    if std == 0:
        return []

    anomalies = [i for i, v in enumerate(values) if abs(v - mean) / std > threshold]
    if anomalies:
        logger.info(
            "Z-score anomalies detected",
            anomaly_count=len(anomalies),
            total_values=len(values),
            threshold=threshold,
        )
    return anomalies
