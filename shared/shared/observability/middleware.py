"""Request context middleware: enriches every log with HTTP metadata."""

import time

import structlog
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from shared.log_codes import HTTP_REQUEST
from shared.utils import generate_id


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Binds request_id/client_ip/user_agent/method/path/service to structlog
    context and logs an access summary per request."""

    def __init__(self, app, service_name: str = "unknown", access_log_enabled: bool = True) -> None:
        super().__init__(app)
        self.service_name = service_name
        self.access_log_enabled = access_log_enabled
        self._logger = structlog.get_logger("access")

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if request.url.path == "/metrics":
            return await call_next(request)

        request_id = request.headers.get("X-Request-ID", str(generate_id()))

        # Respect reverse-proxy forwarded IP
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            client_ip = forwarded.split(",")[0].strip()
        elif request.client:
            client_ip = request.client.host
        else:
            client_ip = "unknown"

        user_agent = request.headers.get("User-Agent", "unknown")

        structlog.contextvars.bind_contextvars(
            request_id=request_id,
            client_ip=client_ip,
            user_agent=user_agent,
            http_method=request.method,
            http_path=request.url.path,
            service=self.service_name,
        )

        start = time.perf_counter()
        try:
            response = await call_next(request)
            duration_ms = round((time.perf_counter() - start) * 1000, 1)

            response.headers["X-Request-ID"] = request_id

            if self.access_log_enabled:
                self._logger.info(
                    "Request handled",
                    code=HTTP_REQUEST,
                    status=response.status_code,
                    duration_ms=duration_ms,
                )
            return response
        except Exception:
            duration_ms = round((time.perf_counter() - start) * 1000, 1)
            if self.access_log_enabled:
                self._logger.exception(
                    "Request failed",
                    code=HTTP_REQUEST,
                    status=500,
                    duration_ms=duration_ms,
                )
            raise
        finally:
            structlog.contextvars.clear_contextvars()
