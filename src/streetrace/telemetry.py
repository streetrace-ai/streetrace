"""OpenTelemetry telemetry configuration for StreetRace."""

import os


def init_telemetry() -> object | None:
    """Initialize OpenTelemetry tracing if configured.

    Returns:
        TracerProvider if telemetry is configured, None otherwise

    """
    # Check if OTEL is configured
    traces_endpoint = os.environ.get("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT")
    otlp_endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT")
    endpoint = traces_endpoint or otlp_endpoint
    if not endpoint:
        return None

    # Import OpenTelemetry modules only when needed
    from openinference.instrumentation.google_adk import GoogleADKInstrumentor
    from opentelemetry import trace
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    from opentelemetry.sdk import trace as trace_sdk
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor

    # Create tracer provider
    tracer_provider = trace_sdk.TracerProvider()

    # Configure OTLP exporter
    headers = {}
    if auth_header := os.environ.get("OTEL_EXPORTER_OTLP_HEADERS"):
        # Parse headers in format "key1=value1,key2=value2"
        for header in auth_header.split(","):
            if "=" in header:
                key, value = header.split("=", 1)
                headers[key.strip()] = value.strip()

    exporter = OTLPSpanExporter(
        endpoint=endpoint,
        headers=headers,
    )

    # Add span processor
    tracer_provider.add_span_processor(SimpleSpanProcessor(exporter))

    GoogleADKInstrumentor().instrument(tracer_provider=tracer_provider)

    # Set as global tracer provider
    trace.set_tracer_provider(tracer_provider)

    return tracer_provider
