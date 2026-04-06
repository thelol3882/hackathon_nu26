import os
from collections.abc import Callable

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.instrumentation.redis import RedisInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.trace.sampling import TraceIdRatioBased


def _env(service_name: str, key: str, default: str) -> str:
    prefix = service_name.upper().replace("-", "_")
    return os.environ.get(f"{prefix}_{key}", os.environ.get(key, default))


def setup_tracing(service_name: str, otlp_endpoint: str) -> Callable[[], None]:
    # Default 5% sampling to cap Jaeger memory; override via OTEL_TRACE_SAMPLE_RATE.
    sample_rate = float(_env(service_name, "OTEL_TRACE_SAMPLE_RATE", "0.05"))
    sampler = TraceIdRatioBased(sample_rate)

    resource = Resource.create({"service.name": service_name})
    provider = TracerProvider(resource=resource, sampler=sampler)

    exporter = OTLPSpanExporter(endpoint=otlp_endpoint, insecure=True)
    # Bounded queue/batch to cap memory under high throughput.
    processor = BatchSpanProcessor(
        exporter,
        max_queue_size=2048,
        max_export_batch_size=256,
        schedule_delay_millis=5000,
    )
    provider.add_span_processor(processor)

    trace.set_tracer_provider(provider)

    # Optional instrumentors — skip if the library isn't installed
    # (e.g. ws-server has no asyncpg/grpc deps).
    try:
        from opentelemetry.instrumentation.asyncpg import AsyncPGInstrumentor

        AsyncPGInstrumentor().instrument()
    except ImportError:
        pass

    try:
        from opentelemetry.instrumentation.grpc import GrpcAioInstrumentorServer

        GrpcAioInstrumentorServer().instrument()
    except ImportError:
        pass

    RedisInstrumentor().instrument()
    HTTPXClientInstrumentor().instrument()

    def shutdown() -> None:
        provider.shutdown()

    return shutdown
