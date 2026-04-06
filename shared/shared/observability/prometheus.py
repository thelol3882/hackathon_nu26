"""Prometheus metrics: per-service counters, histograms, and /metrics endpoint."""

from __future__ import annotations

import os
import time

from fastapi import FastAPI, Request, Response
from prometheus_client import (
    CollectorRegistry,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.routing import Match


def _get_path_template(request: Request) -> str:
    """Return the route template (e.g. /telemetry/{loco_id}) instead of the concrete path."""
    for route in request.app.routes:
        match, _ = route.matches(request.scope)
        if match == Match.FULL:
            return getattr(route, "path", request.url.path)
    return request.url.path


registry = CollectorRegistry()

# HTTP metrics
http_requests_total = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["service", "method", "path", "status"],
    registry=registry,
)

http_request_duration_seconds = Histogram(
    "http_request_duration_seconds",
    "HTTP request latency in seconds",
    ["service", "method", "path"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0),
    registry=registry,
)

http_requests_in_progress = Gauge(
    "http_requests_in_progress",
    "Number of HTTP requests currently being processed",
    ["service"],
    registry=registry,
)

# Business metrics (populated by services)
telemetry_ingested_total = Counter(
    "telemetry_ingested_total",
    "Total telemetry readings ingested",
    ["locomotive_type"],
    registry=registry,
)

health_index_calculated_total = Counter(
    "health_index_calculated_total",
    "Total health index calculations performed",
    registry=registry,
)

health_index_value = Gauge(
    "health_index_value",
    "Latest health index score per locomotive",
    ["locomotive_id", "locomotive_type"],
    registry=registry,
)

alerts_fired_total = Counter(
    "alerts_fired_total",
    "Total alerts fired",
    ["severity", "sensor_type"],
    registry=registry,
)

ws_connections_active = Gauge(
    "ws_connections_active",
    "Number of active WebSocket connections",
    registry=registry,
)

reports_generated_total = Counter(
    "reports_generated_total",
    "Total reports generated",
    ["format", "status"],
    registry=registry,
)

# Stream consumer metrics (DB Writer)
stream_messages_consumed = Counter(
    "stream_messages_consumed_total",
    "Total messages consumed from Redis Streams",
    ["stream"],
    registry=registry,
)

stream_rows_written = Counter(
    "stream_rows_written_total",
    "Total rows written to TimescaleDB by DB Writer",
    ["table"],
    registry=registry,
)

stream_write_errors = Counter(
    "stream_write_errors_total",
    "Total failed batch writes",
    ["stream"],
    registry=registry,
)

stream_consumer_lag = Gauge(
    "stream_consumer_lag",
    "Number of pending (unacknowledged) messages in stream",
    ["stream"],
    registry=registry,
)

# Fleet aggregator metrics (Analytics Service)
fleet_aggregator_size = Gauge(
    "fleet_aggregator_size",
    "Number of locomotives tracked by fleet aggregator",
    registry=registry,
)

fleet_summary_published = Counter(
    "fleet_summary_published_total",
    "Total fleet summary publishes",
    registry=registry,
)

fleet_changes_detected = Counter(
    "fleet_changes_detected_total",
    "Total category changes detected across fleet",
    registry=registry,
)


class PrometheusMiddleware(BaseHTTPMiddleware):
    """Collects request count, latency, and in-progress gauge per route."""

    def __init__(self, app: FastAPI, service_name: str) -> None:
        super().__init__(app)
        self.service_name = service_name

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if request.url.path == "/metrics":
            return await call_next(request)

        path = _get_path_template(request)
        method = request.method

        http_requests_in_progress.labels(service=self.service_name).inc()
        start = time.perf_counter()

        try:
            response = await call_next(request)
        except Exception:
            http_requests_total.labels(service=self.service_name, method=method, path=path, status="500").inc()
            raise
        finally:
            duration = time.perf_counter() - start
            http_requests_in_progress.labels(service=self.service_name).dec()
            http_request_duration_seconds.labels(service=self.service_name, method=method, path=path).observe(duration)

        http_requests_total.labels(
            service=self.service_name, method=method, path=path, status=str(response.status_code)
        ).inc()

        return response


def _env(service_name: str, key: str, default: str) -> str:
    prefix = service_name.upper().replace("-", "_")
    return os.environ.get(f"{prefix}_{key}", os.environ.get(key, default))


def setup_prometheus(app: FastAPI, service_name: str) -> None:
    """Add Prometheus middleware and /metrics endpoint to a FastAPI app."""
    enabled = _env(service_name, "PROMETHEUS_ENABLED", "true").lower() == "true"
    if not enabled:
        return

    app.add_middleware(PrometheusMiddleware, service_name=service_name)

    @app.get("/metrics", include_in_schema=False)
    async def metrics():
        return Response(content=generate_latest(registry), media_type="text/plain; version=0.0.4; charset=utf-8")
