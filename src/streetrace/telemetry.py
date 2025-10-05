"""OpenTelemetry telemetry configuration for StreetRace."""

import os
from typing import Optional

from openinference.instrumentation.google_adk import GoogleADKInstrumentor
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk import trace as trace_sdk
from opentelemetry.sdk.trace.export import ConsoleSpanExporter, SimpleSpanProcessor


def init_telemetry() -> Optional[trace_sdk.TracerProvider]:
    """Initialize OpenTelemetry tracing if configured.
    
    Returns:
        TracerProvider if telemetry is configured, None otherwise
    """
    # Check if OTEL is configured
    endpoint = os.environ.get("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT") or os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT")
    if not endpoint:
        return None
    
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
        headers=headers
    )
    
    # Add span processor
    #tracer_provider.add_span_processor(SimpleSpanProcessor(exporter))
    tracer_provider.add_span_processor(SimpleSpanProcessor(exporter))

    # Set as global tracer provider
    trace.set_tracer_provider(tracer_provider)
    
    return tracer_provider