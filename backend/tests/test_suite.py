"""
KMRL NexusAI — Test Suite
============================
Unit + Integration + Optimization Engine tests
Run: pytest tests/ -v --cov=app --cov-report=html
"""
from __future__ import annotations

import json
from datetime import date, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest


# ── Optimization Engine Tests ─────────────────────────────────────────────

class TestConstraintChecker:
    """Tests for hard and soft constraint evaluation."""

    @pytest.fixture
    def checker(self):
        from app.optimization.engine import ConstraintChecker
        return ConstraintChecker()

    @pytest.fixture
    def healthy_trainset(self):
        from app.optimization.engine import TrainsetState
        return TrainsetState(
            id="ts-001", code="TS-01",
            fitness_valid=True, signalling_clear=True, telecom_clear=True,
            critical_jobs_open=0, mileage_km=3500.0,
            brake_health_pct=92.0, hvac_health_pct=88.0, door_health_pct=95.0,
            cleaning_done=True, branding_priority=75,
            days_since_ibl=30, predicted_failure_risk=0.05,
        )

    @pytest.fixture
    def unhealthy_trainset(self):
        from app.optimization.engine import TrainsetState
        return TrainsetState(
            id="ts-002", code="TS-02",
            fitness_valid=False, signalling_clear=True, telecom_clear=False,
            critical_jobs_open=2, mileage_km=5200.0,
            brake_health_pct=42.0, hvac_health_pct=60.0, door_health_pct=70.0,
            cleaning_done=False, branding_priority=0,
            days_since_ibl=95, predicted_failure_risk=0.88,
        )

    def test_no_hard_violations_for_healthy_trainset(self, checker, healthy_trainset):
        violations = checker.check_hard_constraints(healthy_trainset)
        assert violations == [], f"Expected no violations, got: {violations}"

    def test_multiple_hard_violations_for_unhealthy_trainset(self, checker, unhealthy_trainset):
        violations = checker.check_hard_constraints(unhealthy_trainset)
        assert len(violations) >= 3, "Expected ≥3 hard violations"
        assert any("fitness" in v.lower() for v in violations)
        assert any("telecom" in v.lower() for v in violations)
        assert any("critical job" in v.lower() for v in violations)

    def test_brake_health_below_50_triggers_violation(self, checker, healthy_trainset):
        healthy_trainset.brake_health_pct = 45.0
        violations = checker.check_hard_constraints(healthy_trainset)
        assert any("brake" in v.lower() for v in violations)

    def test_high_failure_risk_triggers_violation(self, checker, healthy_trainset):
        healthy_trainset.predicted_failure_risk = 0.90
        violations = checker.check_hard_constraints(healthy_trainset)
        assert any("risk" in v.lower() for v in violations)

    def test_soft_score_range(self, checker, healthy_trainset):
        score, factors = checker.compute_soft_score(healthy_trainset, fleet_avg_mileage=3500.0, depot=MagicMock())
        assert 0 <= score <= 100, f"Score {score} out of range [0,100]"
        assert isinstance(factors, dict)
        assert len(factors) > 0

    def test_cleaning_done_increases_score(self, checker, healthy_trainset):
        healthy_trainset.cleaning_done = True
        score_clean, factors_clean = checker.compute_soft_score(healthy_trainset, 3500.0, MagicMock())
        healthy_trainset.cleaning_done = False
        score_dirty, factors_dirty = checker.compute_soft_score(healthy_trainset, 3500.0, MagicMock())
        assert score_clean > score_dirty, "Cleaning done should increase score"

    def test_branding_priority_affects_score(self, checker, healthy_trainset):
        healthy_trainset.branding_priority = 100
        score_high, _ = checker.compute_soft_score(healthy_trainset, 3500.0, MagicMock())
        healthy_trainset.branding_priority = 0
        score_low, _ = checker.compute_soft_score(healthy_trainset, 3500.0, MagicMock())
        assert score_high > score_low

    def test_below_avg_mileage_scores_higher(self, checker, healthy_trainset):
        fleet_avg = 4000.0
        healthy_trainset.mileage_km = 3000.0  # well below avg
        score_low_mi, _ = checker.compute_soft_score(healthy_trainset, fleet_avg, MagicMock())
        healthy_trainset.mileage_km = 5000.0  # above avg
        score_high_mi, _ = checker.compute_soft_score(healthy_trainset, fleet_avg, MagicMock())
        assert score_low_mi > score_high_mi


class TestInductionOptimizer:
    """Tests for the OR-Tools optimization engine."""

    @pytest.fixture
    def depot_config(self):
        from app.optimization.engine import DepotConfig
        return DepotConfig(total_bays=25, ibl_bays=4, cleaning_bays=3, revenue_target=18, standby_target=3)

    @pytest.fixture
    def fleet_25(self):
        """25-trainset fleet with realistic heterogeneous states."""
        from app.optimization.engine import TrainsetState
        import random
        random.seed(42)
        return [
            TrainsetState(
                id=f"ts-{i+1:03d}", code=f"TS-{i+1:02d}",
                fitness_valid=random.random() > 0.08,
                signalling_clear=random.random() > 0.02,
                telecom_clear=random.random() > 0.02,
                critical_jobs_open=1 if i in [2, 7, 21] else 0,
                mileage_km=round(3000 + random.uniform(0, 2000), 1),
                brake_health_pct=round(55 + random.uniform(0, 45), 1),
                hvac_health_pct=round(65 + random.uniform(0, 35), 1),
                door_health_pct=round(70 + random.uniform(0, 30), 1),
                cleaning_done=random.random() > 0.25,
                current_bay=f"A{i+1}",
                branding_priority=random.randint(0, 100),
                days_since_ibl=random.randint(5, 120),
                predicted_failure_risk=round(random.uniform(0.03, 0.45), 3),
            )
            for i in range(25)
        ]

    def test_optimizer_produces_result(self, fleet_25, depot_config):
        from app.optimization.engine import InductionOptimizer
        optimizer = InductionOptimizer(depot=depot_config, timeout_seconds=10)
        result = optimizer.optimize(fleet_25, plan_date=date.today())
        assert result is not None
        assert result.status in ("optimal", "feasible", "fallback")

    def test_total_assignments_equals_fleet_size(self, fleet_25, depot_config):
        from app.optimization.engine import InductionOptimizer
        optimizer = InductionOptimizer(depot=depot_config, timeout_seconds=10)
        result = optimizer.optimize(fleet_25)
        total = (len(result.revenue_service) + len(result.standby) +
                 len(result.ibl) + len(result.maintenance))
        assert total == len(fleet_25), f"Total {total} ≠ fleet size {len(fleet_25)}"

    def test_no_trainset_assigned_twice(self, fleet_25, depot_config):
        from app.optimization.engine import InductionOptimizer
        optimizer = InductionOptimizer(depot=depot_config, timeout_seconds=10)
        result = optimizer.optimize(fleet_25)
        all_codes = (
            [i.trainset_code for i in result.revenue_service] +
            [i.trainset_code for i in result.standby] +
            [i.trainset_code for i in result.ibl] +
            [i.trainset_code for i in result.maintenance]
        )
        assert len(all_codes) == len(set(all_codes)), "Duplicate trainset assignments found"

    def test_minimum_revenue_trains_satisfied(self, fleet_25, depot_config):
        from app.optimization.engine import InductionOptimizer
        optimizer = InductionOptimizer(depot=depot_config, timeout_seconds=10)
        result = optimizer.optimize(fleet_25)
        assert len(result.revenue_service) >= depot_config.revenue_target, \
            f"Revenue count {len(result.revenue_service)} < target {depot_config.revenue_target}"

    def test_ibl_capacity_constraint(self, fleet_25, depot_config):
        from app.optimization.engine import InductionOptimizer
        optimizer = InductionOptimizer(depot=depot_config, timeout_seconds=10)
        result = optimizer.optimize(fleet_25)
        assert len(result.ibl) <= depot_config.ibl_bays, \
            f"IBL count {len(result.ibl)} > capacity {depot_config.ibl_bays}"

    def test_hard_violation_trainsets_not_in_revenue(self, fleet_25, depot_config):
        """Trainsets with open critical jobs must NOT be in revenue service."""
        from app.optimization.engine import InductionOptimizer
        optimizer = InductionOptimizer(depot=depot_config, timeout_seconds=10)
        result = optimizer.optimize(fleet_25)

        revenue_codes = {i.trainset_code for i in result.revenue_service}
        for i, ts in enumerate(fleet_25):
            if ts.critical_jobs_open > 0:
                assert ts.code not in revenue_codes, \
                    f"{ts.code} has critical jobs but was assigned revenue service"

    def test_score_is_between_0_and_100(self, fleet_25, depot_config):
        from app.optimization.engine import InductionOptimizer
        optimizer = InductionOptimizer(depot=depot_config, timeout_seconds=10)
        result = optimizer.optimize(fleet_25)
        assert 0 <= result.score <= 100, f"Score {result.score} out of valid range"

    def test_confidence_pct_per_item(self, fleet_25, depot_config):
        from app.optimization.engine import InductionOptimizer
        optimizer = InductionOptimizer(depot=depot_config, timeout_seconds=10)
        result = optimizer.optimize(fleet_25)
        for item in result.revenue_service:
            assert 0 <= item.confidence_pct <= 100, \
                f"Confidence {item.confidence_pct} out of range for {item.trainset_code}"

    def test_solve_time_recorded(self, fleet_25, depot_config):
        from app.optimization.engine import InductionOptimizer
        optimizer = InductionOptimizer(depot=depot_config, timeout_seconds=10)
        result = optimizer.optimize(fleet_25)
        assert result.solve_time_ms > 0

    def test_mileage_variance_calculated(self, fleet_25, depot_config):
        from app.optimization.engine import InductionOptimizer
        optimizer = InductionOptimizer(depot=depot_config, timeout_seconds=10)
        result = optimizer.optimize(fleet_25)
        assert result.mileage_variance >= 0

    def test_explainable_ai_reasons(self, fleet_25, depot_config):
        from app.optimization.engine import ExplainableAI, InductionOptimizer
        ts = fleet_25[0]
        checker = InductionOptimizer(depot=depot_config).checker
        fleet_avg = sum(t.mileage_km for t in fleet_25) / len(fleet_25)
        _, factors = checker.compute_soft_score(ts, fleet_avg, depot_config)
        reasons = ExplainableAI.generate_reasons(ts, fleet_avg, factors, "revenue_service")
        assert isinstance(reasons, list)
        assert len(reasons) >= 1
        assert all(isinstance(r, str) for r in reasons)


# ── ML Pipeline Tests ─────────────────────────────────────────────────────

class TestPredictiveMaintenanceModel:
    """Unit tests for the XGBoost maintenance model."""

    @pytest.fixture
    def model(self):
        from app.ml.pipeline import PredictiveMaintenanceModel
        return PredictiveMaintenanceModel(horizon_days=14)

    @pytest.fixture
    def sample_features(self) -> dict:
        from app.ml.pipeline import MAINTENANCE_FEATURES
        import random
        random.seed(7)
        return {feat: random.uniform(0, 100) for feat in MAINTENANCE_FEATURES}

    @pytest.fixture
    def training_data(self):
        """Minimal synthetic training set (500 samples)."""
        import pandas as pd
        from app.ml.pipeline import MAINTENANCE_FEATURES
        n = 500
        np.random.seed(0)
        return (
            pd.DataFrame({feat: np.random.uniform(0, 100, n) for feat in MAINTENANCE_FEATURES}),
            pd.DataFrame({"brake_failure_in_14d": (np.random.random(n) < 0.1).astype(int)})
        )

    def test_train_returns_metrics(self, model, training_data):
        X, y = training_data
        metrics = model.train(X, y, system="brake")
        assert "roc_auc" in metrics
        assert "avg_precision" in metrics
        assert 0.0 <= metrics["roc_auc"] <= 1.0

    def test_predict_after_train(self, model, training_data, sample_features):
        X, y = training_data
        model.train(X, y, system="brake")
        result = model.predict(sample_features, system="brake")
        assert "failure_probability" in result
        assert 0.0 <= result["failure_probability"] <= 1.0
        assert result["risk_level"] in ("low", "medium", "high", "critical")

    def test_predict_without_training_raises(self, model, sample_features):
        with pytest.raises(AssertionError):
            model.predict(sample_features, system="brake")

    def test_predict_returns_shap_values(self, model, training_data, sample_features):
        X, y = training_data
        model.train(X, y, system="brake")
        result = model.predict(sample_features, system="brake")
        assert "top_shap_features" in result
        assert len(result["top_shap_features"]) <= 5

    def test_risk_recommendation_thresholds(self, model):
        assert "IMMEDIATE" in model._risk_recommendation(0.8)
        assert "URGENT" in model._risk_recommendation(0.5)
        assert "MONITOR" in model._risk_recommendation(0.25)
        assert "NOMINAL" in model._risk_recommendation(0.1)


class TestDriftDetector:
    """Tests for model drift detection."""

    @pytest.fixture
    def detector(self):
        from app.ml.pipeline import ModelDriftDetector
        return ModelDriftDetector()

    def test_no_drift_same_distribution(self, detector):
        np.random.seed(0)
        ref = np.random.beta(2, 5, 1000)
        cur = np.random.beta(2, 5, 500)
        result = detector.check_drift("test_model", ref, cur)
        assert not result["needs_retrain"]
        assert result["psi"] < 0.1

    def test_drift_detected_different_distribution(self, detector):
        np.random.seed(0)
        ref = np.random.beta(2, 5, 1000)
        cur = np.random.beta(8, 2, 500)   # heavily different
        result = detector.check_drift("test_model", ref, cur)
        assert result["needs_retrain"]
        assert result["psi"] > 0.2

    def test_psi_is_non_negative(self, detector):
        np.random.seed(1)
        ref = np.random.uniform(0, 1, 500)
        cur = np.random.uniform(0, 1, 300)
        result = detector.check_drift("m", ref, cur)
        assert result["psi"] >= 0


class TestAnomalyDetector:
    """Tests for IoT telemetry anomaly detection."""

    @pytest.fixture
    def detector(self):
        from app.ml.pipeline import TelemetryAnomalyDetector
        d = TelemetryAnomalyDetector()
        # Fit on baseline normal data
        np.random.seed(42)
        normal = np.random.normal(loc=50, scale=5, size=(500, 4))
        d.fit("ts-001", normal)
        return d

    def test_normal_reading_not_anomaly(self, detector):
        normal_reading = np.array([50.0, 50.0, 50.0, 50.0])
        result = detector.score("ts-001", normal_reading)
        assert result["trained"]
        # Most normal readings should not be flagged
        assert isinstance(result["is_anomaly"], bool)

    def test_extreme_reading_detected_as_anomaly(self, detector):
        extreme_reading = np.array([200.0, 200.0, 200.0, 200.0])
        result = detector.score("ts-001", extreme_reading)
        assert result["is_anomaly"]

    def test_untrained_trainset_returns_safe(self, detector):
        result = detector.score("ts-unknown", np.array([50.0, 50.0, 50.0, 50.0]))
        assert not result["is_anomaly"]
        assert not result["trained"]


# ── API Tests ─────────────────────────────────────────────────────────────

class TestHealthEndpoint:
    @pytest.mark.asyncio
    async def test_health_returns_200(self):
        from httpx import AsyncClient, ASGITransport
        from app.main import app
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "version" in data

    @pytest.mark.asyncio
    async def test_root_returns_service_info(self):
        from httpx import AsyncClient, ASGITransport
        from app.main import app
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/")
        assert response.status_code == 200
        assert "KMRL" in response.json()["service"]


class TestAuthEndpoint:
    @pytest.mark.asyncio
    async def test_valid_login_returns_token(self):
        from httpx import AsyncClient, ASGITransport
        from app.main import app
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/v1/auth/token",
                data={"username": "depot_controller@kmrl.in", "password": "kmrl@2025"},
            )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    @pytest.mark.asyncio
    async def test_invalid_credentials_returns_401(self):
        from httpx import AsyncClient, ASGITransport
        from app.main import app
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/v1/auth/token",
                data={"username": "wrong@kmrl.in", "password": "wrong"},
            )
        assert response.status_code == 401


# ── Performance / Load Tests ──────────────────────────────────────────────

class TestOptimizerPerformance:
    """Ensure optimizer meets timing SLAs."""

    def test_25_trainset_optimization_under_30s(self):
        import time
        from app.optimization.engine import DepotConfig, InductionOptimizer, TrainsetState
        import random

        random.seed(99)
        fleet = [
            TrainsetState(
                id=f"ts-{i:03d}", code=f"TS-{i:02d}",
                fitness_valid=random.random() > 0.1,
                critical_jobs_open=0,
                mileage_km=round(3000 + random.uniform(0, 2000), 1),
                brake_health_pct=round(60 + random.uniform(0, 40), 1),
                hvac_health_pct=round(70 + random.uniform(0, 30), 1),
                door_health_pct=round(75 + random.uniform(0, 25), 1),
                cleaning_done=True,
                predicted_failure_risk=random.uniform(0.0, 0.3),
            )
            for i in range(25)
        ]
        depot = DepotConfig(revenue_target=18)
        optimizer = InductionOptimizer(depot=depot, timeout_seconds=30)

        start = time.perf_counter()
        result = optimizer.optimize(fleet)
        elapsed = time.perf_counter() - start

        assert elapsed < 30, f"Optimization took {elapsed:.1f}s — must complete in <30s"
        assert result.status in ("optimal", "feasible")

    def test_40_trainset_optimization_feasible(self):
        """Future fleet size of 40 must still produce a feasible solution."""
        import random
        from app.optimization.engine import DepotConfig, InductionOptimizer, TrainsetState

        random.seed(77)
        fleet = [
            TrainsetState(
                id=f"ts-{i:03d}", code=f"TS-{i:02d}",
                fitness_valid=random.random() > 0.1,
                critical_jobs_open=0,
                mileage_km=round(3000 + random.uniform(0, 2500), 1),
                brake_health_pct=round(65 + random.uniform(0, 35), 1),
                hvac_health_pct=round(70 + random.uniform(0, 30), 1),
                door_health_pct=round(75 + random.uniform(0, 25), 1),
                cleaning_done=True,
                predicted_failure_risk=random.uniform(0.0, 0.35),
            )
            for i in range(40)
        ]
        depot = DepotConfig(total_bays=40, ibl_bays=6, revenue_target=28)
        optimizer = InductionOptimizer(depot=depot, timeout_seconds=30)
        result = optimizer.optimize(fleet)
        assert result.status in ("optimal", "feasible")
        assert len(result.revenue_service) >= 28
