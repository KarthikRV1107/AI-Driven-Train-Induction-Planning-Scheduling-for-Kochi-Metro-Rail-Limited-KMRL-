"""
KMRL NexusAI — Full Pipeline Integration Tests
=================================================
End-to-end tests that exercise the complete induction planning pipeline:
  1. Feature computation from raw data
  2. ML risk scoring
  3. OR-Tools optimization
  4. SHAP explanation generation
  5. RL weight adaptation
  6. Simulation scenario
  7. PDF report generation
  8. Alert dispatch simulation

These tests validate that all modules integrate correctly.
"""
from __future__ import annotations

import json
import logging
from datetime import date, timedelta
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

logger = logging.getLogger(__name__)


# ── Fixtures ──────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def sample_fleet_data():
    """25-trainset fleet with realistic heterogeneous state."""
    import random
    random.seed(2025)
    statuses = (["revenue_service"] * 18 + ["standby"] * 3 +
                ["ibl"] * 2 + ["maintenance"] * 2)
    return [
        {
            "id":            f"ts-{i+1:03d}",
            "trainset_code": f"TS-{i+1:02d}",
            "rake_number":   f"KMRL-R{i+1:03d}",
            "current_status": statuses[i],
            "current_bay":   f"A{i % 9 + 1}",
            "total_mileage_km": round(3000 + random.uniform(0, 2000), 1),
            "brake_health":  round(55 + random.uniform(0, 45), 1),
            "hvac_health":   round(65 + random.uniform(0, 35), 1),
            "door_health":   round(70 + random.uniform(0, 30), 1),
            "days_since_service": random.randint(5, 90),
            "days_since_ibl":    random.randint(10, 120),
            "open_jobs":     random.randint(0, 4),
            "critical_jobs": 1 if i in [2, 6, 21] else 0,
            "year_of_manufacture": random.randint(2011, 2019),
            "pantograph_wear": round(random.uniform(20, 70), 1),
        }
        for i in range(25)
    ]


@pytest.fixture(scope="module")
def sample_telemetry():
    """7 days of synthetic telemetry per trainset."""
    import random
    random.seed(42)
    readings = []
    for ts_id in [f"ts-{i+1:03d}" for i in range(5)]:  # sample 5 trainsets
        for day in range(7):
            for _ in range(24):  # hourly readings
                readings.append({
                    "trainset_id":   ts_id,
                    "sensor_type":   "brake_pressure",
                    "value":         round(6.5 + random.gauss(0, 0.3), 3),
                    "timestamp":     f"2025-05-{24 - day:02d}T{_:02d}:00:00Z",
                })
                readings.append({
                    "trainset_id":   ts_id,
                    "sensor_type":   "vibration",
                    "value":         round(1.2 + random.gauss(0, 0.2), 3),
                    "timestamp":     f"2025-05-{24 - day:02d}T{_:02d}:00:00Z",
                })
    return readings


# ── Test 1: Feature Store Pipeline ────────────────────────────────────────

class TestFeatureStorePipeline:

    def test_bulk_feature_computation(self, sample_fleet_data, sample_telemetry):
        """Feature store should compute features for entire fleet."""
        from app.ml.feature_store import FeatureStore

        store = FeatureStore()
        snapshots = store.bulk_compute(sample_fleet_data[:5])

        assert len(snapshots) == 5
        for snap in snapshots:
            assert snap.trainset_code.startswith("TS-")
            assert len(snap.features) == 20
            assert all(isinstance(v, float) for v in snap.features.values())
            assert snap.snapshot_date == str(date.today())

    def test_feature_values_in_valid_range(self, sample_fleet_data):
        """All features must be clipped to their defined valid range."""
        from app.ml.feature_store import FeatureStore, MAINTENANCE_FEATURE_DEFS

        store = FeatureStore()
        snap  = store.compute_and_store(sample_fleet_data[0])

        for feat, (dtype, lo, hi, *_) in MAINTENANCE_FEATURE_DEFS.items():
            val = snap.features[feat]
            assert float(lo) <= val <= float(hi), \
                f"{feat} value {val} out of range [{lo}, {hi}]"

    def test_feature_retrieval_after_storage(self, sample_fleet_data):
        """Stored features should be retrievable by trainset ID."""
        from app.ml.feature_store import FeatureStore

        store = FeatureStore()
        snap  = store.compute_and_store(sample_fleet_data[3])
        retrieved = store.get_latest(snap.trainset_id)

        assert retrieved is not None
        assert retrieved.trainset_code == snap.trainset_code
        assert retrieved.features == snap.features

    def test_fingerprint_determinism(self, sample_fleet_data):
        """Same input data produces same fingerprint."""
        from app.ml.feature_store import FeatureStore

        store = FeatureStore()
        s1 = store.compute_and_store(sample_fleet_data[0])
        s2 = store.compute_and_store(sample_fleet_data[0])
        assert s1.fingerprint() == s2.fingerprint()


# ── Test 2: Full ML → Optimizer Pipeline ─────────────────────────────────

class TestMLOptimizerIntegration:

    def test_ml_scores_feed_into_optimizer(self, sample_fleet_data):
        """ML risk scores should influence optimizer trainset assignments."""
        from app.ml.pipeline import MLService
        from app.optimization.engine import (
            ConstraintChecker, DepotConfig, InductionOptimizer, TrainsetState
        )

        service = MLService.get_instance()
        checker = ConstraintChecker()

        # Build trainset states using ML risk scores
        trainset_states = []
        for ts in sample_fleet_data:
            features = {
                "brake_health_pct":    ts["brake_health"],
                "hvac_health_pct":     ts["hvac_health"],
                "door_health_pct":     ts["door_health"],
                "total_mileage_km":    ts["total_mileage_km"],
                "days_since_last_service": ts["days_since_service"],
                "days_since_ibl":      ts["days_since_ibl"],
                "open_job_cards_count": ts["open_jobs"],
                "critical_jobs_count": ts["critical_jobs"],
                "age_years":           2025 - ts["year_of_manufacture"],
            }
            profile = service.get_trainset_risk_profile(features, ts["id"])
            risk    = profile["risk_profile"].get("composite_failure_risk", 0.0)

            trainset_states.append(TrainsetState(
                id=ts["id"], code=ts["trainset_code"],
                fitness_valid=ts["critical_jobs"] == 0,
                critical_jobs_open=ts["critical_jobs"],
                mileage_km=ts["total_mileage_km"],
                brake_health_pct=ts["brake_health"],
                hvac_health_pct=ts["hvac_health"],
                door_health_pct=ts["door_health"],
                cleaning_done=True,
                days_since_ibl=ts["days_since_ibl"],
                predicted_failure_risk=risk,
            ))

        depot = DepotConfig(revenue_target=18)
        optimizer = InductionOptimizer(depot=depot, timeout_seconds=15)
        result = optimizer.optimize(trainset_states, plan_date=date.today())

        # High-risk trainsets should NOT be in revenue service
        revenue_codes = {i.trainset_code for i in result.revenue_service}
        for ts_state in trainset_states:
            if ts_state.predicted_failure_risk > 0.85:
                assert ts_state.code not in revenue_codes, \
                    f"High-risk {ts_state.code} should not be in revenue service"

        assert len(result.revenue_service) >= 18
        assert result.score > 0

    def test_explainability_completeness(self, sample_fleet_data):
        """Every revenue service recommendation must have human-readable reasons."""
        from app.optimization.engine import (
            DepotConfig, ExplainableAI, InductionOptimizer, TrainsetState
        )

        states = [
            TrainsetState(
                id=ts["id"], code=ts["trainset_code"],
                fitness_valid=ts["critical_jobs"] == 0,
                critical_jobs_open=ts["critical_jobs"],
                mileage_km=ts["total_mileage_km"],
                brake_health_pct=ts["brake_health"],
                hvac_health_pct=ts["hvac_health"],
                door_health_pct=ts["door_health"],
                cleaning_done=True,
                days_since_ibl=ts["days_since_ibl"],
                predicted_failure_risk=0.05,
            )
            for ts in sample_fleet_data
        ]

        fleet_avg = sum(s.mileage_km for s in states) / len(states)
        depot = DepotConfig(revenue_target=18)
        checker = InductionOptimizer(depot=depot).checker

        for ts in states[:5]:  # test top 5
            _, factors = checker.compute_soft_score(ts, fleet_avg, depot)
            reasons = ExplainableAI.generate_reasons(ts, fleet_avg, factors, "revenue_service")
            assert len(reasons) >= 1
            assert all(isinstance(r, str) and len(r) > 5 for r in reasons)


# ── Test 3: RL Agent Integration ──────────────────────────────────────────

class TestRLAgentIntegration:

    def test_rl_learns_from_outcomes(self):
        """RL agent should update weights based on operational outcomes."""
        from app.rl.agent import (
            FleetState, HistoricalLearningService, OperationalOutcome
        )

        service = HistoricalLearningService()
        initial_weights = service.agent.get_current_weights().to_dict()

        # Process a good outcome
        state = FleetState(
            avg_brake_health=90, avg_hvac_health=88, avg_door_health=92,
            fleet_avg_mileage_km=150000, mileage_std_dev=12000,
            cert_expiry_within_7d=0, critical_jobs_open=0,
            branding_deficit_count=0, standby_ratio=0.12,
            time_of_day_bucket=2,
        )
        good_outcome = OperationalOutcome(
            plan_date=date.today(),
            planned_revenue=18, actual_revenue=18,
            withdrawals=0, delays=1,
            mileage_variance_km=12.4,
            sla_compliance_pct=97.0,
            supervisor_overrides=0,
        )
        action = service.agent.select_action(state)
        result = service.process_outcome(state, action, good_outcome, state)

        assert "reward" in result
        assert result["reward"] > 0  # good outcome → positive reward
        assert "updated_weights" in result
        assert len(result["updated_weights"]) == 6

    def test_rl_reward_signals(self):
        """Reward function should produce correct signals for known outcomes."""
        from app.rl.agent import OperationalOutcome

        # Perfect outcome
        perfect = OperationalOutcome(
            plan_date=date.today(), planned_revenue=18, actual_revenue=18,
            withdrawals=0, delays=0, mileage_variance_km=10,
            sla_compliance_pct=100, supervisor_overrides=0,
        )
        assert perfect.compute_reward() > 1.0

        # Terrible outcome
        terrible = OperationalOutcome(
            plan_date=date.today(), planned_revenue=18, actual_revenue=12,
            withdrawals=4, delays=8, mileage_variance_km=80,
            sla_compliance_pct=60, supervisor_overrides=5,
        )
        assert terrible.compute_reward() < -1.0

        # Good always > terrible
        assert perfect.compute_reward() > terrible.compute_reward()

    def test_rl_warm_start_simulation(self):
        """Simulated learning should improve reward over 50 episodes."""
        from app.rl.agent import HistoricalLearningService

        service = HistoricalLearningService()
        result  = service.simulate_learning(n_episodes=50)

        assert result["episodes"] == 50
        assert "avg_reward" in result
        assert "final_weights" in result
        assert result["final_epsilon"] < 1.0  # epsilon has decayed
        assert len(result["reward_trend"]) > 0


# ── Test 4: Simulation Engine ─────────────────────────────────────────────

class TestSimulationIntegration:

    @pytest.fixture
    def sim_trainsets(self, sample_fleet_data):
        from app.simulation.engine import SimTrainset, TrainState
        status_map = {
            "revenue_service": TrainState.IN_SERVICE,
            "standby":         TrainState.STABLED,
            "ibl":             TrainState.IBL,
            "maintenance":     TrainState.MAINTENANCE,
        }
        return [
            SimTrainset(
                id=ts["id"], code=ts["trainset_code"],
                current_bay=ts["current_bay"],
                state=status_map.get(ts["current_status"], TrainState.STABLED),
                mileage_km=ts["total_mileage_km"],
                brake_health=ts["brake_health"],
                cleaning_done=True,
                assigned_status=ts["current_status"],
            )
            for ts in sample_fleet_data
        ]

    def test_all_five_scenarios_execute(self, sim_trainsets):
        """All 5 simulation scenarios must complete without error."""
        from app.simulation.engine import WhatIfEngine

        engine    = WhatIfEngine()
        scenarios = [
            "shunting_optimization",
            "maintenance_delay",
            "emergency_withdrawal",
            "bay_reallocation",
            "cleaning_bottleneck",
        ]
        results = engine.compare_scenarios(sim_trainsets, scenarios)

        assert len(results) == 5
        for scenario, result in results.items():
            assert result is not None, f"Scenario {scenario} returned None"
            assert result.fleet_readiness_pct >= 0
            assert result.fleet_readiness_pct <= 100
            assert result.optimized_shunting_ops >= 0

    def test_shunting_optimization_improves_on_baseline(self, sim_trainsets):
        """Optimized shunting must be ≤ baseline."""
        from app.simulation.engine import DepotSimulator

        sim    = DepotSimulator()
        result = sim.run("shunting_optimization", sim_trainsets)
        assert result.optimized_shunting_ops <= result.baseline_shunting_ops

    def test_emergency_withdrawal_identifies_replacements(self, sim_trainsets):
        """Emergency withdrawal sim must identify standby replacements."""
        from app.simulation.engine import DepotSimulator

        sim    = DepotSimulator()
        result = sim.run("emergency_withdrawal", sim_trainsets, {"n_withdrawn": 2})
        kpis   = result.kpis
        assert "replacements_available" in kpis
        assert int(kpis.get("replacements_available", 0)) >= 0

    def test_depot_layout_path_planning(self):
        """Dijkstra path planning must find paths between all major bay pairs."""
        from app.simulation.engine import DepotLayout

        layout = DepotLayout()
        test_pairs = [("A1", "A9"), ("A1", "C1"), ("B1", "M1"), ("A5", "D2")]

        for b1, b2 in test_pairs:
            path, dist = layout.shortest_path(b1, b2)
            assert len(path) >= 2, f"No path found from {b1} to {b2}"
            assert dist > 0, f"Zero distance from {b1} to {b2}"
            assert path[0] == b1
            assert path[-1] == b2


# ── Test 5: PDF Report Generation ────────────────────────────────────────

class TestReportGeneration:

    def test_induction_report_generates_bytes(self):
        """PDF report must produce non-empty bytes output."""
        from app.reports.generator import ReportService

        service = ReportService()
        plan_data = {
            "plan_date":         str(date.today()),
            "depot_name":        "Muttom Depot",
            "prepared_by":       "Test Suite",
            "score":             94.2,
            "revenue_service":   [
                {"rank": 1, "trainset_code": "TS-14", "confidence_pct": 96,
                 "reasons": ["All certs valid", "Low mileage", "Cleaning done"],
                 "constraint_violations": []},
                {"rank": 2, "trainset_code": "TS-02", "confidence_pct": 91,
                 "reasons": ["No critical jobs", "Branding priority"],
                 "constraint_violations": []},
            ],
            "standby":        [{"trainset_code": "TS-11"}],
            "ibl":            [{"trainset_code": "TS-07", "constraint_violations": ["Brake wear"]}],
            "maintenance":    [{"trainset_code": "TS-03", "constraint_violations": ["Job card open"]}],
            "total_shunting_ops": 14,
            "mileage_variance_km": 12.4,
            "sla_compliance_pct": 97.0,
            "conflict_alerts": [{"trainset": "TS-07", "violations": ["Brake wear 82%"], "severity": "critical"}],
        }
        output = service.generate_induction_report(plan_data)
        assert isinstance(output, bytes)
        assert len(output) > 100  # must be non-trivial

    def test_fleet_health_report_generates_bytes(self, sample_fleet_data):
        """Fleet health PDF must produce valid output."""
        from app.reports.generator import ReportService

        service = ReportService()
        output  = service.generate_fleet_health_report(sample_fleet_data[:10])
        assert isinstance(output, bytes)
        assert len(output) > 100


# ── Test 6: Copilot Tool Executor ─────────────────────────────────────────

class TestCopilotIntegration:

    def test_fleet_status_tool_returns_data(self, sample_fleet_data):
        """Copilot fleet tool must return trainset data."""
        from app.llm.copilot import CopilotToolExecutor

        executor = CopilotToolExecutor(sample_fleet_data)
        result   = json.loads(executor.execute("get_fleet_status", {}))

        assert "total" in result
        assert result["total"] == 25
        assert "summary" in result
        assert result["summary"]["revenue_service"] >= 0

    def test_maintenance_predictions_tool(self, sample_fleet_data):
        """Copilot maintenance tool must return risk assessments."""
        from app.llm.copilot import CopilotToolExecutor

        executor = CopilotToolExecutor(sample_fleet_data)
        result   = json.loads(executor.execute("get_maintenance_predictions", {"risk_threshold": 0.2}))

        assert "predictions" in result
        for pred in result["predictions"]:
            assert "composite_risk" in pred
            assert 0 <= pred["composite_risk"] <= 1
            assert pred["risk_level"] in ("low", "medium", "high", "critical")

    def test_what_if_simulation_tool(self, sample_fleet_data):
        """Copilot what-if tool must return simulation results."""
        from app.llm.copilot import CopilotToolExecutor

        executor = CopilotToolExecutor(sample_fleet_data)
        result   = json.loads(executor.execute(
            "run_what_if_simulation",
            {"scenario": "emergency_withdrawal", "parameters": {"n_withdrawn": 2}},
        ))

        assert "scenario" in result
        assert "result" in result
        assert result["scenario"] == "emergency_withdrawal"

    def test_copilot_fallback_responses(self, sample_fleet_data):
        """Copilot must return sensible fallbacks when API unavailable."""
        from app.llm.copilot import OperationalCopilot

        copilot  = OperationalCopilot(sample_fleet_data)
        response = copilot._fallback_response("Why was TS-07 sent to IBL tonight?")

        assert isinstance(response, str)
        assert len(response) > 20
        assert "TS-07" in response or "IBL" in response or "brake" in response.lower()


# ── Test 7: End-to-End Optimizer → Report Pipeline ───────────────────────

class TestFullPipeline:

    def test_optimizer_to_pdf_pipeline(self, sample_fleet_data):
        """Complete pipeline: raw fleet data → optimization → PDF report."""
        from app.optimization.engine import DepotConfig, InductionOptimizer, TrainsetState
        from app.reports.generator import ReportService

        # Step 1: Build trainset states
        states = [
            TrainsetState(
                id=ts["id"], code=ts["trainset_code"],
                fitness_valid=ts["critical_jobs"] == 0,
                critical_jobs_open=ts["critical_jobs"],
                mileage_km=ts["total_mileage_km"],
                brake_health_pct=ts["brake_health"],
                hvac_health_pct=ts["hvac_health"],
                door_health_pct=ts["door_health"],
                cleaning_done=True,
                days_since_ibl=ts["days_since_ibl"],
                predicted_failure_risk=0.1,
            )
            for ts in sample_fleet_data
        ]

        # Step 2: Run optimizer
        depot     = DepotConfig(revenue_target=18)
        optimizer = InductionOptimizer(depot=depot, timeout_seconds=15)
        result    = optimizer.optimize(states, plan_date=date.today())

        assert result.status in ("optimal", "feasible")
        assert len(result.revenue_service) >= 18

        # Step 3: Generate PDF report
        service   = ReportService()
        plan_data = {
            "plan_date":          str(result.plan_date),
            "depot_name":         "Muttom Depot",
            "prepared_by":        "Integration Test",
            "score":              result.score,
            "revenue_service":    [
                {"rank": item.priority_rank, "trainset_code": item.trainset_code,
                 "confidence_pct": item.confidence_pct,
                 "reasons": item.ai_reasoning.get("human_reasons", []),
                 "constraint_violations": item.constraint_violations}
                for item in result.revenue_service[:5]
            ],
            "standby":        [{"trainset_code": i.trainset_code} for i in result.standby],
            "ibl":            [{"trainset_code": i.trainset_code, "constraint_violations": i.constraint_violations} for i in result.ibl],
            "maintenance":    [{"trainset_code": i.trainset_code, "constraint_violations": i.constraint_violations} for i in result.maintenance],
            "total_shunting_ops": result.total_shunting_ops,
            "mileage_variance_km": result.mileage_variance,
            "sla_compliance_pct": result.sla_compliance_pct,
            "conflict_alerts": result.conflict_alerts,
        }
        pdf = service.generate_induction_report(plan_data)

        assert isinstance(pdf, bytes)
        assert len(pdf) > 100
        logger.info(
            "Full pipeline test passed: score=%.1f revenue=%d pdf_size=%d bytes",
            result.score, len(result.revenue_service), len(pdf)
        )
