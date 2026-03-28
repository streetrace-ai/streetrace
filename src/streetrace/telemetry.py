"""OpenTelemetry telemetry configuration for StreetRace."""

import os


def init_telemetry() -> object | None:
    """Initialize OpenTelemetry tracing if configured.

    Returns:
        TracerProvider if telemetry is configured, None otherwise

    """
    # Check if OTEL is enabled
    if os.environ.get("OTEL_ENABLED", "false").lower() != "true":
        return None

    # Check if OTEL is configured
    if not (
        os.environ.get("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT")
        or os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT")
    ):
        return None

    # Import OpenTelemetry modules only when needed
    from openinference.instrumentation.google_adk import GoogleADKInstrumentor
    from opentelemetry import trace
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    from opentelemetry.instrumentation.mcp import McpInstrumentor
    from opentelemetry.sdk import trace as trace_sdk
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor

    # Create tracer provider
    tracer_provider = trace_sdk.TracerProvider()

    # OTLPSpanExporter natively reads OTEL_EXPORTER_OTLP_ENDPOINT (appends
    # /v1/traces) and OTEL_EXPORTER_OTLP_HEADERS from the environment.
    exporter = OTLPSpanExporter()

    # Add span processor
    tracer_provider.add_span_processor(SimpleSpanProcessor(exporter))

    GoogleADKInstrumentor().instrument(tracer_provider=tracer_provider)
    McpInstrumentor().instrument(tracer_provider=tracer_provider)  # type: ignore[no-untyped-call]

    # Set as global tracer provider
    trace.set_tracer_provider(tracer_provider)

    return tracer_provider
