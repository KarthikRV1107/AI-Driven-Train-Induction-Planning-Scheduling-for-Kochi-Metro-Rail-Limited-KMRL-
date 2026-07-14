"""
KMRL NexusAI — Feature Store
=============================
Centralised feature computation and caching layer for ML models.
Provides point-in-time correct feature snapshots to avoid training/serving skew.

Architecture:
  - Raw data  → FeatureComputer (transforms) → FeatureStore (Redis cache + Postgres persist)
  - Training: bulk load from Postgres feature_snapshots table
  - Inference: real-time fetch from Redis (< 5ms latency)
"""
from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Any

logger = logging.getLogger(__name__)

# ── Feature Definitions ───────────────────────────────────────────────────

MAINTENANCE_FEATURE_DEFS = {
    "brake_health_pct":             ("float", 0.0, 100.0, "Brake system health percentage"),
    "hvac_health_pct":              ("float", 0.0, 100.0, "HVAC health percentage"),
    "door_health_pct":              ("float", 0.0, 100.0, "Door system health percentage"),
    "total_mileage_km":             ("float", 0.0, 1_000_000.0, "Cumulative mileage in km"),
    "days_since_last_service":      ("int",   0,   365, "Days since last scheduled service"),
    "days_since_ibl":               ("int",   0,   365, "Days since last IBL inspection"),
    "open_job_cards_count":         ("int",   0,   50,  "Open job cards (any priority)"),
    "critical_jobs_count":          ("int",   0,   10,  "Open critical job cards"),
    "vibration_mean_7d":            ("float", 0.0, 20.0, "Mean vibration (g) over 7 days"),
    "vibration_std_7d":             ("float", 0.0, 5.0,  "Std dev vibration over 7 days"),
    "temperature_mean_7d":          ("float", -10.0, 60.0, "Mean wheel bearing temp (°C) 7d"),
    "speed_max_7d":                 ("float", 0.0, 100.0, "Max speed (km/h) over 7 days"),
    "brake_pressure_mean_7d":       ("float", 0.0, 10.0, "Mean brake pressure (bar) 7d"),
    "door_cycle_count_7d":          ("float", 0.0, 5000.0, "Door open/close cycles 7d"),
    "hvac_runtime_hrs_7d":          ("float", 0.0, 168.0, "HVAC runtime hours 7d"),
    "age_years":                    ("float", 0.0, 30.0, "Trainset age in years"),
    "km_since_last_brake_service":  ("float", 0.0, 100_000.0, "km since last brake service"),
    "km_since_last_hvac_service":   ("float", 0.0, 100_000.0, "km since last HVAC service"),
    "brake_events_7d":              ("int",   0,   100,  "Emergency brake applications 7d"),
    "pantograph_wear_pct":          ("float", 0.0, 100.0, "Pantograph wear percentage"),
}

READINESS_FEATURE_DEFS = {
    "brake_health_pct":    ("float", 0.0, 100.0),
    "hvac_health_pct":     ("float", 0.0, 100.0),
    "door_health_pct":     ("float", 0.0, 100.0),
    "daily_km":            ("float", 0.0, 300.0),
    "brake_events":        ("int",   0,   20),
    "door_faults":         ("int",   0,   20),
    "hvac_faults":         ("int",   0,   20),
    "is_cleaning_done":    ("bool",  0,   1),
    "open_jobs":           ("int",   0,   20),
}


@dataclass
class FeatureSnapshot:
    """Immutable point-in-time feature snapshot for one trainset."""
    trainset_id: str
    trainset_code: str
    snapshot_date: str          # ISO date
    features: dict[str, float]
    feature_version: str = "v1.0"
    computed_at: str = ""

    def __post_init__(self):
        if not self.computed_at:
            self.computed_at = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def fingerprint(self) -> str:
        """SHA-256 fingerprint of feature values for deduplication."""
        payload = json.dumps(self.features, sort_keys=True)
        return hashlib.sha256(payload.encode()).hexdigest()[:16]


# ── Feature Computer ──────────────────────────────────────────────────────

class FeatureComputer:
    """
    Transforms raw operational data into ML-ready feature snapshots.
    Handles: telemetry aggregation, mileage deltas, rolling windows.
    """

    def compute_maintenance_features(
        self,
        trainset_data: dict[str, Any],
        telemetry_7d: list[dict[str, Any]],
        mileage_history: list[dict[str, Any]],
    ) -> dict[str, float]:
        """
        Compute all maintenance model features for a single trainset.

        Args:
            trainset_data: current trainset record from DB
            telemetry_7d: list of sensor readings from last 7 days
            mileage_history: list of daily mileage log records

        Returns:
            Feature dict matching MAINTENANCE_FEATURE_DEFS keys
        """
        import numpy as np
        from datetime import date

        features: dict[str, float] = {}

        # Direct mappings from trainset record
        features["brake_health_pct"]    = float(trainset_data.get("brake_health", 90))
        features["hvac_health_pct"]     = float(trainset_data.get("hvac_health", 90))
        features["door_health_pct"]     = float(trainset_data.get("door_health", 90))
        features["total_mileage_km"]    = float(trainset_data.get("total_mileage_km", 0))
        features["open_job_cards_count"]= float(trainset_data.get("open_jobs", 0))
        features["critical_jobs_count"] = float(trainset_data.get("critical_jobs", 0))
        features["pantograph_wear_pct"] = float(trainset_data.get("pantograph_wear", 30))

        # Age
        mfr_year = trainset_data.get("year_of_manufacture", 2015)
        features["age_years"] = float(date.today().year - mfr_year)

        # Days since service
        last_svc = trainset_data.get("last_service_date")
        if last_svc:
            try:
                d = date.fromisoformat(str(last_svc))
                features["days_since_last_service"] = float((date.today() - d).days)
            except Exception:
                features["days_since_last_service"] = 45.0
        else:
            features["days_since_last_service"] = 45.0

        features["days_since_ibl"] = float(trainset_data.get("days_since_ibl", 60))

        # km since last specialized service (estimate if not available)
        total_km = features["total_mileage_km"]
        features["km_since_last_brake_service"] = total_km * 0.15
        features["km_since_last_hvac_service"]  = total_km * 0.20

        # Telemetry aggregations
        if telemetry_7d:
            sensor_groups: dict[str, list[float]] = {}
            for reading in telemetry_7d:
                s_type = reading.get("sensor_type", "")
                val    = float(reading.get("value", 0))
                sensor_groups.setdefault(s_type, []).append(val)

            def agg(s: str, fn: str) -> float:
                vals = sensor_groups.get(s, [0.0])
                return float(getattr(np, fn)(vals))

            features["vibration_mean_7d"]      = agg("vibration", "mean")
            features["vibration_std_7d"]       = agg("vibration", "std")
            features["temperature_mean_7d"]    = agg("temperature", "mean")
            features["speed_max_7d"]           = agg("speed", "max")
            features["brake_pressure_mean_7d"] = agg("brake_pressure", "mean")
            features["door_cycle_count_7d"]    = agg("door_cycle_count", "sum")
            features["hvac_runtime_hrs_7d"]    = agg("hvac_runtime", "sum")
            features["brake_events_7d"]        = float(len([
                r for r in telemetry_7d
                if r.get("sensor_type") == "brake_event"
            ]))
        else:
            # Defaults when no telemetry available
            for key in [
                "vibration_mean_7d", "vibration_std_7d", "temperature_mean_7d",
                "speed_max_7d", "brake_pressure_mean_7d", "door_cycle_count_7d",
                "hvac_runtime_hrs_7d", "brake_events_7d",
            ]:
                features.setdefault(key, 0.0)

        return self._validate_and_clip(features, MAINTENANCE_FEATURE_DEFS)

    def compute_readiness_sequence(
        self,
        daily_records: list[dict[str, Any]],
        seq_len: int = 30,
    ) -> list[dict[str, float]]:
        """
        Build a sequence of daily feature snapshots for the LSTM model.
        Returns list of feature dicts (most recent last), length = seq_len.
        """
        sequence = []
        for record in daily_records[-seq_len:]:
            sequence.append({
                "brake_health_pct": float(record.get("brake_health", 90)),
                "hvac_health_pct":  float(record.get("hvac_health", 90)),
                "door_health_pct":  float(record.get("door_health", 90)),
                "daily_km":         float(record.get("daily_km", 0)),
                "brake_events":     float(record.get("brake_events", 0)),
                "door_faults":      float(record.get("door_faults", 0)),
                "hvac_faults":      float(record.get("hvac_faults", 0)),
                "is_cleaning_done": float(record.get("cleaning_done", True)),
                "open_jobs":        float(record.get("open_jobs", 0)),
            })

        # Pad to seq_len with zeros if not enough history
        while len(sequence) < seq_len:
            sequence.insert(0, {k: 0.0 for k in READINESS_FEATURE_DEFS})

        return sequence[:seq_len]

    @staticmethod
    def _validate_and_clip(
        features: dict[str, float],
        defs: dict[str, tuple],
    ) -> dict[str, float]:
        """Clip all features to their defined valid range and fill missing with 0."""
        clean = {}
        for key, (dtype, lo, hi, *_) in defs.items():
            val = float(features.get(key, 0.0))
            clean[key] = max(float(lo), min(float(hi), val))
        return clean


# ── In-Memory Feature Store (Redis-backed in production) ─────────────────

class FeatureStore:
    """
    Stores and retrieves feature snapshots.
    In production: backed by Redis (inference) + PostgreSQL (training history).
    Here: in-memory dict for development/testing.
    """

    def __init__(self):
        self._store: dict[str, FeatureSnapshot] = {}
        self._history: list[FeatureSnapshot] = []
        self.computer = FeatureComputer()

    def put(self, snapshot: FeatureSnapshot) -> None:
        key = f"{snapshot.trainset_id}:{snapshot.snapshot_date}"
        self._store[key] = snapshot
        self._history.append(snapshot)
        logger.debug("Feature snapshot stored: %s @ %s", snapshot.trainset_code, snapshot.snapshot_date)

    def get(self, trainset_id: str, snapshot_date: str | None = None) -> FeatureSnapshot | None:
        date_key = snapshot_date or str(date.today())
        key = f"{trainset_id}:{date_key}"
        return self._store.get(key)

    def get_latest(self, trainset_id: str) -> FeatureSnapshot | None:
        matching = [
            s for s in self._history
            if s.trainset_id == trainset_id
        ]
        return matching[-1] if matching else None

    def get_training_batch(
        self,
        from_date: date,
        to_date: date,
        trainset_ids: list[str] | None = None,
    ) -> list[FeatureSnapshot]:
        """Fetch all feature snapshots in date range (for model training)."""
        result = []
        for snapshot in self._history:
            d = date.fromisoformat(snapshot.snapshot_date)
            if from_date <= d <= to_date:
                if trainset_ids is None or snapshot.trainset_id in trainset_ids:
                    result.append(snapshot)
        return result

    def compute_and_store(
        self,
        trainset_data: dict[str, Any],
        telemetry_7d: list[dict[str, Any]] | None = None,
        mileage_history: list[dict[str, Any]] | None = None,
    ) -> FeatureSnapshot:
        """Compute features from raw data and store the snapshot."""
        features = self.computer.compute_maintenance_features(
            trainset_data,
            telemetry_7d or [],
            mileage_history or [],
        )
        snapshot = FeatureSnapshot(
            trainset_id=trainset_data.get("id", ""),
            trainset_code=trainset_data.get("trainset_code", ""),
            snapshot_date=str(date.today()),
            features=features,
        )
        self.put(snapshot)
        return snapshot

    def bulk_compute(self, fleet_data: list[dict[str, Any]]) -> list[FeatureSnapshot]:
        """Compute and store feature snapshots for entire fleet."""
        snapshots = []
        for ts_data in fleet_data:
            try:
                snapshot = self.compute_and_store(ts_data)
                snapshots.append(snapshot)
            except Exception as exc:
                logger.error("Feature computation failed for %s: %s", ts_data.get("trainset_code"), exc)
        logger.info("Bulk feature computation complete: %d snapshots", len(snapshots))
        return snapshots

    def stats(self) -> dict[str, Any]:
        return {
            "total_snapshots": len(self._history),
            "unique_trainsets": len({s.trainset_id for s in self._history}),
            "date_range": {
                "earliest": min((s.snapshot_date for s in self._history), default="—"),
                "latest": max((s.snapshot_date for s in self._history), default="—"),
            },
        }


# ── Singleton ─────────────────────────────────────────────────────────────

_feature_store: FeatureStore | None = None

def get_feature_store() -> FeatureStore:
    global _feature_store
    if _feature_store is None:
        _feature_store = FeatureStore()
    return _feature_store
