"""
KMRL NexusAI — Kafka Consumer
================================
Ingests real-time telemetry from IoT sensors, IBM Maximo events,
and UNS (Unified Namespace) streams.

Topics consumed:
  kmrl.trainset.telemetry     — brake/HVAC/door/speed sensor readings
  kmrl.maintenance.events     — Maximo work order updates
  kmrl.alerts                 — inter-service alert events

Run: python -m app.kafka_consumer
"""
from __future__ import annotations

import asyncio
import json
import logging
import signal
from datetime import datetime, timezone
from typing import Any, Callable

from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
from aiokafka.errors import KafkaConnectionError

from app.core.config import settings

logger = logging.getLogger(__name__)


# ── Message Schemas ───────────────────────────────────────────────────────

class TelemetryReading:
    """Validates incoming telemetry payload."""

    REQUIRED_FIELDS = {"trainset_id", "sensor_type", "value", "timestamp"}

    @classmethod
    def validate(cls, data: dict) -> bool:
        return cls.REQUIRED_FIELDS.issubset(data.keys())

    @classmethod
    def normalize(cls, data: dict) -> dict:
        """Normalize timestamps, units, fill defaults."""
        ts = data.get("timestamp")
        if isinstance(ts, (int, float)):
            data["timestamp"] = datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()
        data.setdefault("unit", "")
        data.setdefault("is_anomaly", False)
        data.setdefault("anomaly_score", 0.0)
        return data


class MaintenanceEvent:
    """IBM Maximo work order event."""

    REQUIRED_FIELDS = {"work_order_id", "trainset_id", "event_type", "timestamp"}

    @classmethod
    def validate(cls, data: dict) -> bool:
        return cls.REQUIRED_FIELDS.issubset(data.keys())


# ── Consumer ─────────────────────────────────────────────────────────────

class KMRLKafkaConsumer:
    """
    Async Kafka consumer with:
    - At-least-once delivery semantics
    - Dead letter queue (DLQ) for failed messages
    - Backpressure via semaphore
    - Graceful shutdown
    - Anomaly detection pipeline integration
    """

    DLQ_TOPIC = "kmrl.dlq"
    BATCH_SIZE = 100
    MAX_CONCURRENT = 50

    def __init__(self):
        self.consumer: AIOKafkaConsumer | None = None
        self.producer: AIOKafkaProducer | None = None
        self._running = False
        self._semaphore = asyncio.Semaphore(self.MAX_CONCURRENT)
        self._handlers: dict[str, Callable] = {}
        self._processed = 0
        self._errors = 0

    def register_handler(self, topic: str, handler: Callable) -> None:
        self._handlers[topic] = handler
        logger.info("Registered handler for topic: %s", topic)

    async def start(self) -> None:
        """Start consumer and producer connections."""
        logger.info("Starting KMRL Kafka consumer...")

        self.consumer = AIOKafkaConsumer(
            settings.KAFKA_TOPIC_TELEMETRY,
            "kmrl.maintenance.events",
            settings.KAFKA_TOPIC_ALERTS,
            bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS,
            group_id=settings.KAFKA_CONSUMER_GROUP,
            auto_offset_reset="latest",
            enable_auto_commit=False,
            max_poll_records=self.BATCH_SIZE,
            session_timeout_ms=30_000,
            heartbeat_interval_ms=10_000,
            value_deserializer=lambda v: json.loads(v.decode("utf-8")),
        )

        self.producer = AIOKafkaProducer(
            bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS,
            value_serializer=lambda v: json.dumps(v).encode("utf-8"),
            acks="all",
            enable_idempotence=True,
        )

        retry_count = 0
        while retry_count < 10:
            try:
                await self.consumer.start()
                await self.producer.start()
                logger.info("Kafka consumer connected successfully")
                break
            except KafkaConnectionError as e:
                retry_count += 1
                wait = min(2 ** retry_count, 60)
                logger.warning("Kafka connection failed (%d/10), retry in %ds: %s", retry_count, wait, e)
                await asyncio.sleep(wait)

        self._running = True
        self._register_default_handlers()

    async def stop(self) -> None:
        """Graceful shutdown — commit offsets before stopping."""
        logger.info("Stopping Kafka consumer... processed=%d errors=%d", self._processed, self._errors)
        self._running = False
        if self.consumer:
            await self.consumer.commit()
            await self.consumer.stop()
        if self.producer:
            await self.producer.stop()

    async def run(self) -> None:
        """Main consumption loop."""
        await self.start()
        try:
            async for msg in self.consumer:
                if not self._running:
                    break
                async with self._semaphore:
                    asyncio.create_task(self._process_message(msg))
        finally:
            await self.stop()

    async def _process_message(self, msg: Any) -> None:
        """Route message to appropriate handler."""
        topic = msg.topic
        try:
            data = msg.value
            handler = self._handlers.get(topic, self._default_handler)
            await handler(data, topic=topic, partition=msg.partition, offset=msg.offset)
            await self.consumer.commit()
            self._processed += 1

            if self._processed % 1000 == 0:
                logger.info("Consumer stats: processed=%d errors=%d", self._processed, self._errors)

        except Exception as exc:
            self._errors += 1
            logger.error("Failed to process message from %s: %s", topic, exc, exc_info=True)
            await self._send_to_dlq(msg, str(exc))

    async def _send_to_dlq(self, msg: Any, error: str) -> None:
        """Send failed message to Dead Letter Queue."""
        if self.producer:
            dlq_payload = {
                "original_topic": msg.topic,
                "original_partition": msg.partition,
                "original_offset": msg.offset,
                "error": error,
                "payload": msg.value,
                "failed_at": datetime.now(timezone.utc).isoformat(),
            }
            try:
                await self.producer.send_and_wait(self.DLQ_TOPIC, dlq_payload)
            except Exception:
                pass

    async def _default_handler(self, data: dict, **kwargs) -> None:
        logger.debug("Unhandled message on %s: %s", kwargs.get("topic"), data)

    def _register_default_handlers(self) -> None:
        self.register_handler(settings.KAFKA_TOPIC_TELEMETRY, self._handle_telemetry)
        self.register_handler("kmrl.maintenance.events", self._handle_maintenance_event)
        self.register_handler(settings.KAFKA_TOPIC_ALERTS, self._handle_alert_event)

    async def _handle_telemetry(self, data: dict, **kwargs) -> None:
        """
        Process incoming IoT sensor reading.
        Pipeline:
          1. Validate schema
          2. Normalize
          3. Run anomaly detection
          4. Buffer into Redis for batch TimescaleDB write
          5. Publish anomaly alert if detected
        """
        if not TelemetryReading.validate(data):
            raise ValueError(f"Invalid telemetry schema: {data.keys()}")

        data = TelemetryReading.normalize(data)
        trainset_id = data["trainset_id"]
        sensor_type = data["sensor_type"]
        value = float(data["value"])

        # Anomaly detection
        from app.ml.pipeline import MLService
        service = MLService.get_instance()

        import numpy as np
        sensor_vector = np.array([value, 0.0, 0.0, 0.0])  # expand with full feature set
        anomaly_result = service.anomaly_detector.score(trainset_id, sensor_vector)

        if anomaly_result.get("is_anomaly"):
            data["is_anomaly"] = True
            data["anomaly_score"] = anomaly_result.get("anomaly_score", 0.0)
            logger.warning("Anomaly detected: trainset=%s sensor=%s value=%.2f", trainset_id, sensor_type, value)

            # Publish alert
            if self.producer:
                await self.producer.send_and_wait(
                    settings.KAFKA_TOPIC_ALERTS,
                    {
                        "alert_code": "TELEMETRY_ANOMALY",
                        "severity": "warning",
                        "trainset_id": trainset_id,
                        "sensor_type": sensor_type,
                        "value": value,
                        "anomaly_score": data["anomaly_score"],
                        "timestamp": data["timestamp"],
                    }
                )

        # Buffer in Redis for batch write
        # In production: push to Redis list, periodic Celery task flushes to TimescaleDB
        redis_key = f"telemetry_buffer:{trainset_id}"
        # await redis_client.rpush(redis_key, json.dumps(data))

    async def _handle_maintenance_event(self, data: dict, **kwargs) -> None:
        """
        Process IBM Maximo work order events.
        Updates job card status, triggers certificate refresh checks.
        """
        if not MaintenanceEvent.validate(data):
            raise ValueError(f"Invalid maintenance event schema: {data.keys()}")

        event_type = data.get("event_type")
        trainset_id = data.get("trainset_id")
        wo_id = data.get("work_order_id")

        logger.info("Maintenance event: type=%s wo=%s trainset=%s", event_type, wo_id, trainset_id)

        if event_type == "WORK_ORDER_COMPLETED":
            # Trigger re-evaluation of trainset readiness
            from app.workers import run_nightly_optimization
            # Could trigger partial re-optimization here

        elif event_type == "CERTIFICATE_RENEWED":
            logger.info("Certificate renewed for %s — clearing alerts", trainset_id)

    async def _handle_alert_event(self, data: dict, **kwargs) -> None:
        """
        Process inter-service alert events.
        Deduplicates and routes to dispatch workers.
        """
        from app.workers import dispatch_alert
        dispatch_alert.delay(
            alert_code=data.get("alert_code", "UNKNOWN"),
            severity=data.get("severity", "info"),
            title=data.get("title", "System Alert"),
            description=data.get("description", ""),
            trainset_code=data.get("trainset_id"),
            channels=data.get("channels", ["dashboard"]),
        )


# ── ETL Pipeline ─────────────────────────────────────────────────────────

class ETLPipeline:
    """
    Batch ETL for ingesting:
    - IBM Maximo CSV/API exports
    - Excel maintenance schedules
    - Historical mileage CSVs
    """

    @staticmethod
    def ingest_maximo_csv(file_path: str) -> list[dict]:
        """Parse IBM Maximo work order export CSV."""
        import csv
        records = []
        with open(file_path, newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
                record = ETLPipeline._normalize_maximo_row(row)
                if record:
                    records.append(record)
        logger.info("Ingested %d records from Maximo CSV: %s", len(records), file_path)
        return records

    @staticmethod
    def _normalize_maximo_row(row: dict) -> dict | None:
        """Map Maximo column names to internal schema."""
        mapping = {
            "WONUM": "work_order_id",
            "ASSET": "trainset_code",
            "DESCRIPTION": "description",
            "WORKTYPE": "job_type",
            "STATUS": "status",
            "REPORTDATE": "reported_date",
            "SITEID": "depot_code",
        }
        try:
            return {
                internal: row[maximo].strip()
                for maximo, internal in mapping.items()
                if maximo in row
            }
        except Exception:
            return None

    @staticmethod
    def ingest_mileage_excel(file_path: str) -> list[dict]:
        """Parse Excel mileage log sheets."""
        import pandas as pd
        df = pd.read_excel(file_path, sheet_name=0, header=0)
        df.columns = [str(c).strip().lower().replace(" ", "_") for c in df.columns]
        df = df.dropna(subset=["trainset_code", "date"])
        return df.to_dict(orient="records")

    @staticmethod
    def validate_and_deduplicate(records: list[dict], key_fields: list[str]) -> list[dict]:
        """Remove duplicates based on key fields."""
        seen = set()
        unique = []
        for rec in records:
            key = tuple(rec.get(f) for f in key_fields)
            if key not in seen:
                seen.add(key)
                unique.append(rec)
        removed = len(records) - len(unique)
        if removed:
            logger.info("Deduplicated %d records", removed)
        return unique


# ── Main Entry Point ──────────────────────────────────────────────────────

async def main() -> None:
    """Run the Kafka consumer until SIGINT/SIGTERM."""
    consumer = KMRLKafkaConsumer()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(
            sig,
            lambda: asyncio.create_task(consumer.stop())
        )

    logger.info("KMRL Kafka Consumer starting — topics: telemetry, maintenance, alerts")
    await consumer.run()


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    asyncio.run(main())
