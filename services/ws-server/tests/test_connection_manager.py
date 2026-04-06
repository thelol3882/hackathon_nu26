"""Tests for ws_server.connection_manager."""

from __future__ import annotations

from unittest.mock import AsyncMock, PropertyMock

import pytest

from ws_server.connection_manager import ConnectionManager


def _mock_redis():
    redis = AsyncMock()
    pubsub = AsyncMock()
    pubsub.subscribe = AsyncMock()
    pubsub.unsubscribe = AsyncMock()
    pubsub.aclose = AsyncMock()
    redis.pubsub.return_value = pubsub
    return redis


def _mock_ws(*, connected=True):
    ws = AsyncMock()
    ws.accept = AsyncMock()
    ws.close = AsyncMock()
    ws.send_bytes = AsyncMock()
    from starlette.websockets import WebSocketState

    type(ws).client_state = PropertyMock(
        return_value=WebSocketState.CONNECTED if connected else WebSocketState.DISCONNECTED
    )
    return ws


@pytest.mark.asyncio
async def test_accept_increments_active_connections():
    manager = ConnectionManager(_mock_redis(), max_connections=10)
    ws = _mock_ws()

    result = await manager.accept(ws)

    assert result is True
    assert manager.active_connections == 1
    ws.accept.assert_called_once()


@pytest.mark.asyncio
async def test_accept_rejects_over_limit():
    manager = ConnectionManager(_mock_redis(), max_connections=1)
    ws1 = _mock_ws()
    ws2 = _mock_ws()

    await manager.accept(ws1)
    result = await manager.accept(ws2)

    assert result is False
    assert manager.active_connections == 1
    ws2.close.assert_called_once_with(code=1013, reason="Server too busy")


@pytest.mark.asyncio
async def test_disconnect_decrements_active_connections():
    manager = ConnectionManager(_mock_redis(), max_connections=10)
    ws = _mock_ws()

    await manager.accept(ws)
    assert manager.active_connections == 1

    await manager.disconnect(ws)
    assert manager.active_connections == 0


@pytest.mark.asyncio
async def test_subscribe_creates_relay():
    redis = _mock_redis()
    manager = ConnectionManager(redis, max_connections=10)
    ws = _mock_ws()

    await manager.accept(ws)
    await manager.subscribe(ws, "telemetry:live:loco-1", envelope_type="telemetry")

    assert "telemetry:live:loco-1" in manager._relays
    assert manager._relays["telemetry:live:loco-1"].client_count == 1


@pytest.mark.asyncio
async def test_disconnect_removes_from_all_channels():
    redis = _mock_redis()
    manager = ConnectionManager(redis, max_connections=10)
    ws = _mock_ws()

    await manager.accept(ws)
    await manager.subscribe(ws, "ch1", envelope_type="a")
    await manager.subscribe(ws, "ch2", envelope_type="b")

    await manager.disconnect(ws)

    # Relays with zero clients are cleaned up.
    assert manager.active_connections == 0
    assert "ch1" not in manager._relays
    assert "ch2" not in manager._relays


@pytest.mark.asyncio
async def test_mark_pong():
    redis = _mock_redis()
    manager = ConnectionManager(redis, max_connections=10)
    ws = _mock_ws()

    await manager.accept(ws)

    ws_id = id(ws)
    state = manager._ws_states[ws_id]
    state.pong_received = False

    manager.mark_pong(ws)
    assert state.pong_received is True


@pytest.mark.asyncio
async def test_mark_pong_unknown_ws():
    redis = _mock_redis()
    manager = ConnectionManager(redis, max_connections=10)
    ws = _mock_ws()

    manager.mark_pong(ws)


@pytest.mark.asyncio
async def test_shutdown_clears_all():
    redis = _mock_redis()
    manager = ConnectionManager(redis, max_connections=10)
    ws1 = _mock_ws()
    ws2 = _mock_ws()

    await manager.accept(ws1)
    await manager.accept(ws2)
    await manager.subscribe(ws1, "ch1", envelope_type="a")
    await manager.subscribe(ws2, "ch1", envelope_type="a")

    await manager.shutdown()

    assert manager.active_connections == 0
    assert len(manager._relays) == 0


@pytest.mark.asyncio
async def test_multiple_clients_same_channel():
    redis = _mock_redis()
    manager = ConnectionManager(redis, max_connections=10)
    ws1 = _mock_ws()
    ws2 = _mock_ws()

    await manager.accept(ws1)
    await manager.accept(ws2)
    await manager.subscribe(ws1, "ch1", envelope_type="a")
    await manager.subscribe(ws2, "ch1", envelope_type="a")

    assert manager._relays["ch1"].client_count == 2

    await manager.disconnect(ws1)
    assert manager._relays["ch1"].client_count == 1

    await manager.disconnect(ws2)
    assert "ch1" not in manager._relays
