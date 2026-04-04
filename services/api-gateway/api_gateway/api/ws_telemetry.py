"""WebSocket endpoints for real-time telemetry and alert streaming.

Wire format (JSON or msgpack) is controlled globally by WIRE_FORMAT env var.
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


@router.websocket("/ws/telemetry/{loco_id}")
async def ws_telemetry(ws: WebSocket, loco_id: str):
    """Real-time telemetry stream for a specific locomotive."""
    manager = _get_manager(ws)
    if not await manager.accept(ws):
        return

    channel = f"{TELEMETRY_CHANNEL}:{loco_id}"
    await manager.subscribe(ws, channel)
    logger.info("WS telemetry connected", code=WS_CONNECTED, loco_id=loco_id)
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
    if not await manager.accept(ws):
        return

    await manager.subscribe(ws, ALERT_CHANNEL)
    logger.info("WS alerts connected", code=WS_CONNECTED)
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
    """
    manager = _get_manager(ws)
    if not await manager.accept(ws):
        return

    telemetry_channel = f"{TELEMETRY_CHANNEL}:{loco_id}"
    health_channel = f"{HEALTH_CHANNEL}:{loco_id}"
    await manager.subscribe(ws, telemetry_channel, envelope_type="telemetry")
    await manager.subscribe(ws, ALERT_CHANNEL, filter_loco_id=loco_id, envelope_type="alert")
    await manager.subscribe(ws, health_channel, envelope_type="health")
    logger.info("WS live connected", code=WS_CONNECTED, loco_id=loco_id)
    try:
        while True:
            await ws.receive_text()
    except (WebSocketDisconnect, Exception):
        pass
    finally:
        logger.info("WS live disconnected", code=WS_DISCONNECTED, loco_id=loco_id)
        await manager.disconnect(ws)
