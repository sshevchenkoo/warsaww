"""Observability wiring: Prometheus `/metrics` + OpenTelemetry traces.

The audit found the app was completely uninstrumented — the OTel Collector,
Prometheus scrape job, and Tempo backend were all deployed but received
nothing. This module closes that gap.

Two independent signals:
- **Metrics** (pull): a Prometheus `/metrics` endpoint via
  prometheus-fastapi-instrumentator. Always on — it is cheap and local dev can
  scrape it too.
- **Traces** (push): OpenTelemetry spans exported over OTLP/gRPC to the
  collector. Enabled only when ``OTEL_EXPORTER_OTLP_ENDPOINT`` is set, so local
  dev without a collector stays quiet instead of logging export failures.

Everything is wrapped defensively: a missing optional package or a bad endpoint
must never stop the API from serving.
"""

import logging
import os

from fastapi import FastAPI

log = logging.getLogger(__name__)


def setup_observability(app: FastAPI) -> None:
    """Attach metrics and (when configured) tracing to the FastAPI app."""
    _setup_metrics(app)
    _setup_tracing(app)


def _setup_metrics(app: FastAPI) -> None:
    try:
        from prometheus_fastapi_instrumentator import Instrumentator
    except ImportError:
        log.warning("prometheus-fastapi-instrumentator not installed — /metrics disabled")
        return
    # Exposes request count/latency/in-progress histograms at /metrics, kept out
    # of the OpenAPI schema so it doesn't clutter the public API surface.
    Instrumentator().instrument(app).expose(
        app, endpoint="/metrics", include_in_schema=False
    )
    log.info("Prometheus metrics exposed at /metrics")


def _setup_tracing(app: FastAPI) -> None:
    endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
    if not endpoint:
        log.info("OTEL_EXPORTER_OTLP_ENDPOINT not set — tracing disabled")
        return
    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
    except ImportError:
        log.warning("opentelemetry packages not installed — tracing disabled")
        return

    service_name = os.getenv("OTEL_SERVICE_NAME", "warsaw-events-api")
    provider = TracerProvider(resource=Resource.create({"service.name": service_name}))
    # OTLPSpanExporter() reads OTEL_EXPORTER_OTLP_ENDPOINT from the environment.
    provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
    trace.set_tracer_provider(provider)

    FastAPIInstrumentor.instrument_app(app)
    _instrument_outbound()
    log.info("OpenTelemetry tracing enabled (service=%s) → %s", service_name, endpoint)


def _instrument_outbound() -> None:
    """Trace outbound DB queries and HTTP calls (best-effort)."""
    try:
        from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor

        from app.catalog.db import engine

        SQLAlchemyInstrumentor().instrument(engine=engine)
    except Exception:
        log.debug("SQLAlchemy instrumentation skipped", exc_info=True)
    try:
        from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor

        HTTPXClientInstrumentor().instrument()
    except Exception:
        log.debug("httpx instrumentation skipped", exc_info=True)
