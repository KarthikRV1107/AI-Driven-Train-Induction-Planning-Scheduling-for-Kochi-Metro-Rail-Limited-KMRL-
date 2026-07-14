"""
KMRL NexusAI — ML Pipeline
============================
Models:
  1. PredictiveMaintenanceModel  — XGBoost failure probability per system
  2. ReadinessForecastModel      — PyTorch sequence model for deployment readiness
  3. MileageForecastModel        — Linear/XGB mileage projection
  4. AnomalyDetector             — Isolation Forest on telemetry streams
  5. DriftDetector               — Statistical drift monitoring
"""
from __future__ import annotations

import json
import logging
import os
import pickle
from dataclasses import asdict, dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import shap
import torch
import torch.nn as nn
from sklearn.ensemble import IsolationForest
from sklearn.metrics import (
    average_precision_score, roc_auc_score,
    mean_absolute_error, mean_squared_error,
)
from sklearn.model_selection import StratifiedKFold, TimeSeriesSplit
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from xgboost import XGBClassifier, XGBRegressor

logger = logging.getLogger(__name__)

MODEL_DIR = Path(os.getenv("ML_MODEL_PATH", "/app/models"))
MODEL_DIR.mkdir(parents=True, exist_ok=True)


# ── Feature Engineering ───────────────────────────────────────────────────

MAINTENANCE_FEATURES = [
    "brake_health_pct",
    "hvac_health_pct",
    "door_health_pct",
    "total_mileage_km",
    "days_since_last_service",
    "days_since_ibl",
    "open_job_cards_count",
    "critical_jobs_count",
    "vibration_mean_7d",
    "vibration_std_7d",
    "temperature_mean_7d",
    "speed_max_7d",
    "brake_pressure_mean_7d",
    "door_cycle_count_7d",
    "hvac_runtime_hrs_7d",
    "age_years",
    "km_since_last_brake_service",
    "km_since_last_hvac_service",
    "brake_events_7d",          # emergency brake applications
    "pantograph_wear_pct",
]

READINESS_SEQUENCE_FEATURES = [
    "brake_health_pct",
    "hvac_health_pct",
    "door_health_pct",
    "daily_km",
    "brake_events",
    "door_faults",
    "hvac_faults",
    "is_cleaning_done",
    "open_jobs",
]


# ── Feature Engineering Functions ─────────────────────────────────────────

def engineer_maintenance_features(df: pd.DataFrame) -> pd.DataFrame:
    """Create derived features for the maintenance model."""
    df = df.copy()

    # Rolling stats (assumes telemetry columns present)
    for col in ["brake_pressure", "vibration", "temperature", "speed"]:
        if col in df.columns:
            df[f"{col}_mean_7d"] = df.groupby("trainset_id")[col].transform(
                lambda x: x.rolling(7, min_periods=1).mean()
            )
            df[f"{col}_std_7d"] = df.groupby("trainset_id")[col].transform(
                lambda x: x.rolling(7, min_periods=1).std().fillna(0)
            )

    # Age in years
    if "year_of_manufacture" in df.columns:
        current_year = date.today().year
        df["age_years"] = current_year - df["year_of_manufacture"]

    # Km since last service (fill with total mileage if unavailable)
    for service_type in ["brake", "hvac"]:
        col = f"km_since_last_{service_type}_service"
        if col not in df.columns:
            df[col] = df.get("total_mileage_km", 0) * 0.3  # estimate

    # Ensure all required features exist
    for feat in MAINTENANCE_FEATURES:
        if feat not in df.columns:
            df[feat] = 0.0

    return df[MAINTENANCE_FEATURES]


# ── Model 1: Predictive Maintenance (XGBoost) ─────────────────────────────

class PredictiveMaintenanceModel:
    """
    Predicts failure probability per system (brake, HVAC, door) within
    a configurable horizon (default: 14 days).

    Target variable: binary — did a failure/unplanned withdrawal occur
    within `horizon_days`?
    """

    SYSTEMS = ["brake", "hvac", "door", "pantograph", "bogie"]
    VERSION = "1.3.0"

    def __init__(self, horizon_days: int = 14):
        self.horizon_days = horizon_days
        self.models: dict[str, XGBClassifier] = {}
        self.scalers: dict[str, StandardScaler] = {}
        self.explainers: dict[str, shap.TreeExplainer] = {}
        self._is_trained = False

    def _make_model(self) -> XGBClassifier:
        return XGBClassifier(
            n_estimators=400,
            max_depth=6,
            learning_rate=0.05,
            subsample=0.85,
            colsample_bytree=0.85,
            min_child_weight=5,
            scale_pos_weight=4,         # handle class imbalance
            eval_metric="aucpr",
            early_stopping_rounds=30,
            n_jobs=-1,
            random_state=42,
        )

    def train(
        self,
        df_features: pd.DataFrame,
        df_labels: pd.DataFrame,
        system: str = "brake",
        eval_size: float = 0.2,
    ) -> dict[str, float]:
        """
        Train for a single system. Returns evaluation metrics.
        df_labels must have columns: [trainset_id, date, {system}_failure_in_{horizon}d]
        """
        target_col = f"{system}_failure_in_{self.horizon_days}d"
        assert target_col in df_labels.columns, f"Missing target column: {target_col}"

        X = df_features.copy().fillna(0)
        y = df_labels[target_col].values

        # Time-series split (no data leakage)
        tss = TimeSeriesSplit(n_splits=5)
        oof_preds = np.zeros(len(y))

        for fold, (train_idx, val_idx) in enumerate(tss.split(X)):
            X_tr, X_val = X.iloc[train_idx], X.iloc[val_idx]
            y_tr, y_val = y[train_idx], y[val_idx]

            scaler = StandardScaler()
            X_tr_s = scaler.fit_transform(X_tr)
            X_val_s = scaler.transform(X_val)

            m = self._make_model()
            m.fit(
                X_tr_s, y_tr,
                eval_set=[(X_val_s, y_val)],
                verbose=False,
            )
            oof_preds[val_idx] = m.predict_proba(X_val_s)[:, 1]

        # Final model on all data
        scaler_final = StandardScaler()
        X_scaled = scaler_final.fit_transform(X)
        model_final = self._make_model()
        # Remove early stopping for final training
        model_final.set_params(early_stopping_rounds=None)
        model_final.fit(X_scaled, y, verbose=False)

        self.models[system] = model_final
        self.scalers[system] = scaler_final
        self.explainers[system] = shap.TreeExplainer(model_final)
        self._is_trained = True

        metrics = {
            "system": system,
            "horizon_days": self.horizon_days,
            "roc_auc": round(roc_auc_score(y, oof_preds), 4),
            "avg_precision": round(average_precision_score(y, oof_preds), 4),
            "positive_rate": round(y.mean(), 4),
            "n_samples": len(y),
        }
        logger.info("Trained %s model: %s", system, metrics)
        return metrics

    def predict(
        self,
        features: dict[str, float],
        system: str = "brake",
    ) -> dict[str, Any]:
        """
        Returns failure probability + SHAP explanation for a single trainset.
        """
        assert self._is_trained and system in self.models, \
            f"Model for '{system}' not trained"

        X = pd.DataFrame([features])[MAINTENANCE_FEATURES].fillna(0)
        X_scaled = self.scalers[system].transform(X)

        prob = float(self.models[system].predict_proba(X_scaled)[0, 1])

        # SHAP explanations
        shap_values = self.explainers[system].shap_values(X_scaled)
        feature_importance = {
            feat: round(float(shap_values[0][j]), 4)
            for j, feat in enumerate(MAINTENANCE_FEATURES)
        }
        top_features = sorted(
            feature_importance.items(), key=lambda kv: abs(kv[1]), reverse=True
        )[:5]

        return {
            "system": system,
            "failure_probability": round(prob, 4),
            "risk_level": "critical" if prob > 0.7 else "high" if prob > 0.4 else "medium" if prob > 0.2 else "low",
            "horizon_days": self.horizon_days,
            "top_shap_features": dict(top_features),
            "model_version": self.VERSION,
        }

    def predict_all_systems(self, features: dict[str, float]) -> dict[str, Any]:
        """Predict failure risk across all trained systems."""
        results = {}
        for system in self.SYSTEMS:
            if system in self.models:
                results[system] = self.predict(features, system)
        composite_risk = max(
            (r["failure_probability"] for r in results.values()), default=0.0
        )
        return {
            "systems": results,
            "composite_failure_risk": round(composite_risk, 4),
            "recommendation": self._risk_recommendation(composite_risk),
        }

    @staticmethod
    def _risk_recommendation(risk: float) -> str:
        if risk > 0.7:
            return "IMMEDIATE: Remove from service, send to IBL"
        elif risk > 0.4:
            return "URGENT: Schedule inspection within 48 hours"
        elif risk > 0.2:
            return "MONITOR: Increase telemetry sampling, inspect at next opportunity"
        return "NOMINAL: Continue regular monitoring"

    def save(self, path: Path | None = None) -> None:
        path = path or MODEL_DIR / f"predictive_maintenance_v{self.VERSION}"
        path.mkdir(parents=True, exist_ok=True)
        for system in self.models:
            with open(path / f"{system}_model.pkl", "wb") as f:
                pickle.dump(self.models[system], f)
            with open(path / f"{system}_scaler.pkl", "wb") as f:
                pickle.dump(self.scalers[system], f)
        meta = {"version": self.VERSION, "systems": list(self.models.keys()), "horizon_days": self.horizon_days}
        (path / "metadata.json").write_text(json.dumps(meta, indent=2))
        logger.info("Saved maintenance model to %s", path)

    @classmethod
    def load(cls, path: Path) -> "PredictiveMaintenanceModel":
        meta = json.loads((path / "metadata.json").read_text())
        instance = cls(horizon_days=meta["horizon_days"])
        for system in meta["systems"]:
            with open(path / f"{system}_model.pkl", "rb") as f:
                instance.models[system] = pickle.load(f)
            with open(path / f"{system}_scaler.pkl", "rb") as f:
                instance.scalers[system] = pickle.load(f)
            instance.explainers[system] = shap.TreeExplainer(instance.models[system])
        instance._is_trained = True
        return instance


# ── Model 2: Readiness Forecast (PyTorch LSTM) ────────────────────────────

class ReadinessLSTM(nn.Module):
    """
    LSTM-based sequence model.
    Input: (batch, seq_len, n_features) — last 30 days of daily telemetry
    Output: (batch, 1) — probability of successful deployment tomorrow
    """

    def __init__(
        self,
        input_size: int = len(READINESS_SEQUENCE_FEATURES),
        hidden_size: int = 64,
        num_layers: int = 2,
        dropout: float = 0.3,
    ):
        super().__init__()
        self.lstm = nn.LSTM(
            input_size, hidden_size, num_layers,
            batch_first=True, dropout=dropout
        )
        self.attention = nn.MultiheadAttention(hidden_size, num_heads=4, batch_first=True)
        self.classifier = nn.Sequential(
            nn.LayerNorm(hidden_size),
            nn.Linear(hidden_size, 32),
            nn.GELU(),
            nn.Dropout(0.2),
            nn.Linear(32, 1),
            nn.Sigmoid(),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        lstm_out, _ = self.lstm(x)                    # (B, T, H)
        attn_out, _ = self.attention(lstm_out, lstm_out, lstm_out)
        pooled = attn_out.mean(dim=1)                 # (B, H)
        return self.classifier(pooled).squeeze(-1)    # (B,)


class ReadinessForecastModel:
    """
    Wraps ReadinessLSTM with training, inference, and persistence.
    """
    VERSION = "1.1.0"
    SEQ_LEN = 30  # 30 days of history

    def __init__(self, device: str | None = None):
        self.device = torch.device(
            device or ("cuda" if torch.cuda.is_available() else "cpu")
        )
        self.model = ReadinessLSTM().to(self.device)
        self.scaler = StandardScaler()
        self._is_trained = False

    def _prepare_sequences(
        self,
        df: pd.DataFrame,
        trainset_ids: list[str],
    ) -> tuple[np.ndarray, np.ndarray]:
        """Build (X, y) sequences from daily telemetry DataFrame."""
        X_list, y_list = [], []

        for ts_id in trainset_ids:
            ts_df = df[df["trainset_id"] == ts_id].sort_values("date")
            feat_cols = [c for c in READINESS_SEQUENCE_FEATURES if c in ts_df.columns]
            values = ts_df[feat_cols].fillna(0).values

            for i in range(len(values) - self.SEQ_LEN):
                seq = values[i : i + self.SEQ_LEN]
                label = ts_df["successful_deployment"].iloc[i + self.SEQ_LEN]
                X_list.append(seq)
                y_list.append(label)

        return np.array(X_list, dtype=np.float32), np.array(y_list, dtype=np.float32)

    def train(
        self,
        df: pd.DataFrame,
        trainset_ids: list[str],
        epochs: int = 50,
        batch_size: int = 64,
        lr: float = 1e-3,
    ) -> dict[str, float]:
        X, y = self._prepare_sequences(df, trainset_ids)
        n = len(X)
        split = int(n * 0.8)

        # Scale features
        X_flat = X.reshape(-1, X.shape[-1])
        self.scaler.fit(X_flat[:split * self.SEQ_LEN])
        X_scaled = self.scaler.transform(X_flat).reshape(X.shape)

        X_tr = torch.tensor(X_scaled[:split]).to(self.device)
        y_tr = torch.tensor(y[:split]).to(self.device)
        X_val = torch.tensor(X_scaled[split:]).to(self.device)
        y_val = torch.tensor(y[split:]).to(self.device)

        optimizer = torch.optim.AdamW(self.model.parameters(), lr=lr, weight_decay=1e-4)
        scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=epochs)
        criterion = nn.BCELoss()

        best_val_loss = float("inf")
        best_state = None

        self.model.train()
        for epoch in range(epochs):
            perm = torch.randperm(len(X_tr))
            epoch_loss = 0.0
            for i in range(0, len(X_tr), batch_size):
                idx = perm[i : i + batch_size]
                xb, yb = X_tr[idx], y_tr[idx]
                optimizer.zero_grad()
                preds = self.model(xb)
                loss = criterion(preds, yb)
                loss.backward()
                nn.utils.clip_grad_norm_(self.model.parameters(), 1.0)
                optimizer.step()
                epoch_loss += loss.item()
            scheduler.step()

            # Validation
            self.model.eval()
            with torch.no_grad():
                val_preds = self.model(X_val)
                val_loss = criterion(val_preds, y_val).item()
            self.model.train()

            if val_loss < best_val_loss:
                best_val_loss = val_loss
                best_state = {k: v.clone() for k, v in self.model.state_dict().items()}

            if epoch % 10 == 0:
                logger.info("Epoch %d/%d — train_loss=%.4f val_loss=%.4f", epoch, epochs, epoch_loss, val_loss)

        if best_state:
            self.model.load_state_dict(best_state)

        self._is_trained = True
        return {"best_val_loss": round(best_val_loss, 4), "epochs": epochs}

    @torch.no_grad()
    def predict(self, sequence: np.ndarray) -> dict[str, Any]:
        """
        sequence: numpy array of shape (SEQ_LEN, n_features)
        Returns deployment readiness probability.
        """
        assert self._is_trained, "Model not trained"

        seq_flat = sequence.reshape(-1, sequence.shape[-1])
        seq_scaled = self.scaler.transform(seq_flat).reshape(sequence.shape)
        x = torch.tensor(seq_scaled[np.newaxis], dtype=torch.float32).to(self.device)

        self.model.eval()
        prob = float(self.model(x).item())

        return {
            "readiness_probability": round(prob, 4),
            "risk_level": "low" if prob > 0.8 else "medium" if prob > 0.5 else "high",
            "deploy_recommendation": prob > 0.6,
            "model_version": self.VERSION,
        }

    def save(self, path: Path | None = None) -> None:
        path = path or MODEL_DIR / f"readiness_lstm_v{self.VERSION}"
        path.mkdir(parents=True, exist_ok=True)
        torch.save(self.model.state_dict(), path / "model.pt")
        with open(path / "scaler.pkl", "wb") as f:
            pickle.dump(self.scaler, f)
        (path / "metadata.json").write_text(json.dumps({"version": self.VERSION, "seq_len": self.SEQ_LEN}))

    @classmethod
    def load(cls, path: Path, device: str | None = None) -> "ReadinessForecastModel":
        meta = json.loads((path / "metadata.json").read_text())
        instance = cls(device=device)
        instance.model.load_state_dict(torch.load(path / "model.pt", map_location=instance.device))
        with open(path / "scaler.pkl", "rb") as f:
            instance.scaler = pickle.load(f)
        instance._is_trained = True
        return instance


# ── Model 3: Mileage Forecast (XGBoost Regressor) ────────────────────────

class MileageForecastModel:
    """Forecasts daily/weekly mileage accumulation per trainset."""
    VERSION = "1.0.0"

    def __init__(self):
        self.model = XGBRegressor(
            n_estimators=300, max_depth=5,
            learning_rate=0.05, subsample=0.8,
            n_jobs=-1, random_state=42,
        )
        self.scaler = StandardScaler()
        self._is_trained = False

    def train(self, X: pd.DataFrame, y: pd.Series) -> dict[str, float]:
        X_scaled = self.scaler.fit_transform(X.fillna(0))
        self.model.fit(X_scaled, y)
        preds = self.model.predict(X_scaled)
        self._is_trained = True
        return {
            "mae": round(mean_absolute_error(y, preds), 2),
            "rmse": round(mean_squared_error(y, preds) ** 0.5, 2),
        }

    def predict_7d(self, features: dict[str, float]) -> float:
        X = pd.DataFrame([features]).fillna(0)
        return round(float(self.model.predict(self.scaler.transform(X))[0]), 1)


# ── Model 4: Anomaly Detector (Isolation Forest) ──────────────────────────

class TelemetryAnomalyDetector:
    """
    Detects anomalous sensor readings in real-time telemetry streams.
    Fitted on 30 days of baseline data per trainset.
    """
    VERSION = "1.0.0"
    CONTAMINATION = 0.05   # expect ~5% anomalies

    def __init__(self):
        self.models: dict[str, IsolationForest] = {}
        self.scalers: dict[str, StandardScaler] = {}

    def fit(self, trainset_id: str, X: np.ndarray) -> None:
        scaler = StandardScaler()
        X_s = scaler.fit_transform(X)
        model = IsolationForest(
            n_estimators=200,
            contamination=self.CONTAMINATION,
            random_state=42, n_jobs=-1,
        )
        model.fit(X_s)
        self.models[trainset_id] = model
        self.scalers[trainset_id] = scaler

    def score(self, trainset_id: str, reading: np.ndarray) -> dict[str, Any]:
        """Returns anomaly score (-1 = anomaly, 1 = normal)."""
        if trainset_id not in self.models:
            return {"is_anomaly": False, "score": 0.0, "trained": False}

        x = self.scalers[trainset_id].transform(reading.reshape(1, -1))
        pred = int(self.models[trainset_id].predict(x)[0])
        score = float(self.models[trainset_id].score_samples(x)[0])

        return {
            "is_anomaly": pred == -1,
            "anomaly_score": round(score, 4),
            "trained": True,
            "trainset_id": trainset_id,
        }


# ── Drift Detector ────────────────────────────────────────────────────────

class ModelDriftDetector:
    """
    Population Stability Index (PSI) based drift detection.
    Triggers model retraining when PSI > threshold.
    """
    PSI_THRESHOLD = 0.2   # >0.2 = significant drift
    BUCKETS = 10

    @staticmethod
    def compute_psi(expected: np.ndarray, actual: np.ndarray) -> float:
        """Compute PSI between reference and production distributions."""
        eps = 1e-8
        breakpoints = np.percentile(expected, np.linspace(0, 100, ModelDriftDetector.BUCKETS + 1))
        breakpoints[0] = -np.inf
        breakpoints[-1] = np.inf

        expected_percents = np.histogram(expected, bins=breakpoints)[0] / len(expected)
        actual_percents = np.histogram(actual, bins=breakpoints)[0] / len(actual)

        expected_percents = np.clip(expected_percents, eps, None)
        actual_percents = np.clip(actual_percents, eps, None)

        psi = np.sum((actual_percents - expected_percents) * np.log(actual_percents / expected_percents))
        return round(float(psi), 4)

    def check_drift(
        self,
        model_name: str,
        reference_preds: np.ndarray,
        current_preds: np.ndarray,
    ) -> dict[str, Any]:
        psi = self.compute_psi(reference_preds, current_preds)
        needs_retrain = psi > self.PSI_THRESHOLD
        return {
            "model": model_name,
            "psi": psi,
            "needs_retrain": needs_retrain,
            "severity": "high" if psi > 0.25 else "medium" if psi > self.PSI_THRESHOLD else "low",
        }


# ── ML Service (Inference Orchestrator) ──────────────────────────────────

class MLService:
    """
    Singleton service that loads all models and serves predictions.
    Used by FastAPI endpoints and Celery workers.
    """
    _instance: "MLService | None" = None

    def __init__(self):
        self.maintenance_model: PredictiveMaintenanceModel | None = None
        self.readiness_model: ReadinessForecastModel | None = None
        self.mileage_model: MileageForecastModel | None = None
        self.anomaly_detector = TelemetryAnomalyDetector()
        self.drift_detector = ModelDriftDetector()
        self._loaded = False

    @classmethod
    def get_instance(cls) -> "MLService":
        if cls._instance is None:
            cls._instance = cls()
            cls._instance._load_models()
        return cls._instance

    def _load_models(self) -> None:
        """Load models from disk; skip gracefully if not yet trained."""
        try:
            maint_path = MODEL_DIR / "predictive_maintenance_v1.3.0"
            if maint_path.exists():
                self.maintenance_model = PredictiveMaintenanceModel.load(maint_path)
                logger.info("Loaded maintenance model")

            ready_path = MODEL_DIR / "readiness_lstm_v1.1.0"
            if ready_path.exists():
                self.readiness_model = ReadinessForecastModel.load(ready_path)
                logger.info("Loaded readiness LSTM model")

            self._loaded = True
        except Exception as exc:
            logger.warning("Model load failed (will use defaults): %s", exc)

    def get_trainset_risk_profile(
        self,
        features: dict[str, float],
        trainset_id: str,
    ) -> dict[str, Any]:
        """Full risk assessment for a single trainset."""
        if self.maintenance_model and self.maintenance_model._is_trained:
            risk = self.maintenance_model.predict_all_systems(features)
        else:
            # Fallback: rule-based heuristic
            brake = features.get("brake_health_pct", 100)
            hvac = features.get("hvac_health_pct", 100)
            door = features.get("door_health_pct", 100)
            composite = 1 - min(brake, hvac, door) / 100
            risk = {
                "composite_failure_risk": round(composite, 3),
                "recommendation": PredictiveMaintenanceModel._risk_recommendation(composite),
                "systems": {},
                "source": "heuristic_fallback",
            }

        return {
            "trainset_id": trainset_id,
            "risk_profile": risk,
            "assessed_at": pd.Timestamp.now().isoformat(),
        }
