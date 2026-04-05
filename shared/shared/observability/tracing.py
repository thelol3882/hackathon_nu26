import os
from collections.abc import Callable

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.asyncpg import AsyncPGInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.instrumentation.redis import RedisInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.trace.sampling import TraceIdRatioBased


def setup_tracing(service_name: str, otlp_endpoint: str) -> Callable[[], None]:
    # Sample only a fraction of traces to keep Jaeger memory usage low.
    # Default 5% — override via OTEL_TRACE_SAMPLE_RATE (0.0–1.0).
    sample_rate = float(os.environ.get("OTEL_TRACE_SAMPLE_RATE", "0.05"))
    sampler = TraceIdRatioBased(sample_rate)

    resource = Resource.create({"service.name": service_name})
    provider = TracerProvider(resource=resource, sampler=sampler)

    exporter = OTLPSpanExporter(endpoint=otlp_endpoint, insecure=True)
    # Limit batch size and queue to cap memory usage under high throughput.
    processor = BatchSpanProcessor(
        exporter,
        max_queue_size=2048,
        max_export_batch_size=256,
        schedule_delay_millis=5000,
    )
    provider.add_span_processor(processor)

    trace.set_tracer_provider(provider)

    AsyncPGInstrumentor().instrument()
    RedisInstrumentor().instrument()
    HTTPXClientInstrumentor().instrument()

    def shutdown() -> None:
        provider.shutdown()

    return shutdown
