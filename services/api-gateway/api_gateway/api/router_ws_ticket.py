"""Endpoint for requesting one-time WebSocket authentication tickets."""

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
    """Generate a short-lived one-time ticket for WebSocket authentication."""
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
