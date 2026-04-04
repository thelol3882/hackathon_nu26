"""Tests for api_gateway.services.connection_manager.ConnectionManager."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from starlette.websockets import WebSocketState

from api_gateway.services.connection_manager import ConnectionManager

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_ws():
    ws = AsyncMock()
    ws.accept = AsyncMock()
    ws.close = AsyncMock()
    ws.send_bytes = AsyncMock()
    ws.send_text = AsyncMock()
    ws.send_json = AsyncMock()
    ws.client_state = WebSocketState.CONNECTED
    return ws


# ---------------------------------------------------------------------------
# accept
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_accept_success(mock_redis):
    mgr = ConnectionManager(mock_redis, max_connections=10)
    ws = _make_ws()

    result = await mgr.accept(ws)

    assert result is True
    assert mgr.active_connections == 1
    ws.accept.assert_awaited_once()


@pytest.mark.asyncio
async def test_accept_over_limit(mock_redis):
    mgr = ConnectionManager(mock_redis, max_connections=1)

    ws1 = _make_ws()
    ws2 = _make_ws()

    await mgr.accept(ws1)
    result = await mgr.accept(ws2)

    assert result is False
    ws2.close.assert_awaited_once()
    close_kwargs = ws2.close.call_args
    assert (
        close_kwargs[1].get("code") == 1013
        or (close_kwargs[0] and close_kwargs[0][0] == 1013)
        or 1013 in str(close_kwargs)
    )
    assert mgr.active_connections == 1


# ---------------------------------------------------------------------------
# disconnect
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_disconnect_decrements(mock_redis):
    mgr = ConnectionManager(mock_redis, max_connections=10)
    ws = _make_ws()

    await mgr.accept(ws)
    assert mgr.active_connections == 1

    await mgr.disconnect(ws)
    assert mgr.active_connections == 0


@pytest.mark.asyncio
async def test_disconnect_removes_relay_when_empty(mock_redis):
    mgr = ConnectionManager(mock_redis, max_connections=10)
    ws = _make_ws()

    await mgr.accept(ws)

    # Patch _ChannelRelay so subscribe works without real Redis
    with patch("api_gateway.services.connection_manager._ChannelRelay") as mock_relay_cls:
        relay_instance = AsyncMock()
        relay_instance.remove_client = AsyncMock(return_value=0)
        relay_instance.add_client = AsyncMock()
        mock_relay_cls.return_value = relay_instance

        await mgr.subscribe(ws, "telemetry:live")
        assert "telemetry:live" in mgr._relays

    # Now replace the relay in _relays with one whose remove_client returns 0
    relay_mock = AsyncMock()
    relay_mock.remove_client = AsyncMock(return_value=0)
    mgr._relays["telemetry:live"] = relay_mock

    await mgr.disconnect(ws)

    assert mgr.active_connections == 0
    assert "telemetry:live" not in mgr._relays


# ---------------------------------------------------------------------------
# subscribe
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_subscribe_creates_relay(mock_redis):
    mgr = ConnectionManager(mock_redis, max_connections=10)
    ws = _make_ws()

    await mgr.accept(ws)

    with patch("api_gateway.services.connection_manager._ChannelRelay") as mock_relay_cls:
        relay_instance = AsyncMock()
        relay_instance.add_client = AsyncMock()
        mock_relay_cls.return_value = relay_instance

        await mgr.subscribe(ws, "telemetry:live")

    assert "telemetry:live" in mgr._relays


# ---------------------------------------------------------------------------
# shutdown
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_shutdown_clears(mock_redis):
    mgr = ConnectionManager(mock_redis, max_connections=10)
    ws = _make_ws()

    await mgr.accept(ws)

    await mgr.shutdown()

    assert mgr.active_connections == 0
    assert len(mgr._relays) == 0
