"""Tests for db_writer.services.stream_consumer."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from shared.wire import decode as wire_decode
from shared.wire import encode as wire_encode


class TestPayloadCodec:
    def test_round_trip(self):
        rows = [
            {"sensor_type": "COOLANT_TEMP", "value": 82.0},
            {"sensor_type": "DIESEL_RPM", "value": 700.0},
        ]
        encoded = wire_encode({"rows": rows})
        decoded = wire_decode(encoded)
        assert decoded["rows"] == rows

    def test_empty_rows(self):
        encoded = wire_encode({"rows": []})
        decoded = wire_decode(encoded)
        assert decoded["rows"] == []


def _make_consumer(model_class=None, worker_count: int = 1, rows_per_flush: int = 5000):
    """Build a StreamConsumer wired to fully-mocked Redis and pg pool."""
    from db_writer.services.stream_consumer import StreamConsumer

    if model_class is None:
        from db_writer.models.telemetry_entity import TelemetryRecord

        model_class = TelemetryRecord

    redis_mock = AsyncMock()
    pg_pool = AsyncMock()

    return StreamConsumer(
        redis_client=redis_mock,
        pg_pool=pg_pool,
        stream="stream:telemetry",
        consumer_name="test-writer",
        model_class=model_class,
        staging_tables=[f"raw_telemetry_staging_test_{i}" for i in range(worker_count)],
        reader_batch_size=50,
        rows_per_flush=rows_per_flush,
        queue_maxsize=2,
    )


class TestEnqueueEntries:
    @pytest.mark.asyncio
    async def test_decodes_and_enqueues_rows(self):
        consumer = _make_consumer()
        rows = [
            {
                "time": "2026-01-01T00:00:00+00:00",
                "locomotive_id": "11111111-1111-1111-1111-111111111111",
                "locomotive_type": "DIESEL",
                "sensor_type": "COOLANT_TEMP",
                "value": 82.0,
                "filtered_value": 82.0,
                "unit": "C",
                "sample_rate_hz": 1.0,
                "latitude": None,
                "longitude": None,
            }
        ]
        payload = wire_encode({"rows": rows})
        entries = [(b"1-0", {b"d": payload})]

        await consumer._enqueue_entries(entries)

        assert consumer._queue.qsize() == 1
        msg_ids, enqueued_rows = await consumer._queue.get()
        assert msg_ids == [b"1-0"]
        assert len(enqueued_rows) == 1
        assert enqueued_rows[0]["sensor_type"] == "COOLANT_TEMP"

        consumer._redis.xack.assert_not_called()

    @pytest.mark.asyncio
    async def test_acks_malformed_message_directly(self):
        """Poison pills are ACK'd without going through the queue."""
        consumer = _make_consumer()
        entries = [(b"1-0", {b"other": b"data"})]

        await consumer._enqueue_entries(entries)

        assert consumer._queue.empty()
        consumer._redis.xack.assert_called_once()

    @pytest.mark.asyncio
    async def test_empty_entries_noop(self):
        consumer = _make_consumer()
        await consumer._enqueue_entries([])
        assert consumer._queue.empty()
        consumer._redis.xack.assert_not_called()

    @pytest.mark.asyncio
    async def test_multiple_messages_merged(self):
        """Rows from multiple messages are flattened into one batch."""
        consumer = _make_consumer()
        base = {
            "time": "2026-01-01T00:00:00+00:00",
            "locomotive_id": "11111111-1111-1111-1111-111111111111",
            "locomotive_type": "DIESEL",
            "value": 1.0,
            "filtered_value": 1.0,
            "unit": "U",
            "sample_rate_hz": 1.0,
            "latitude": None,
            "longitude": None,
        }
        rows1 = [{**base, "sensor_type": "A"}]
        rows2 = [{**base, "sensor_type": "B"}, {**base, "sensor_type": "C"}]
        entries = [
            (b"1-0", {b"d": wire_encode({"rows": rows1})}),
            (b"2-0", {b"d": wire_encode({"rows": rows2})}),
        ]

        await consumer._enqueue_entries(entries)

        msg_ids, enqueued_rows = await consumer._queue.get()
        assert msg_ids == [b"1-0", b"2-0"]
        assert len(enqueued_rows) == 3


class TestRowAdapter:
    def test_telemetry_adapter_produces_tuple_in_column_order(self):
        from db_writer.models.telemetry_entity import TelemetryRecord
        from db_writer.services.stream_consumer import _get_adapter

        columns, row_to_tuple = _get_adapter(TelemetryRecord)
        assert columns == (
            "time",
            "locomotive_id",
            "locomotive_type",
            "sensor_type",
            "value",
            "filtered_value",
            "unit",
            "sample_rate_hz",
            "latitude",
            "longitude",
        )

        row = {
            "time": "2026-01-01T00:00:00+00:00",
            "locomotive_id": "11111111-1111-1111-1111-111111111111",
            "locomotive_type": "DIESEL",
            "sensor_type": "COOLANT_TEMP",
            "value": 82.5,
            "filtered_value": 82.3,
            "unit": "C",
            "sample_rate_hz": 1.0,
            "latitude": 55.7,
            "longitude": 37.6,
        }
        tup = row_to_tuple(row)
        from datetime import datetime

        assert isinstance(tup[0], datetime)
        import uuid

        assert isinstance(tup[1], uuid.UUID)
        assert tup[3] == "COOLANT_TEMP"
        assert tup[4] == 82.5

    def test_health_adapter_serializes_jsonb(self):
        from db_writer.models.health_entity import HealthSnapshotRecord
        from db_writer.services.stream_consumer import _get_adapter

        columns, row_to_tuple = _get_adapter(HealthSnapshotRecord)
        assert "top_factors" in columns

        row = {
            "id": "22222222-2222-2222-2222-222222222222",
            "locomotive_id": "11111111-1111-1111-1111-111111111111",
            "locomotive_type": "DIESEL",
            "score": 95.0,
            "category": "healthy",
            "top_factors": [{"sensor": "oil", "impact": 0.1}],
            "damage_penalty": 0.0,
            "calculated_at": "2026-01-01T00:00:00+00:00",
        }
        tup = row_to_tuple(row)
        idx = columns.index("top_factors")
        import json

        assert isinstance(tup[idx], str)
        assert json.loads(tup[idx]) == [{"sensor": "oil", "impact": 0.1}]


class TestWorkerBatchChunking:
    @pytest.mark.asyncio
    async def test_large_batch_split_into_multiple_flushes(self):
        """Batches larger than rows_per_flush split into multiple transactions."""
        from db_writer.services.stream_consumer import StreamConsumer  # noqa: F401

        consumer = _make_consumer(rows_per_flush=100)

        mock_conn = AsyncMock()
        mock_tx = AsyncMock()
        mock_tx.__aenter__ = AsyncMock(return_value=mock_tx)
        mock_tx.__aexit__ = AsyncMock(return_value=False)
        mock_conn.transaction = MagicMock(return_value=mock_tx)
        mock_conn.execute = AsyncMock()
        mock_conn.copy_records_to_table = AsyncMock()

        acquire_ctx = AsyncMock()
        acquire_ctx.__aenter__ = AsyncMock(return_value=mock_conn)
        acquire_ctx.__aexit__ = AsyncMock(return_value=False)
        consumer._pool.acquire = MagicMock(return_value=acquire_ctx)

        # 250 rows with chunk 100 → 3 flushes (100 + 100 + 50).
        rows = [
            {
                "time": "2026-01-01T00:00:00+00:00",
                "locomotive_id": "11111111-1111-1111-1111-111111111111",
                "locomotive_type": "DIESEL",
                "sensor_type": f"S{i}",
                "value": float(i),
                "filtered_value": float(i),
                "unit": "U",
                "sample_rate_hz": 1.0,
                "latitude": None,
                "longitude": None,
            }
            for i in range(250)
        ]

        await consumer._write_batch("raw_telemetry_staging_test_0", rows)

        assert mock_conn.copy_records_to_table.call_count == 3
        # TRUNCATE + INSERT SELECT per chunk × 3 chunks.
        assert mock_conn.execute.call_count == 6
