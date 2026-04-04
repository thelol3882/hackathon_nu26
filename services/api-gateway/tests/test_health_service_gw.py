"""Tests for _compute_component_score and _categorize in health_service."""

from __future__ import annotations

import pytest

from api_gateway.services.health_service import _categorize, _compute_component_score

# ---------------------------------------------------------------------------
# _compute_component_score
# ---------------------------------------------------------------------------


class TestComputeComponentScore:
    def test_at_midpoint_returns_1(self):
        # value exactly at midpoint of [60, 100] -> score 1.0
        score = _compute_component_score(80.0, 60.0, 100.0)
        assert score == pytest.approx(1.0)

    def test_within_range_near_boundary(self):
        # value at lo boundary: deviation = 1.0, score = 1 - 1.0*0.3 = 0.7
        score = _compute_component_score(60.0, 60.0, 100.0)
        assert score == pytest.approx(0.7)

    def test_equal_lo_hi_returns_1(self):
        # span = 0, so score should be 1.0 for exact match
        score = _compute_component_score(50.0, 50.0, 50.0)
        assert score == pytest.approx(1.0)

    def test_below_range(self):
        # value = 50, lo = 60, hi = 100
        # overshoot = (60-50)/max(60,1) = 10/60 ~ 0.1667
        # score = max(0, 1 - 0.1667) ~ 0.833
        score = _compute_component_score(50.0, 60.0, 100.0)
        assert 0.0 < score < 1.0
        expected = 1.0 - (60.0 - 50.0) / 60.0
        assert score == pytest.approx(expected)

    def test_above_range(self):
        # value = 110, lo = 60, hi = 100
        # overshoot = (110-100)/max(100,1) = 10/100 = 0.1
        # score = 1 - 0.1 = 0.9
        score = _compute_component_score(110.0, 60.0, 100.0)
        expected = 1.0 - (110.0 - 100.0) / 100.0
        assert score == pytest.approx(expected)

    def test_value_far_below_range_clamped_to_0(self):
        # value = 0, lo = 100, hi = 200
        # overshoot = (100 - 0) / 100 = 1.0
        # score = max(0, 1 - 1.0) = 0.0
        score = _compute_component_score(0.0, 100.0, 200.0)
        assert score == pytest.approx(0.0)

    def test_value_far_above_range_clamped_to_0(self):
        # value = 500, lo = 60, hi = 100
        # overshoot = (500 - 100)/100 = 4.0
        # score = max(0, 1-4) = 0.0
        score = _compute_component_score(500.0, 60.0, 100.0)
        assert score == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# _categorize
# ---------------------------------------------------------------------------


class TestCategorize:
    def test_norma(self):
        assert _categorize(90.0) == "Норма"

    def test_vnimanie(self):
        assert _categorize(65.0) == "Внимание"

    def test_kritichno(self):
        assert _categorize(30.0) == "Критично"

    def test_boundary_80_is_norma(self):
        assert _categorize(80.0) == "Норма"

    def test_boundary_50_is_vnimanie(self):
        assert _categorize(50.0) == "Внимание"

    def test_boundary_49_9_is_kritichno(self):
        assert _categorize(49.9) == "Критично"
