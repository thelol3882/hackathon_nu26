"""Tests for report_service.services.anomaly_detector."""

import random

from report_service.services.anomaly_detector import detect_zscore_anomalies

# ── Happy-path tests ──────────────────────────────────────────────────────────


class TestDetectZscoreAnomaliesHappy:
    def test_no_anomalies_uniform(self):
        """All identical values -> std=0 -> empty list."""
        result = detect_zscore_anomalies([5.0, 5.0, 5.0, 5.0, 5.0])
        assert result == []

    def test_detect_single_outlier(self):
        """One extreme outlier in otherwise constant data."""
        # Need enough constant values so the outlier's z-score exceeds 3.
        values = [1.0] * 20 + [100.0]
        result = detect_zscore_anomalies(values)
        assert 20 in result

    def test_detect_multiple_outliers(self):
        """Both high and low outliers detected."""
        values = [10.0] * 50 + [100.0, -80.0]
        result = detect_zscore_anomalies(values)
        assert 50 in result  # high outlier
        assert 51 in result  # low outlier

    def test_custom_threshold_catches_more(self):
        """Lower threshold detects values that default threshold=3.0 misses."""
        values = [0.0] * 20 + [5.0]
        # With default threshold=3.0 this might or might not trigger;
        # with threshold=1.0 the outlier is definitely caught.
        result_strict = detect_zscore_anomalies(values, threshold=1.0)
        result_default = detect_zscore_anomalies(values, threshold=3.0)
        assert len(result_strict) >= len(result_default)
        assert 20 in result_strict

    def test_large_dataset_with_outlier(self):
        """1000 normal values + 1 extreme outlier."""
        random.seed(42)
        values = [random.gauss(50, 2) for _ in range(1000)]
        values.append(200.0)  # clear outlier
        result = detect_zscore_anomalies(values)
        assert 1000 in result


# ── Edge-case tests ───────────────────────────────────────────────────────────


class TestDetectZscoreAnomaliesEdge:
    def test_empty_list(self):
        assert detect_zscore_anomalies([]) == []

    def test_single_value(self):
        assert detect_zscore_anomalies([5.0]) == []

    def test_two_values(self):
        """Two values: neither can be >3 std from the population mean."""
        # For [1, 2]: mean=1.5, std=0.5, z-scores = 1.0 for both -> not >3.
        result = detect_zscore_anomalies([1.0, 2.0])
        assert result == []

    def test_all_same_values_std_zero(self):
        result = detect_zscore_anomalies([5.0, 5.0, 5.0, 5.0])
        assert result == []

    def test_negative_values(self):
        """Mix of negative and positive with one outlier."""
        values = [-1.0, -1.0, -1.0, 0.0, 0.0, 0.0, 1.0, 1.0, 1.0] * 5 + [100.0]
        result = detect_zscore_anomalies(values)
        assert len(values) - 1 in result  # 100.0 is the outlier
