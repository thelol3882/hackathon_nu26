"""Middleware that binds user context from JWT to structlog."""

import jwt
import structlog
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from api_gateway.core.config import get_settings


class UserContextMiddleware(BaseHTTPMiddleware):
    """Binds user_id + user_role to structlog context. Does NOT enforce auth."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
            try:
                settings = get_settings()
                payload = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
                structlog.contextvars.bind_contextvars(
                    user_id=payload.get("sub"),
                    user_role=payload.get("role"),
                )
            except (jwt.InvalidTokenError, Exception):
                pass  # no user context for this request

        return await call_next(request)
