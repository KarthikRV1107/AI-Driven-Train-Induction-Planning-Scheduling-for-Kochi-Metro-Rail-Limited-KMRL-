"""
KMRL NexusAI — Observability Layer
=====================================
OpenTelemetry instrumentation with Jaeger export.

Traces:
  - Every FastAPI request (auto-instrumented)
  - OR-Tools optimization solve duration
  - ML model inference latency
  - Kafka consumer processing
  - Database query spans
  - Celery task execution

Metrics (Prometheus):
  - Fleet availability gauge
  - Optimization solve time histogram
  - ML prediction latency histogram
  - Kafka consumer lag
  - Active WebSocket connections
  - Per-endpoint error rates

Logs:
  - Structured JSON via structlog
  - Correlated with trace IDs
  - Severity-aware sampling
"""
from __future__ import annotations

import logging
import time
from contextlib import contextmanager
from functools import wraps
from typing import Any, Callable

from app.core.config import settings

logger = logging.getLogger(__name__)

# ── OpenTelemetry Setup ───────────────────────────────────────────────────

_tracer = None
_meter  = None

def init_telemetry(app=None) -> None:
    """
    Initialize OpenTelemetry with OTLP export to Jaeger.
    Call once at application startup.
    """
    global _tracer, _meter
    try:
        from opentelemetry import metrics, trace
        from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import (
            OTLPMetricExporter,
        )
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
            OTLPSpanExporter,
        )
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
        from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
        from opentelemetry.sdk.metrics import MeterProvider
        from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
        from opentelemetry.sdk.resources import SERVICE_NAME, SERVICE_VERSION, Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
        from opentelemetry.sdk.trace.sampling import ParentBased, TraceIdRatioBased

        OTLP_ENDPOINT = getattr(settings, "OTLP_ENDPOINT", "http://jaeger:4317")

        resource = Resource.create({
            SERVICE_NAME:    "kmrl-nexusai-api",
            SERVICE_VERSION: settings.APP_VERSION,
            "deployment.environment": settings.ENVIRONMENT,
            "service.namespace":      "kmrl",
        })

        # ── Tracer Provider ─────────────────────────────────────────────
        sampler = ParentBased(
            TraceIdRatioBased(1.0 if settings.ENVIRONMENT != "production" else 0.1)
        )
        tracer_provider = TracerProvider(resource=resource, sampler=sampler)
        tracer_provider.add_span_processor(
            BatchSpanProcessor(OTLPSpanExporter(endpoint=OTLP_ENDPOINT, insecure=True))
        )
        trace.set_tracer_provider(tracer_provider)
        _tracer = trace.get_tracer("kmrl.nexusai", settings.APP_VERSION)

        # ── Meter Provider ──────────────────────────────────────────────
        metric_reader   = PeriodicExportingMetricReader(
            OTLPMetricExporter(endpoint=OTLP_ENDPOINT, insecure=True),
            export_interval_millis=30_000,
        )
        meter_provider  = MeterProvider(resource=resource, metric_readers=[metric_reader])
        metrics.set_meter_provider(meter_provider)
        _meter = metrics.get_meter("kmrl.nexusai", settings.APP_VERSION)

        # ── Auto-instrument libraries ───────────────────────────────────
        if app is not None:
            FastAPIInstrumentor.instrument_app(app)
        HTTPXClientInstrumentor().instrument()
        SQLAlchemyInstrumentor().instrument()

        logger.info("OpenTelemetry initialized → %s", OTLP_ENDPOINT)

    except ImportError as exc:
        logger.warning("OpenTelemetry packages not installed, telemetry disabled: %s", exc)
    except Exception as exc:
        logger.error("Telemetry init failed (non-fatal): %s", exc)


def get_tracer():
    global _tracer
    if _tracer is None:
        try:
            from opentelemetry import trace
            _tracer = trace.get_tracer("kmrl.nexusai")
        except ImportError:
            return _NoOpTracer()
    return _tracer


# ── Span Context Manager ──────────────────────────────────────────────────

@contextmanager
def trace_span(name: str, attributes: dict[str, Any] | None = None):
    """Context manager for manual span creation."""
    tracer = get_tracer()
    try:
        from opentelemetry import trace
        with tracer.start_as_current_span(name) as span:
            if attributes:
                for k, v in attributes.items():
                    span.set_attribute(k, str(v))
            yield span
    except (ImportError, AttributeError):
        yield _NoOpSpan()


# ── Decorator ────────────────────────────────────────────────────────────

def traced(span_name: str | None = None, attributes: dict | None = None):
    """Decorator to trace a function call."""
    def decorator(fn: Callable) -> Callable:
        @wraps(fn)
        async def async_wrapper(*args, **kwargs):
            name = span_name or f"{fn.__module__}.{fn.__qualname__}"
            with trace_span(name, attributes) as span:
                start = time.perf_counter()
                try:
                    result = await fn(*args, **kwargs)
                    return result
                except Exception as exc:
                    try:
                        span.record_exception(exc)
                        span.set_status(
                            __import__("opentelemetry.trace", fromlist=["StatusCode"]).StatusCode.ERROR
                        )
                    except Exception:
                        pass
                    raise
                finally:
                    elapsed = (time.perf_counter() - start) * 1000
                    try:
                        span.set_attribute("duration_ms", round(elapsed, 2))
                    except Exception:
                        pass

        @wraps(fn)
        def sync_wrapper(*args, **kwargs):
            name = span_name or f"{fn.__module__}.{fn.__qualname__}"
            with trace_span(name, attributes):
                return fn(*args, **kwargs)

        import asyncio
        return async_wrapper if asyncio.iscoroutinefunction(fn) else sync_wrapper
    return decorator


# ── Prometheus Metrics ────────────────────────────────────────────────────

class KMRLMetrics:
    """
    Application-specific Prometheus metrics.
    Registered via prometheus_fastapi_instrumentator on startup.
    """
    _instance: "KMRLMetrics | None" = None

    def __init__(self):
        try:
            from prometheus_client import Counter, Gauge, Histogram, Summary

            # Fleet metrics
            self.fleet_availability = Gauge(
                "kmrl_fleet_availability_pct",
                "Current fleet availability percentage",
                ["depot"],
            )
            self.revenue_service_count = Gauge(
                "kmrl_revenue_service_count",
                "Number of trainsets in revenue service",
                ["depot"],
            )
            self.active_alerts = Gauge(
                "kmrl_active_alerts_total",
                "Number of unacknowledged alerts",
                ["severity"],
            )

            # Optimization metrics
            self.optimization_duration = Histogram(
                "kmrl_optimization_duration_seconds",
                "Time taken to run the induction optimizer",
                ["status", "depot"],
                buckets=[0.1, 0.5, 1, 2, 5, 10, 30],
            )
            self.optimization_score = Gauge(
                "kmrl_optimization_score",
                "Latest optimizer score (0-100)",
                ["depot"],
            )
            self.shunting_ops_total = Gauge(
                "kmrl_shunting_ops_tonight",
                "Number of shunting operations planned tonight",
                ["depot"],
            )

            # ML metrics
            self.ml_prediction_duration = Histogram(
                "kmrl_ml_prediction_duration_seconds",
                "ML inference latency",
                ["model", "system"],
                buckets=[0.01, 0.05, 0.1, 0.5, 1.0],
            )
            self.ml_failure_risk = Gauge(
                "kmrl_ml_failure_risk",
                "AI-predicted failure risk per trainset",
                ["trainset_code", "system"],
            )
            self.model_drift_psi = Gauge(
                "kmrl_model_drift_psi",
                "Population Stability Index for drift detection",
                ["model"],
            )

            # Kafka metrics
            self.kafka_messages_processed = Counter(
                "kmrl_kafka_messages_processed_total",
                "Total Kafka messages processed",
                ["topic", "status"],
            )
            self.kafka_consumer_lag = Gauge(
                "kmrl_kafka_consumer_lag",
                "Kafka consumer lag per topic",
                ["topic"],
            )

            # WebSocket metrics
            self.websocket_connections = Gauge(
                "kmrl_websocket_connections_active",
                "Active WebSocket connections",
            )

            # RL agent metrics
            self.rl_agent_epsilon = Gauge(
                "kmrl_rl_agent_epsilon",
                "Current exploration rate of RL agent",
            )
            self.rl_reward = Gauge(
                "kmrl_rl_last_reward",
                "Last reward signal from operational outcome",
            )

            self._available = True
            logger.info("Prometheus metrics registered")

        except ImportError:
            self._available = False
            logger.warning("prometheus_client not installed, metrics disabled")

    @classmethod
    def get(cls) -> "KMRLMetrics":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def record_optimization(
        self,
        depot: str,
        duration_s: float,
        score: float,
        status: str,
        shunting_ops: int,
    ) -> None:
        if not self._available: return
        self.optimization_duration.labels(status=status, depot=depot).observe(duration_s)
        self.optimization_score.labels(depot=depot).set(score)
        self.shunting_ops_total.labels(depot=depot).set(shunting_ops)

    def record_fleet_state(self, depot: str, availability: float, revenue: int) -> None:
        if not self._available: return
        self.fleet_availability.labels(depot=depot).set(availability)
        self.revenue_service_count.labels(depot=depot).set(revenue)

    def record_ml_prediction(
        self, model: str, system: str, duration_s: float,
        trainset_code: str, risk: float,
    ) -> None:
        if not self._available: return
        self.ml_prediction_duration.labels(model=model, system=system).observe(duration_s)
        self.ml_failure_risk.labels(trainset_code=trainset_code, system=system).set(risk)

    def record_kafka_message(self, topic: str, status: str = "success") -> None:
        if not self._available: return
        self.kafka_messages_processed.labels(topic=topic, status=status).inc()

    def set_websocket_count(self, count: int) -> None:
        if not self._available: return
        self.websocket_connections.set(count)

    def record_rl_update(self, epsilon: float, reward: float) -> None:
        if not self._available: return
        self.rl_agent_epsilon.set(epsilon)
        self.rl_reward.set(reward)


# ── Structured Logging ────────────────────────────────────────────────────

def configure_structured_logging(level: str = "INFO") -> None:
    """
    Configure structlog for JSON-formatted structured logging.
    Correlates log entries with OpenTelemetry trace IDs.
    """
    try:
        import structlog

        def add_trace_context(logger, method, event_dict):
            """Inject current trace/span IDs into every log record."""
            try:
                from opentelemetry import trace
                span = trace.get_current_span()
                ctx  = span.get_span_context()
                if ctx.is_valid:
                    event_dict["trace_id"] = format(ctx.trace_id, "032x")
                    event_dict["span_id"]  = format(ctx.span_id,  "016x")
            except Exception:
                pass
            return event_dict

        structlog.configure(
            processors=[
                structlog.stdlib.filter_by_level,
                structlog.stdlib.add_logger_name,
                structlog.stdlib.add_log_level,
                structlog.stdlib.PositionalArgumentsFormatter(),
                structlog.processors.TimeStamper(fmt="iso"),
                add_trace_context,
                structlog.processors.StackInfoRenderer(),
                structlog.processors.format_exc_info,
                structlog.processors.UnicodeDecoder(),
                structlog.processors.JSONRenderer(),
            ],
            context_class=dict,
            logger_factory=structlog.stdlib.LoggerFactory(),
            wrapper_class=structlog.stdlib.BoundLogger,
            cache_logger_on_first_use=True,
        )
        logging.basicConfig(
            format="%(message)s",
            level=getattr(logging, level.upper(), logging.INFO),
        )
        logger.info("Structured logging configured", level=level)

    except ImportError:
        logging.basicConfig(
            level=getattr(logging, level.upper(), logging.INFO),
            format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        )


# ── No-Op Implementations (graceful degradation) ─────────────────────────

class _NoOpSpan:
    def set_attribute(self, *a, **kw): pass
    def record_exception(self, *a, **kw): pass
    def set_status(self, *a, **kw): pass
    def __enter__(self): return self
    def __exit__(self, *a): pass

class _NoOpTracer:
    def start_as_current_span(self, *a, **kw):
        from contextlib import contextmanager
        @contextmanager
        def _ctx():
            yield _NoOpSpan()
        return _ctx()


# ── Grafana Dashboard JSON ────────────────────────────────────────────────
# Exported as a dict to be provisioned via grafana-dashboards volume

GRAFANA_DASHBOARD = {
    "title": "KMRL NexusAI — Operations",
    "uid":   "kmrl-ops",
    "schemaVersion": 39,
    "tags": ["kmrl", "railway", "ai"],
    "panels": [
        {
            "id": 1, "title": "Fleet Availability %",
            "type": "stat",
            "targets": [{"expr": "kmrl_fleet_availability_pct"}],
            "fieldConfig": {"defaults": {"thresholds": {"steps": [
                {"value": 0,  "color": "red"},
                {"value": 85, "color": "yellow"},
                {"value": 92, "color": "green"},
            ]}, "unit": "percent"}},
        },
        {
            "id": 2, "title": "Revenue Service Count",
            "type": "stat",
            "targets": [{"expr": "kmrl_revenue_service_count"}],
        },
        {
            "id": 3, "title": "Optimizer Solve Duration (p95)",
            "type": "timeseries",
            "targets": [{"expr": "histogram_quantile(0.95, rate(kmrl_optimization_duration_seconds_bucket[5m]))"}],
        },
        {
            "id": 4, "title": "Active Alerts",
            "type": "stat",
            "targets": [{"expr": "sum(kmrl_active_alerts_total) by (severity)"}],
        },
        {
            "id": 5, "title": "ML Prediction Latency (p95)",
            "type": "timeseries",
            "targets": [{"expr": "histogram_quantile(0.95, rate(kmrl_ml_prediction_duration_seconds_bucket[10m]))"}],
        },
        {
            "id": 6, "title": "Kafka Consumer Lag",
            "type": "timeseries",
            "targets": [{"expr": "kmrl_kafka_consumer_lag"}],
        },
        {
            "id": 7, "title": "RL Agent Epsilon",
            "type": "timeseries",
            "targets": [{"expr": "kmrl_rl_agent_epsilon"}],
        },
        {
            "id": 8, "title": "Model Drift PSI",
            "type": "gauge",
            "targets": [{"expr": "kmrl_model_drift_psi"}],
            "fieldConfig": {"defaults": {"thresholds": {"steps": [
                {"value": 0,    "color": "green"},
                {"value": 0.1,  "color": "yellow"},
                {"value": 0.2,  "color": "red"},
            ]}}},
        },
    ],
    "refresh": "30s",
    "time": {"from": "now-3h", "to": "now"},
}
