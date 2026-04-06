"""WebSocket endpoint with ticket-based authentication.

No JWT decoding here.  No database queries.  No user lookups.
Authentication is delegated to the ticket system:

  1. API Gateway already verified the user's JWT
  2. API Gateway created a one-time ticket in Redis
  3. We just check if the ticket exists in Redis (one GETDEL)

Close codes:
  4400 — Missing ticket parameter
  4401 — Invalid or expired ticket
  1013 — Server too busy (connection limit reached)
  1011 — Server not ready
"""

from __future__ import annotations

from fastapi import APIRouter, Query, WebSocket

from shared.constants import (
    ALERT_CHANNEL,
    FLEET_CHANGES_CHANNEL,
    FLEET_SUMMARY_CHANNEL,
    HEALTH_CHANNEL,
    TELEMETRY_CHANNEL,
)
from shared.observability import get_logger
from shared.wire import decode as wire_decode
from shared.ws_ticket import validate_ticket
from ws_server.connection_manager import ConnectionManager
from ws_server.core.redis_client import get_redis_raw

logger = get_logger(__name__)

router = APIRouter()

_manager: ConnectionManager | None = None


def set_manager(manager: ConnectionManager) -> None:
    """Called from main.py during startup to inject the manager."""
    global _manager
    _manager = manager


@router.websocket("/ws/live/{loco_id}")
async def ws_live(ws: WebSocket, loco_id: str, ticket: str = Query(default=None)):
    """Real-time telemetry + alerts + health stream for a specific locomotive.

    Connection requires a valid one-time ticket from GET /api/ws/ticket.
    """
    if _manager is None:
        await ws.close(code=1011, reason="Server not ready")
        return

    # --- Ticket authentication ---
    if ticket is None:
        await ws.close(code=4400, reason="Missing ticket parameter")
        return

    redis_client = get_redis_raw()
    user_info = await validate_ticket(redis_client, ticket)

    if user_info is None:
        await ws.close(code=4401, reason="Invalid or expired ticket")
        return

    # --- Connection accepted ---
    user_id = user_info.get("user_id", "unknown")

    if not await _manager.accept(ws):
        return  # over connection limit, already closed with 1013

    telemetry_channel = f"{TELEMETRY_CHANNEL}:{loco_id}"
    health_channel = f"{HEALTH_CHANNEL}:{loco_id}"
    await _manager.subscribe(ws, telemetry_channel, envelope_type="telemetry")
    await _manager.subscribe(ws, ALERT_CHANNEL, filter_loco_id=loco_id, envelope_type="alert")
    await _manager.subscribe(ws, health_channel, envelope_type="health")

    logger.info("WS connected via ticket", user_id=user_id, loco_id=loco_id)

    try:
        while True:
            msg = await ws.receive()
            raw = msg.get("bytes")
            if raw is None:
                continue
            try:
                data = wire_decode(raw)
                if isinstance(data, dict) and data.get("type") == "pong":
                    _manager.mark_pong(ws)
            except Exception:
                pass  # ignore malformed client messages
    except Exception:
        pass
    finally:
        logger.info("WS disconnected", user_id=user_id, loco_id=loco_id)
        await _manager.disconnect(ws)


@router.websocket("/ws/fleet")
async def ws_fleet(ws: WebSocket, ticket: str = Query(default=None)):
    """Fleet-wide dashboard stream.

    Receives two types of messages:
      fleet_summary — full fleet stats every ~2 seconds
      fleet_changes — only locomotives that changed category
    """
    if _manager is None:
        await ws.close(code=1011, reason="Server not ready")
        return

    if ticket is None:
        await ws.close(code=4400, reason="Missing ticket parameter")
        return

    redis_client = get_redis_raw()
    user_info = await validate_ticket(redis_client, ticket)

    if user_info is None:
        await ws.close(code=4401, reason="Invalid or expired ticket")
        return

    user_id = user_info.get("user_id", "unknown")

    if not await _manager.accept(ws):
        return

    await _manager.subscribe(ws, FLEET_SUMMARY_CHANNEL, envelope_type="fleet_summary")
    await _manager.subscribe(ws, FLEET_CHANGES_CHANNEL, envelope_type="fleet_changes")

    logger.info("WS fleet connected via ticket", user_id=user_id)

    try:
        while True:
            msg = await ws.receive()
            raw = msg.get("bytes")
            if raw is None:
                continue
            try:
                data = wire_decode(raw)
                if isinstance(data, dict) and data.get("type") == "pong":
                    _manager.mark_pong(ws)
            except Exception:
                pass
    except Exception:
        pass
    finally:
        logger.info("WS fleet disconnected", user_id=user_id)
        await _manager.disconnect(ws)
