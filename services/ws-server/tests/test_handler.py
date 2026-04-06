"""Tests for ws_server.handler WebSocket endpoints."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from starlette.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from ws_server.handler import router, set_manager


@pytest.fixture(autouse=True)
def _reset_manager():
    set_manager(None)
    yield
    set_manager(None)


def _make_app():
    from fastapi import FastAPI

    app = FastAPI()
    app.include_router(router)
    return app


def test_ws_live_missing_ticket():
    app = _make_app()
    manager = AsyncMock()
    set_manager(manager)

    client = TestClient(app)
    with pytest.raises(WebSocketDisconnect) as exc_info, client.websocket_connect("/ws/live/loco-1"):
        pass
    assert exc_info.value.code == 4400


def test_ws_live_invalid_ticket():
    app = _make_app()
    manager = AsyncMock()
    set_manager(manager)

    with (
        patch("ws_server.handler.get_redis_raw") as mock_get_redis,
        patch("ws_server.handler.validate_ticket", new_callable=AsyncMock) as mock_validate,
    ):
        mock_get_redis.return_value = AsyncMock()
        mock_validate.return_value = None

        client = TestClient(app)
        with (
            pytest.raises(WebSocketDisconnect) as exc_info,
            client.websocket_connect("/ws/live/loco-1?ticket=bad-ticket"),
        ):
            pass
        assert exc_info.value.code == 4401


def test_ws_live_server_not_ready():
    app = _make_app()

    client = TestClient(app)
    with pytest.raises(WebSocketDisconnect) as exc_info, client.websocket_connect("/ws/live/loco-1?ticket=some-ticket"):
        pass
    assert exc_info.value.code == 1011


def test_ws_live_connection_limit():
    app = _make_app()
    manager = AsyncMock()
    manager.accept = AsyncMock(return_value=False)
    set_manager(manager)

    with (
        patch("ws_server.handler.get_redis_raw") as mock_get_redis,
        patch("ws_server.handler.validate_ticket", new_callable=AsyncMock) as mock_validate,
    ):
        mock_get_redis.return_value = AsyncMock()
        mock_validate.return_value = {"user_id": "u1", "role": "operator"}

        client = TestClient(app)
        with pytest.raises(WebSocketDisconnect), client.websocket_connect("/ws/live/loco-1?ticket=valid-ticket"):
            pass

        manager.accept.assert_called_once()


def test_ws_fleet_missing_ticket():
    app = _make_app()
    manager = AsyncMock()
    set_manager(manager)

    client = TestClient(app)
    with pytest.raises(WebSocketDisconnect) as exc_info, client.websocket_connect("/ws/fleet"):
        pass
    assert exc_info.value.code == 4400


def test_ws_fleet_invalid_ticket():
    app = _make_app()
    manager = AsyncMock()
    set_manager(manager)

    with (
        patch("ws_server.handler.get_redis_raw") as mock_get_redis,
        patch("ws_server.handler.validate_ticket", new_callable=AsyncMock) as mock_validate,
    ):
        mock_get_redis.return_value = AsyncMock()
        mock_validate.return_value = None

        client = TestClient(app)
        with pytest.raises(WebSocketDisconnect) as exc_info, client.websocket_connect("/ws/fleet?ticket=bad"):
            pass
        assert exc_info.value.code == 4401


def test_ws_fleet_server_not_ready():
    app = _make_app()

    client = TestClient(app)
    with pytest.raises(WebSocketDisconnect) as exc_info, client.websocket_connect("/ws/fleet?ticket=t"):
        pass
    assert exc_info.value.code == 1011
