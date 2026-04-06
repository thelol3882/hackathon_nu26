"""Tests for report_service.services.anomaly_detector."""

import random

from report_service.services.anomaly_detector import detect_zscore_anomalies


class TestDetectZscoreAnomaliesHappy:
    def test_no_anomalies_uniform(self):
        result = detect_zscore_anomalies([5.0, 5.0, 5.0, 5.0, 5.0])
        assert result == []

    def test_detect_single_outlier(self):
        values = [1.0] * 20 + [100.0]
        result = detect_zscore_anomalies(values)
        assert 20 in result

    def test_detect_multiple_outliers(self):
        values = [10.0] * 50 + [100.0, -80.0]
        result = detect_zscore_anomalies(values)
        assert 50 in result
        assert 51 in result

    def test_custom_threshold_catches_more(self):
        values = [0.0] * 20 + [5.0]
        result_strict = detect_zscore_anomalies(values, threshold=1.0)
        result_default = detect_zscore_anomalies(values, threshold=3.0)
        assert len(result_strict) >= len(result_default)
        assert 20 in result_strict

    def test_large_dataset_with_outlier(self):
        random.seed(42)
        values = [random.gauss(50, 2) for _ in range(1000)]
        values.append(200.0)
        result = detect_zscore_anomalies(values)
        assert 1000 in result


class TestDetectZscoreAnomaliesEdge:
    def test_empty_list(self):
        assert detect_zscore_anomalies([]) == []

    def test_single_value(self):
        assert detect_zscore_anomalies([5.0]) == []

    def test_two_values(self):
        # For [1, 2]: population std=0.5, z-scores are ±1.0 — can't exceed 3.
        result = detect_zscore_anomalies([1.0, 2.0])
        assert result == []

    def test_all_same_values_std_zero(self):
        result = detect_zscore_anomalies([5.0, 5.0, 5.0, 5.0])
        assert result == []

    def test_negative_values(self):
        values = [-1.0, -1.0, -1.0, 0.0, 0.0, 0.0, 1.0, 1.0, 1.0] * 5 + [100.0]
        result = detect_zscore_anomalies(values)
        assert len(values) - 1 in result
