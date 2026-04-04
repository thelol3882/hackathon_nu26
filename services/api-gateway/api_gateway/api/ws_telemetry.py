"""WebSocket endpoints for real-time telemetry and alert streaming."""

from __future__ import annotations

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from api_gateway.services.connection_manager import ConnectionManager
from shared.constants import ALERT_CHANNEL, TELEMETRY_CHANNEL

router = APIRouter()


def _get_manager(ws: WebSocket) -> ConnectionManager:
    return ws.app.state.ws_manager


@router.websocket("/ws/telemetry/{loco_id}")
async def ws_telemetry(ws: WebSocket, loco_id: str):
    """Real-time telemetry stream for a specific locomotive."""
    manager = _get_manager(ws)
    if not await manager.accept(ws):
        return

    channel = f"{TELEMETRY_CHANNEL}:{loco_id}"
    await manager.subscribe(ws, channel)
    try:
        while True:
            await ws.receive_text()  # keep alive, detect disconnect
    except (WebSocketDisconnect, Exception):
        pass
    finally:
        await manager.disconnect(ws)


@router.websocket("/ws/alerts")
async def ws_alerts(ws: WebSocket):
    """Real-time alert stream (all locomotives)."""
    manager = _get_manager(ws)
    if not await manager.accept(ws):
        return

    await manager.subscribe(ws, ALERT_CHANNEL)
    try:
        while True:
            await ws.receive_text()
    except (WebSocketDisconnect, Exception):
        pass
    finally:
        await manager.disconnect(ws)


@router.websocket("/ws/live/{loco_id}")
async def ws_live(ws: WebSocket, loco_id: str):
    """Combined telemetry + alerts stream for a specific locomotive.

    Messages are wrapped in envelopes:
        {"type": "telemetry", "data": {...}}
        {"type": "alert", "data": {...}}
    """
    manager = _get_manager(ws)
    if not await manager.accept(ws):
        return

    telemetry_channel = f"{TELEMETRY_CHANNEL}:{loco_id}"
    await manager.subscribe(ws, telemetry_channel)
    await manager.subscribe(ws, ALERT_CHANNEL, filter_loco_id=loco_id)
    try:
        while True:
            await ws.receive_text()
    except (WebSocketDisconnect, Exception):
        pass
    finally:
        await manager.disconnect(ws)
