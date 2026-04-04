from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from api_gateway.services.realtime_relay import relay_telemetry_to_ws

router = APIRouter()


@router.websocket("/ws/telemetry/{loco_id}")
async def ws_telemetry(ws: WebSocket, loco_id: str):
    """Real-time telemetry stream for a specific locomotive."""
    await ws.accept()
    try:
        await relay_telemetry_to_ws(ws, loco_id)
    except WebSocketDisconnect:
        pass
