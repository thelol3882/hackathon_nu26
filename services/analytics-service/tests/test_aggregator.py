"""Tests for analytics.aggregator.FleetAggregator."""

from __future__ import annotations

from analytics.aggregator import FleetAggregator, _LocoState


class TestLocoState:
    def test_slots(self):
        state = _LocoState("id-1", "TE33A", 85.0, "Норма")
        assert state.locomotive_id == "id-1"
        assert state.score == 85.0
        assert not hasattr(state, "__dict__")

    def test_updated_at_set(self):
        state = _LocoState("id-1", "TE33A", 85.0, "Норма")
        assert state.updated_at is not None


class TestUpdateState:
    def _make_aggregator(self):
        return FleetAggregator(redis_client=None)

    def test_first_update_creates_entry(self):
        agg = self._make_aggregator()
        agg._update_state(
            {
                "locomotive_id": "loco-1",
                "locomotive_type": "TE33A",
                "overall_score": 90.0,
                "category": "Норма",
            }
        )
        assert agg.fleet_size == 1
        assert agg._fleet["loco-1"].score == 90.0

    def test_update_overwrites_score(self):
        agg = self._make_aggregator()
        agg._update_state({"locomotive_id": "loco-1", "overall_score": 90.0, "category": "Норма"})
        agg._update_state({"locomotive_id": "loco-1", "overall_score": 70.0, "category": "Внимание"})
        assert agg._fleet["loco-1"].score == 70.0
        assert agg.fleet_size == 1

    def test_no_change_recorded_on_first_update(self):
        agg = self._make_aggregator()
        agg._update_state({"locomotive_id": "loco-1", "overall_score": 90.0, "category": "Норма"})
        assert agg._changes == []

    def test_change_recorded_on_category_transition(self):
        agg = self._make_aggregator()
        agg._update_state({"locomotive_id": "loco-1", "overall_score": 90.0, "category": "Норма"})
        agg._update_state({"locomotive_id": "loco-1", "overall_score": 45.0, "category": "Критично"})
        assert len(agg._changes) == 1
        assert agg._changes[0]["old_category"] == "Норма"
        assert agg._changes[0]["new_category"] == "Критично"

    def test_no_change_when_same_category(self):
        agg = self._make_aggregator()
        agg._update_state({"locomotive_id": "loco-1", "overall_score": 90.0, "category": "Норма"})
        agg._update_state({"locomotive_id": "loco-1", "overall_score": 88.0, "category": "Норма"})
        assert agg._changes == []

    def test_empty_locomotive_id_skipped(self):
        agg = self._make_aggregator()
        agg._update_state({"locomotive_id": "", "overall_score": 90.0, "category": "Норма"})
        assert agg.fleet_size == 0


class TestComputeSummary:
    def _make_aggregator_with_fleet(self, entries):
        agg = FleetAggregator(redis_client=None)
        for entry in entries:
            agg._update_state(entry)
        return agg

    def test_summary_counts_categories(self):
        agg = self._make_aggregator_with_fleet(
            [
                {"locomotive_id": "1", "locomotive_type": "TE33A", "overall_score": 90, "category": "Норма"},
                {"locomotive_id": "2", "locomotive_type": "TE33A", "overall_score": 60, "category": "Внимание"},
                {"locomotive_id": "3", "locomotive_type": "KZ8A", "overall_score": 30, "category": "Критично"},
            ]
        )
        summary = agg._compute_summary()
        assert summary["fleet_size"] == 3
        assert summary["categories"]["norma"] == 1
        assert summary["categories"]["vnimanie"] == 1
        assert summary["categories"]["kritichno"] == 1

    def test_summary_avg_score(self):
        agg = self._make_aggregator_with_fleet(
            [
                {"locomotive_id": "1", "overall_score": 80, "category": "Норма"},
                {"locomotive_id": "2", "overall_score": 60, "category": "Внимание"},
            ]
        )
        summary = agg._compute_summary()
        assert summary["avg_score"] == 70.0

    def test_worst_10_sorted(self):
        entries = [
            {"locomotive_id": str(i), "locomotive_type": "TE33A", "overall_score": float(i * 5), "category": "Норма"}
            for i in range(20)
        ]
        agg = self._make_aggregator_with_fleet(entries)
        summary = agg._compute_summary()
        worst = summary["worst_10"]
        assert len(worst) == 10
        assert worst[0]["score"] == 0.0
        scores = [w["score"] for w in worst]
        assert scores == sorted(scores)

    def test_empty_fleet(self):
        agg = FleetAggregator(redis_client=None)
        assert agg.fleet_size == 0


class TestDrainChanges:
    def test_drain_clears_buffer(self):
        agg = FleetAggregator(redis_client=None)
        agg._update_state({"locomotive_id": "1", "overall_score": 90, "category": "Норма"})
        agg._update_state({"locomotive_id": "1", "overall_score": 40, "category": "Критично"})
        changes = agg._drain_changes()
        assert len(changes) == 1
        assert agg._drain_changes() == []

    def test_drain_empty_returns_empty(self):
        agg = FleetAggregator(redis_client=None)
        assert agg._drain_changes() == []
