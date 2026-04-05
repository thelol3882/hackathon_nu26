"""Tests for db_writer.services.stream_consumer."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from shared.wire import decode as wire_decode
from shared.wire import encode as wire_encode

# ── Payload encoding / decoding ───────────────────────────────────────


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


# ── StreamConsumer._process_entries ───────────────────────────────────


class TestProcessEntries:
    @pytest.fixture
    def consumer(self):
        from db_writer.services.stream_consumer import StreamConsumer

        redis_mock = AsyncMock()
        session_factory = MagicMock()
        model_class = MagicMock()
        model_class.__tablename__ = "raw_telemetry"
        return StreamConsumer(
            redis_client=redis_mock,
            session_factory=session_factory,
            stream="stream:telemetry",
            consumer_name="test-writer",
            model_class=model_class,
        )

    @pytest.mark.asyncio
    async def test_decodes_and_accumulates_rows(self, consumer):
        rows = [{"sensor_type": "COOLANT_TEMP", "value": 82.0}]
        payload = wire_encode({"rows": rows})
        entries = [(b"1-0", {b"d": payload})]

        with patch.object(consumer, "_bulk_insert", new_callable=AsyncMock) as mock_insert:
            await consumer._process_entries(entries)
            mock_insert.assert_called_once()
            inserted_rows = mock_insert.call_args[0][0]
            assert len(inserted_rows) == 1
            assert inserted_rows[0]["sensor_type"] == "COOLANT_TEMP"

        # Verify XACK was called
        consumer._redis.xack.assert_called_once()

    @pytest.mark.asyncio
    async def test_acks_malformed_message(self, consumer):
        """Messages without 'd' field should still be acknowledged."""
        entries = [(b"1-0", {b"other": b"data"})]

        with patch.object(consumer, "_bulk_insert", new_callable=AsyncMock) as mock_insert:
            await consumer._process_entries(entries)
            mock_insert.assert_not_called()

        consumer._redis.xack.assert_called_once()

    @pytest.mark.asyncio
    async def test_no_ack_on_empty(self, consumer):
        """No entries means no XACK call."""
        await consumer._process_entries([])
        consumer._redis.xack.assert_not_called()

    @pytest.mark.asyncio
    async def test_multiple_messages_merged(self, consumer):
        """Multiple stream messages should merge rows before insert."""
        rows1 = [{"sensor_type": "A", "value": 1.0}]
        rows2 = [{"sensor_type": "B", "value": 2.0}, {"sensor_type": "C", "value": 3.0}]
        entries = [
            (b"1-0", {b"d": wire_encode({"rows": rows1})}),
            (b"2-0", {b"d": wire_encode({"rows": rows2})}),
        ]

        with patch.object(consumer, "_bulk_insert", new_callable=AsyncMock) as mock_insert:
            await consumer._process_entries(entries)
            inserted_rows = mock_insert.call_args[0][0]
            assert len(inserted_rows) == 3

    @pytest.mark.asyncio
    async def test_no_ack_on_insert_failure(self, consumer):
        """If bulk_insert raises, messages should NOT be acknowledged."""
        rows = [{"sensor_type": "COOLANT_TEMP", "value": 82.0}]
        payload = wire_encode({"rows": rows})
        entries = [(b"1-0", {b"d": payload})]

        with (
            patch.object(consumer, "_bulk_insert", new_callable=AsyncMock, side_effect=Exception("DB error")),
            pytest.raises(Exception, match="DB error"),
        ):
            await consumer._process_entries(entries)

        consumer._redis.xack.assert_not_called()


# ── Bulk insert chunking ─────────────────────────────────────────────


class TestBulkInsertChunking:
    @pytest.mark.asyncio
    async def test_chunks_large_batch(self):
        """Rows exceeding _INSERT_CHUNK should be split into multiple INSERTs."""
        from db_writer.services.stream_consumer import _INSERT_CHUNK, StreamConsumer

        redis_mock = AsyncMock()
        model_class = MagicMock()
        model_class.__tablename__ = "raw_telemetry"

        mock_session = AsyncMock()
        mock_session_ctx = AsyncMock()
        mock_session_ctx.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_ctx.__aexit__ = AsyncMock(return_value=False)
        session_factory = MagicMock(return_value=mock_session_ctx)

        consumer = StreamConsumer(
            redis_client=redis_mock,
            session_factory=session_factory,
            stream="stream:telemetry",
            consumer_name="test-writer",
            model_class=model_class,
        )

        # Create rows that exceed one chunk
        rows = [{"time": f"2026-01-01T{i:05d}", "value": float(i)} for i in range(_INSERT_CHUNK + 500)]

        with patch("db_writer.services.stream_consumer.pg_insert") as mock_pg_insert:
            mock_stmt = MagicMock()
            mock_stmt.on_conflict_do_nothing.return_value = mock_stmt
            mock_pg_insert.return_value.values.return_value = mock_stmt

            await consumer._bulk_insert(rows)

            # Should be 2 execute calls (one full chunk + one remainder)
            assert mock_session.execute.call_count == 2
            mock_session.commit.assert_called_once()
