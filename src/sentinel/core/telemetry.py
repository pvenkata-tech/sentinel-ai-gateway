"""OpenTelemetry and observability setup."""

import logging
from typing import Optional

from opentelemetry import metrics, trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.exporter.prometheus import PrometheusMetricReader
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor

from sentinel.core.config import settings

logger = logging.getLogger(__name__)


class TelemetryManager:
    """Manages OpenTelemetry initialization and configuration."""

    def __init__(self) -> None:
        """Initialize telemetry manager."""
        self._tracer_provider: Optional[TracerProvider] = None
        self._meter_provider: Optional[MeterProvider] = None
        self._initialized = False

    def initialize(self) -> None:
        """Initialize OpenTelemetry tracing and metrics."""
        if self._initialized:
            logger.warning("Telemetry already initialized")
            return

        if not settings.otel_enabled:
            logger.info("OpenTelemetry disabled in configuration")
            return

        try:
            # Setup resource with service name
            resource = Resource(
                attributes={
                    SERVICE_NAME: settings.otel_service_name,
                    "environment": settings.environment,
                    "version": settings.version,
                }
            )

            # Setup Trace Provider
            trace_exporter = OTLPSpanExporter(
                endpoint=settings.otel_exporter_otlp_endpoint,
            )
            self._tracer_provider = TracerProvider(resource=resource)
            self._tracer_provider.add_span_processor(
                SimpleSpanProcessor(trace_exporter)
            )
            trace.set_tracer_provider(self._tracer_provider)

            # Setup Metrics Provider
            if settings.prometheus_enabled:
                prometheus_reader = PrometheusMetricReader(
                    prefix="sentinel_",
                )
                self._meter_provider = MeterProvider(
                    resource=resource,
                    metric_readers=[prometheus_reader],
                )
            else:
                self._meter_provider = MeterProvider(resource=resource)

            metrics.set_meter_provider(self._meter_provider)

            # Instrument FastAPI and HTTP client
            # Skip app instrumentation for now as it requires app instance
            # Will be instrumented in main.py
            HTTPXClientInstrumentor().instrument()

            self._initialized = True
            logger.info("OpenTelemetry initialized successfully")

        except Exception as e:
            logger.error(f"Failed to initialize OpenTelemetry: {e}")
            raise

    def shutdown(self) -> None:
        """Shutdown telemetry."""
        if self._tracer_provider:
            self._tracer_provider.force_flush()
            self._tracer_provider.shutdown()

        if self._meter_provider:
            self._meter_provider.force_flush()
            self._meter_provider.shutdown()

        self._initialized = False
        logger.info("Telemetry shutdown complete")

    def get_tracer(self, name: str) -> trace.Tracer:
        """Get a tracer instance."""
        if not self._tracer_provider:
            raise RuntimeError("Telemetry not initialized")
        return self._tracer_provider.get_tracer(name)

    def get_meter(self, name: str) -> metrics.Meter:
        """Get a meter instance."""
        if not self._meter_provider:
            raise RuntimeError("Telemetry not initialized")
        return self._meter_provider.get_meter(name)


# Global telemetry manager instance
telemetry_manager = TelemetryManager()
