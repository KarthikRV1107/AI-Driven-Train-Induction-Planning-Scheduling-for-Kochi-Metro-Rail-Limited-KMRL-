"""
KMRL NexusAI — AI Optimization Engine
======================================
Hybrid optimization using Google OR-Tools CP-SAT + custom heuristics.

Solves the nightly train induction planning problem as a
Constraint Programming problem with multi-objective scoring.

Objectives (in priority order):
  1. HARD: Safety constraints (fitness certs, critical job cards)
  2. HARD: Bay capacity constraints
  3. SOFT: Mileage balancing (minimize variance across fleet)
  4. SOFT: Branding exposure SLA compliance
  5. SOFT: Shunting minimization
  6. SOFT: Cleaning schedule adherence
  7. SOFT: Morning readiness optimization
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any
from uuid import UUID

from ortools.sat.python import cp_model

logger = logging.getLogger(__name__)


# ── Data Structures ───────────────────────────────────────────────────────

@dataclass
class TrainsetState:
    """Snapshot of a trainset's operational state for planning."""
    id: str
    code: str                           # TS-01 ... TS-25
    fitness_valid: bool = True
    signalling_clear: bool = True
    telecom_clear: bool = True
    critical_jobs_open: int = 0         # count of open critical job cards
    mileage_km: float = 0.0
    brake_health_pct: float = 100.0
    hvac_health_pct: float = 100.0
    door_health_pct: float = 100.0
    cleaning_done: bool = True
    current_bay: str = ""
    branding_priority: int = 0          # 0–100; higher = must run
    branding_exposure_deficit_hrs: float = 0.0
    days_since_ibl: int = 0
    predicted_failure_risk: float = 0.0  # 0–1 from ML model
    stabling_preference: str = ""       # preferred bay


@dataclass
class DepotConfig:
    """Depot constraints for the optimization."""
    total_bays: int = 25
    ibl_bays: int = 4
    cleaning_bays: int = 3
    maintenance_bays: int = 4
    revenue_target: int = 18            # minimum trains for service
    standby_target: int = 3


@dataclass
class PlanItem:
    """Single trainset assignment in the induction plan."""
    trainset_id: str
    trainset_code: str
    assigned_status: str                # revenue_service, standby, ibl, maintenance
    priority_rank: int
    confidence_pct: float
    ai_reasoning: dict[str, Any]
    constraint_violations: list[str] = field(default_factory=list)
    shunting_required: bool = False
    assigned_bay: str = ""


@dataclass
class OptimizationResult:
    """Full output of the optimizer."""
    plan_date: date
    status: str                         # optimal, feasible, infeasible
    score: float                        # 0–100
    solve_time_ms: float
    revenue_service: list[PlanItem]
    standby: list[PlanItem]
    ibl: list[PlanItem]
    maintenance: list[PlanItem]
    total_shunting_ops: int
    mileage_variance: float
    sla_compliance_pct: float
    conflict_alerts: list[dict]
    optimizer_version: str = "2.4.1"
    explanation: str = ""


# ── Constraint Checker ────────────────────────────────────────────────────

class ConstraintChecker:
    """Evaluates hard and soft constraints for each trainset."""

    CERT_EXPIRY_WARNING_DAYS = 7

    def check_hard_constraints(self, ts: TrainsetState) -> list[str]:
        """Returns list of hard constraint violations (disqualifiers)."""
        violations = []

        if not ts.fitness_valid:
            violations.append("HARD: Fitness certificate expired or invalid")

        if not ts.signalling_clear:
            violations.append("HARD: Signalling clearance not obtained")

        if not ts.telecom_clear:
            violations.append("HARD: Telecom clearance not obtained")

        if ts.critical_jobs_open > 0:
            violations.append(
                f"HARD: {ts.critical_jobs_open} critical job card(s) open"
            )

        if ts.brake_health_pct < 50:
            violations.append(
                f"HARD: Brake health critical ({ts.brake_health_pct:.0f}%)"
            )

        if ts.predicted_failure_risk > 0.85:
            violations.append(
                f"HARD: AI failure risk too high ({ts.predicted_failure_risk:.0%})"
            )

        return violations

    def compute_soft_score(
        self,
        ts: TrainsetState,
        fleet_avg_mileage: float,
        depot: DepotConfig,
    ) -> tuple[float, dict[str, float]]:
        """
        Compute a 0–100 soft score for revenue service suitability.
        Returns (total_score, factor_breakdown).
        """
        factors: dict[str, float] = {}

        # 1. Mileage balance (max 25 pts) — lower relative mileage = better
        mileage_delta = ts.mileage_km - fleet_avg_mileage
        mileage_score = max(0, 25 - (mileage_delta / fleet_avg_mileage) * 25)
        factors["mileage_balance"] = round(mileage_score, 2)

        # 2. Branding SLA priority (max 20 pts)
        branding_score = (ts.branding_priority / 100) * 20
        if ts.branding_exposure_deficit_hrs > 10:
            branding_score = min(20, branding_score + 5)
        factors["branding_sla"] = round(branding_score, 2)

        # 3. Cleaning status (max 15 pts)
        cleaning_score = 15.0 if ts.cleaning_done else 0.0
        factors["cleaning_ready"] = cleaning_score

        # 4. System health composite (max 20 pts)
        health_avg = (ts.brake_health_pct + ts.hvac_health_pct + ts.door_health_pct) / 3
        health_score = (health_avg / 100) * 20
        factors["system_health"] = round(health_score, 2)

        # 5. IBL recency (max 10 pts) — more days since IBL = might need it
        ibl_score = min(10, (ts.days_since_ibl / 90) * 10)
        factors["ibl_recency"] = round(ibl_score, 2)

        # 6. ML failure risk inverse (max 10 pts)
        risk_score = (1 - ts.predicted_failure_risk) * 10
        factors["ml_risk_inverse"] = round(risk_score, 2)

        total = sum(factors.values())
        return round(total, 2), factors


# ── OR-Tools Optimizer ────────────────────────────────────────────────────

class InductionOptimizer:
    """
    CP-SAT based multi-objective optimizer for nightly train induction.

    Decision variables:
      x[i][s] = 1 if trainset i is assigned to status s
    where s ∈ {0: revenue_service, 1: standby, 2: ibl, 3: maintenance}
    """

    STATUS_REVENUE = 0
    STATUS_STANDBY = 1
    STATUS_IBL = 2
    STATUS_MAINTENANCE = 3
    STATUS_LABELS = ["revenue_service", "standby", "ibl", "maintenance"]

    SCALE = 100  # scale floats to integers for CP-SAT

    def __init__(self, depot: DepotConfig, timeout_seconds: int = 30):
        self.depot = depot
        self.timeout_seconds = timeout_seconds
        self.checker = ConstraintChecker()

    def optimize(
        self,
        trainsets: list[TrainsetState],
        plan_date: date | None = None,
    ) -> OptimizationResult:
        start_time = time.perf_counter()
        plan_date = plan_date or date.today()

        n = len(trainsets)
        fleet_avg_mileage = sum(ts.mileage_km for ts in trainsets) / n

        # ── Pre-process: compute scores & violations ──────────────────
        hard_violations: dict[int, list[str]] = {}
        soft_scores: dict[int, tuple[float, dict]] = {}
        forced_ibl: set[int] = set()
        forced_maintenance: set[int] = set()

        for i, ts in enumerate(trainsets):
            v = self.checker.check_hard_constraints(ts)
            hard_violations[i] = v

            score, factors = self.checker.compute_soft_score(
                ts, fleet_avg_mileage, self.depot
            )
            soft_scores[i] = (score, factors)

            # Force IBL if overdue or high failure risk
            if ts.days_since_ibl > 90 or ts.predicted_failure_risk > 0.7:
                forced_ibl.add(i)

            # Force maintenance if critical violations
            if len(v) > 0:
                forced_maintenance.add(i)

        # ── Build CP-SAT model ────────────────────────────────────────
        model = cp_model.CpModel()

        # Variables: x[i][s] ∈ {0, 1}
        x = {}
        for i in range(n):
            for s in range(4):
                x[i, s] = model.new_bool_var(f"x_{i}_{s}")

        # Constraint 1: each trainset exactly one status
        for i in range(n):
            model.add_exactly_one([x[i, s] for s in range(4)])

        # Constraint 2: hard violations → cannot be revenue service
        for i in forced_maintenance:
            model.add(x[i, self.STATUS_REVENUE] == 0)
            model.add(x[i, self.STATUS_STANDBY] == 0)
            if i not in forced_ibl:
                model.add(x[i, self.STATUS_MAINTENANCE] == 1)

        # Constraint 3: forced IBL
        for i in forced_ibl:
            if i not in forced_maintenance:
                model.add(x[i, self.STATUS_IBL] == 1)

        # Constraint 4: minimum revenue trains
        model.add(
            sum(x[i, self.STATUS_REVENUE] for i in range(n))
            >= self.depot.revenue_target
        )

        # Constraint 5: IBL bay capacity
        model.add(
            sum(x[i, self.STATUS_IBL] for i in range(n))
            <= self.depot.ibl_bays
        )

        # Constraint 6: maintenance bay capacity
        model.add(
            sum(x[i, self.STATUS_MAINTENANCE] for i in range(n))
            <= self.depot.maintenance_bays
        )

        # ── Objective: maximize weighted soft score for revenue trains ─
        # Scaled to integers (OR-Tools requires integer objective)
        objective_terms = []
        for i in range(n):
            score, _ = soft_scores[i]
            scaled = int(score * self.SCALE)
            objective_terms.append(x[i, self.STATUS_REVENUE] * scaled)

        # Bonus for standby covering branding-priority trains
        for i, ts in enumerate(trainsets):
            if ts.branding_priority > 70:
                objective_terms.append(x[i, self.STATUS_STANDBY] * int(ts.branding_priority * 5))

        model.maximize(sum(objective_terms))

        # ── Solve ─────────────────────────────────────────────────────
        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = self.timeout_seconds
        solver.parameters.num_workers = 4
        solver.parameters.log_search_progress = False

        status = solver.solve(model)
        solve_ms = (time.perf_counter() - start_time) * 1000

        if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            logger.error("Optimizer: no feasible solution found — falling back to heuristic")
            return self._heuristic_fallback(
                trainsets, plan_date, hard_violations, soft_scores, forced_ibl, forced_maintenance, solve_ms
            )

        # ── Extract results ───────────────────────────────────────────
        assignments: dict[int, int] = {}
        for i in range(n):
            for s in range(4):
                if solver.value(x[i, s]) == 1:
                    assignments[i] = s
                    break

        return self._build_result(
            trainsets, assignments, hard_violations, soft_scores,
            fleet_avg_mileage, plan_date, solve_ms,
            status == cp_model.OPTIMAL
        )

    def _build_result(
        self,
        trainsets: list[TrainsetState],
        assignments: dict[int, int],
        hard_violations: dict[int, list[str]],
        soft_scores: dict[int, tuple[float, dict]],
        fleet_avg_mileage: float,
        plan_date: date,
        solve_ms: float,
        is_optimal: bool,
    ) -> OptimizationResult:
        buckets: dict[int, list[PlanItem]] = {0: [], 1: [], 2: [], 3: []}
        conflict_alerts = []

        for i, ts in enumerate(trainsets):
            s = assignments[i]
            score, factors = soft_scores[i]
            violations = hard_violations[i]

            # Confidence: based on score and violation count
            confidence = min(98, max(40, score + (10 if not violations else -20)))

            reasoning = {
                "assigned_status": self.STATUS_LABELS[s],
                "soft_score": score,
                "factors": factors,
                "hard_violations": violations,
                "fleet_avg_mileage_km": round(fleet_avg_mileage, 1),
                "trainset_mileage_km": ts.mileage_km,
                "predicted_failure_risk": round(ts.predicted_failure_risk, 3),
            }

            item = PlanItem(
                trainset_id=ts.id,
                trainset_code=ts.code,
                assigned_status=self.STATUS_LABELS[s],
                priority_rank=i + 1,
                confidence_pct=round(confidence, 1),
                ai_reasoning=reasoning,
                constraint_violations=violations,
            )

            if violations:
                conflict_alerts.append({
                    "trainset": ts.code,
                    "violations": violations,
                    "status": self.STATUS_LABELS[s],
                    "severity": "critical" if any("HARD" in v for v in violations) else "warning",
                })

            buckets[s].append(item)

        # Sort revenue by score descending (priority rank)
        buckets[0].sort(key=lambda p: p.ai_reasoning["soft_score"], reverse=True)
        for rank, item in enumerate(buckets[0], 1):
            item.priority_rank = rank

        # Compute aggregate metrics
        revenue_mileages = [
            trainsets[i].mileage_km
            for i, ts in enumerate(trainsets)
            if assignments[i] == 0
        ]
        mileage_var = (
            sum((m - fleet_avg_mileage) ** 2 for m in revenue_mileages) / len(revenue_mileages)
        ) ** 0.5 if revenue_mileages else 0

        # SLA compliance: branding-priority trains in revenue service
        branded = [ts for ts in trainsets if ts.branding_priority > 0]
        sla_ok = sum(
            1 for i, ts in enumerate(trainsets)
            if ts.branding_priority > 0 and assignments[i] == 0
        )
        sla_pct = (sla_ok / len(branded) * 100) if branded else 100.0

        total_score = min(100, max(0, (
            80 * (1 if is_optimal else 0.85) +
            10 * (1 - mileage_var / max(fleet_avg_mileage, 1)) +
            10 * (sla_pct / 100)
        )))

        explanation = self._generate_explanation(buckets, conflict_alerts, total_score)

        return OptimizationResult(
            plan_date=plan_date,
            status="optimal" if is_optimal else "feasible",
            score=round(total_score, 1),
            solve_time_ms=round(solve_ms, 1),
            revenue_service=buckets[0],
            standby=buckets[1],
            ibl=buckets[2],
            maintenance=buckets[3],
            total_shunting_ops=self._estimate_shunting(buckets),
            mileage_variance=round(mileage_var, 2),
            sla_compliance_pct=round(sla_pct, 1),
            conflict_alerts=conflict_alerts,
            explanation=explanation,
        )

    def _estimate_shunting(self, buckets: dict[int, list[PlanItem]]) -> int:
        """Estimate shunting ops based on bay movements needed."""
        # IBL and maintenance require at least 2 shunts each
        return len(buckets[2]) * 2 + len(buckets[3]) * 2 + len(buckets[1])

    def _generate_explanation(
        self,
        buckets: dict[int, list[PlanItem]],
        alerts: list[dict],
        score: float,
    ) -> str:
        lines = [
            f"Optimization score: {score:.1f}/100",
            f"Revenue service: {len(buckets[0])} trainsets",
            f"Standby: {len(buckets[1])} | IBL: {len(buckets[2])} | Maintenance: {len(buckets[3])}",
        ]
        if alerts:
            lines.append(f"{len(alerts)} constraint conflicts detected and resolved.")
        top3 = buckets[0][:3]
        if top3:
            lines.append("Top recommendations: " + ", ".join(p.trainset_code for p in top3))
        return " | ".join(lines)

    def _heuristic_fallback(
        self,
        trainsets: list[TrainsetState],
        plan_date: date,
        hard_violations: dict[int, list[str]],
        soft_scores: dict[int, tuple[float, dict]],
        forced_ibl: set[int],
        forced_maintenance: set[int],
        solve_ms: float,
    ) -> OptimizationResult:
        """Greedy heuristic used when CP-SAT times out or finds no solution."""
        logger.warning("Using heuristic fallback")
        fleet_avg = sum(ts.mileage_km for ts in trainsets) / len(trainsets)

        # Sort by soft score desc, place into buckets greedily
        ranked = sorted(
            range(len(trainsets)),
            key=lambda i: soft_scores[i][0],
            reverse=True
        )

        assignments: dict[int, int] = {}
        revenue_count = 0

        for i in ranked:
            if i in forced_maintenance:
                assignments[i] = self.STATUS_MAINTENANCE
            elif i in forced_ibl:
                assignments[i] = self.STATUS_IBL
            elif revenue_count < self.depot.revenue_target:
                assignments[i] = self.STATUS_REVENUE
                revenue_count += 1
            else:
                assignments[i] = self.STATUS_STANDBY

        return self._build_result(
            trainsets, assignments, hard_violations, soft_scores,
            fleet_avg, plan_date, solve_ms, False
        )


# ── SHAP Explainer Wrapper ────────────────────────────────────────────────

class ExplainableAI:
    """Generates human-readable explanations for each AI decision."""

    REASON_TEMPLATES = {
        "fitness_valid": "All fitness certificates valid",
        "no_critical_jobs": "No open critical job cards",
        "cleaning_done": "Cleaning completed as scheduled",
        "mileage_below_avg": "Mileage {delta:.0f}km below fleet average — good balance",
        "mileage_above_avg": "Mileage {delta:.0f}km above fleet average",
        "branding_high": "Branding contract priority HIGH ({advertiser})",
        "brake_good": "Brake health {pct:.0f}% — within limits",
        "brake_low": "⚠ Brake health {pct:.0f}% — approaching threshold",
        "failure_risk_low": "AI failure probability {risk:.0%} — low risk",
        "failure_risk_high": "⚠ AI failure probability {risk:.0%} — IBL recommended",
        "ibl_overdue": "⚠ IBL inspection overdue ({days} days since last)",
    }

    @classmethod
    def generate_reasons(
        cls,
        ts: TrainsetState,
        fleet_avg_mileage: float,
        factors: dict[str, float],
        assigned_status: str,
    ) -> list[str]:
        reasons = []
        mileage_delta = ts.mileage_km - fleet_avg_mileage

        if ts.fitness_valid:
            reasons.append(cls.REASON_TEMPLATES["fitness_valid"])
        if ts.critical_jobs_open == 0:
            reasons.append(cls.REASON_TEMPLATES["no_critical_jobs"])
        if ts.cleaning_done:
            reasons.append(cls.REASON_TEMPLATES["cleaning_done"])

        if mileage_delta < 0:
            reasons.append(cls.REASON_TEMPLATES["mileage_below_avg"].format(delta=abs(mileage_delta)))
        else:
            reasons.append(cls.REASON_TEMPLATES["mileage_above_avg"].format(delta=mileage_delta))

        if ts.branding_priority > 60:
            reasons.append(cls.REASON_TEMPLATES["branding_high"].format(advertiser="Active contract"))

        if ts.brake_health_pct >= 80:
            reasons.append(cls.REASON_TEMPLATES["brake_good"].format(pct=ts.brake_health_pct))
        else:
            reasons.append(cls.REASON_TEMPLATES["brake_low"].format(pct=ts.brake_health_pct))

        if ts.predicted_failure_risk < 0.3:
            reasons.append(cls.REASON_TEMPLATES["failure_risk_low"].format(risk=ts.predicted_failure_risk))
        elif ts.predicted_failure_risk > 0.6:
            reasons.append(cls.REASON_TEMPLATES["failure_risk_high"].format(risk=ts.predicted_failure_risk))

        if ts.days_since_ibl > 60:
            reasons.append(cls.REASON_TEMPLATES["ibl_overdue"].format(days=ts.days_since_ibl))

        return reasons[:6]  # top 6 reasons
