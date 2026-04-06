"""WebSocket ticket system for secure, one-time-use authentication.

Browser WebSocket API doesn't support custom headers.  The common workaround
is ``ws://host/ws?token=JWT``, but this leaks the long-lived JWT into server
access logs, browser history, and Referer headers.

Tickets solve this:
  - One-time use: deleted from Redis immediately via GETDEL
  - Short TTL: 30 seconds, useless after expiration
  - Minimal data: only user_id and role, not a full auth token

Flow:
  1. Client calls ``GET /ws/ticket`` with JWT in Authorization header
  2. API Gateway validates JWT, creates ticket in Redis (TTL 30s)
  3. Client opens WebSocket with ``?ticket=<ticket>``
  4. WS Server validates + consumes ticket via GETDEL, accepts connection
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
    """Generate a one-time WebSocket ticket and store in Redis.

    Called by API Gateway when an authenticated user requests a WS ticket.
    Returns the ticket string for the client to pass as a query parameter.
    """
    ticket = str(uuid.uuid4())
    key = f"{WS_TICKET_PREFIX}:{ticket}"
    data = json.dumps({"user_id": user_id, "role": role})
    await redis_client.set(key, data, ex=WS_TICKET_TTL)
    return ticket


async def validate_ticket(
    redis_client: aioredis.Redis,
    ticket: str,
) -> dict | None:
    """Validate and consume a WebSocket ticket.

    Uses GETDEL (Redis 6.2+) for atomic get-and-delete so the ticket
    can only be used exactly once, even with concurrent connection attempts.

    Returns ``{user_id, role}`` on success, ``None`` if expired or already used.
    """
    key = f"{WS_TICKET_PREFIX}:{ticket}"
    raw = await redis_client.getdel(key)
    if raw is None:
        return None
    return json.loads(raw)
