import os
from collections.abc import Callable

from fastapi import FastAPI

from shared.observability.logging import configure_logging, get_logger
from shared.observability.middleware import RequestContextMiddleware


def setup_observability(app: FastAPI, service_name: str) -> Callable[[], None]:
    configure_logging(service_name)
    logger = get_logger(__name__)

    shutdown_fns: list[Callable[[], None]] = []

    otel_enabled = os.environ.get("OTEL_ENABLED", "true").lower() == "true"
    otlp_endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", "http://jaeger:4317")

    metrics_enabled = os.environ.get("OTEL_METRICS_ENABLED", "false").lower() == "true"

    if otel_enabled:
        from shared.observability.tracing import setup_tracing

        shutdown_fns.append(setup_tracing(service_name, otlp_endpoint))

        if metrics_enabled:
            from shared.observability.metrics import setup_metrics

            shutdown_fns.append(setup_metrics(service_name, otlp_endpoint))
        else:
            logger.info("OTLP metrics export disabled (set OTEL_METRICS_ENABLED=true to enable)")

        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

        FastAPIInstrumentor.instrument_app(app, excluded_urls="metrics,health,ready")
        logger.info("OpenTelemetry enabled", endpoint=otlp_endpoint)
    else:
        logger.info("OpenTelemetry disabled")

    app.add_middleware(RequestContextMiddleware, service_name=service_name)
    logger.info("Observability initialized", service=service_name)

    def shutdown() -> None:
        for fn in shutdown_fns:
            fn()
        logger.info("Observability shut down", service=service_name)

    return shutdown
