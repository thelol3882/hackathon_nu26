"""WebSocket endpoints for real-time telemetry and alert streaming.

Query params:
    ?format=msgpack  — receive binary msgpack frames (default: JSON text)
"""

from __future__ import annotations

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from api_gateway.services.connection_manager import ConnectionManager
from shared.constants import ALERT_CHANNEL, HEALTH_CHANNEL, TELEMETRY_CHANNEL
from shared.log_codes import WS_CONNECTED, WS_DISCONNECTED
from shared.observability import get_logger

logger = get_logger(__name__)

router = APIRouter()


def _get_manager(ws: WebSocket) -> ConnectionManager:
    return ws.app.state.ws_manager


def _wants_msgpack(ws: WebSocket) -> bool:
    return ws.query_params.get("format", "json") == "msgpack"


@router.websocket("/ws/telemetry/{loco_id}")
async def ws_telemetry(ws: WebSocket, loco_id: str):
    """Real-time telemetry stream for a specific locomotive."""
    manager = _get_manager(ws)
    use_msgpack = _wants_msgpack(ws)
    if not await manager.accept(ws, use_msgpack=use_msgpack):
        return

    channel = f"{TELEMETRY_CHANNEL}:{loco_id}"
    await manager.subscribe(ws, channel)
    fmt = "msgpack" if use_msgpack else "json"
    logger.info("WS telemetry connected", code=WS_CONNECTED, loco_id=loco_id, ws_format=fmt)
    try:
        while True:
            await ws.receive_text()
    except (WebSocketDisconnect, Exception):
        pass
    finally:
        logger.info("WS telemetry disconnected", code=WS_DISCONNECTED, loco_id=loco_id)
        await manager.disconnect(ws)


@router.websocket("/ws/alerts")
async def ws_alerts(ws: WebSocket):
    """Real-time alert stream (all locomotives)."""
    manager = _get_manager(ws)
    use_msgpack = _wants_msgpack(ws)
    if not await manager.accept(ws, use_msgpack=use_msgpack):
        return

    await manager.subscribe(ws, ALERT_CHANNEL)
    fmt = "msgpack" if use_msgpack else "json"
    logger.info("WS alerts connected", code=WS_CONNECTED, ws_format=fmt)
    try:
        while True:
            await ws.receive_text()
    except (WebSocketDisconnect, Exception):
        pass
    finally:
        logger.info("WS alerts disconnected", code=WS_DISCONNECTED)
        await manager.disconnect(ws)


@router.websocket("/ws/live/{loco_id}")
async def ws_live(ws: WebSocket, loco_id: str):
    """Combined telemetry + alerts + health stream for a specific locomotive.

    Messages are wrapped in envelopes:
        {"type": "telemetry", "data": {...}}
        {"type": "alert", "data": {...}}
        {"type": "health", "data": {...}}

    Connect with ?format=msgpack for binary frames.
    """
    manager = _get_manager(ws)
    use_msgpack = _wants_msgpack(ws)
    if not await manager.accept(ws, use_msgpack=use_msgpack):
        return

    telemetry_channel = f"{TELEMETRY_CHANNEL}:{loco_id}"
    health_channel = f"{HEALTH_CHANNEL}:{loco_id}"
    await manager.subscribe(ws, telemetry_channel)
    await manager.subscribe(ws, ALERT_CHANNEL, filter_loco_id=loco_id)
    await manager.subscribe(ws, health_channel)
    fmt = "msgpack" if use_msgpack else "json"
    logger.info("WS live connected", code=WS_CONNECTED, loco_id=loco_id, ws_format=fmt)
    try:
        while True:
            await ws.receive_text()
    except (WebSocketDisconnect, Exception):
        pass
    finally:
        logger.info("WS live disconnected", code=WS_DISCONNECTED, loco_id=loco_id)
        await manager.disconnect(ws)
