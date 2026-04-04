"""Redis subscription → WebSocket fan-out relay."""

from fastapi import WebSocket

from api_gateway.core.redis_client import subscribe_telemetry


async def relay_telemetry_to_ws(ws: WebSocket, loco_id: str) -> None:
    """Subscribe to Redis channel and forward messages to a WebSocket client."""
    async for message in subscribe_telemetry(loco_id):
        await ws.send_text(message)
