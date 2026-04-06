"""One-time-use WebSocket auth tickets.

Browsers can't set headers on WS connections; passing a JWT via ``?token=``
would leak the long-lived JWT into logs/history/Referer. Tickets are short-
lived (30s), single-use (GETDEL), and carry only user_id + role.

Flow: client GET /ws/ticket with JWT -> API Gateway stores ticket in Redis
-> client opens WS with ?ticket=X -> WS Server consumes ticket via GETDEL.
"""

from __future__ import annotations

import json
import uuid

import redis.asyncio as aioredis

WS_TICKET_PREFIX = "ws:ticket"
WS_TICKET_TTL = 30  # seconds


async def create_ticket(
    redis_client: aioredis.Redis,
    user_id: str,
    role: str,
) -> str:
    """Generate and store a one-time WS ticket; return the ticket string."""
    ticket = str(uuid.uuid4())
    key = f"{WS_TICKET_PREFIX}:{ticket}"
    data = json.dumps({"user_id": user_id, "role": role})
    await redis_client.set(key, data, ex=WS_TICKET_TTL)
    return ticket


async def validate_ticket(
    redis_client: aioredis.Redis,
    ticket: str,
) -> dict | None:
    """Atomically consume a WS ticket. Returns {user_id, role} or None.

    GETDEL (Redis 6.2+) ensures single-use even under concurrent connects.
    """
    key = f"{WS_TICKET_PREFIX}:{ticket}"
    raw = await redis_client.getdel(key)
    if raw is None:
        return None
    return json.loads(raw)
