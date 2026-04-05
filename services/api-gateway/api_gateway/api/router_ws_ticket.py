"""Endpoint for requesting a one-time WebSocket authentication ticket.

The client calls this with a valid JWT, receives a short-lived ticket,
and uses it to connect to the separate WS Server.
"""

from fastapi import APIRouter
from pydantic import BaseModel

from api_gateway.api.dependencies import Redis
from api_gateway.core.auth import CurrentUser
from shared.ws_ticket import WS_TICKET_TTL, create_ticket

router = APIRouter()


class TicketResponse(BaseModel):
    ticket: str
    expires_in: int
    ws_url: str


@router.get("/ws/ticket", response_model=TicketResponse)
async def get_ws_ticket(user: CurrentUser, redis: Redis):
    """Generate a one-time ticket for WebSocket authentication.

    Requires valid JWT in Authorization header.
    Returns a ticket that can be used once within 30 seconds
    to connect to the WebSocket server.
    """
    ticket = await create_ticket(
        redis,
        user_id=str(user.id),
        role=user.role,
    )
    return TicketResponse(
        ticket=ticket,
        expires_in=WS_TICKET_TTL,
        ws_url="/ws/live",
    )
