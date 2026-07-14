"""
KMRL NexusAI — Shadow Mode & Safe Rollout Controller
======================================================
Enterprise AI systems for safety-critical operations NEVER go directly
autonomous. This module implements a three-phase rollout model:

  Phase 1 — ADVISORY:    AI suggests only. Human makes every decision.
                         Suggestions shown alongside manual plan.
                         No automation. Override always available.

  Phase 2 — ASSISTED:    Human must approve each AI recommendation.
                         One-click approval per trainset assignment.
                         Full reasoning shown. Explicit approval logged.

  Phase 3 — AUTONOMOUS:  AI executes with human supervision.
                         Human can intervene at any point.
                         Emergency stop always available.
                         Limited to pre-approved scenarios.

Shadow Mode (parallel validation):
  AI plan generated nightly alongside manual plan.
  Both executed independently.
  Differences tracked and analyzed.
  Used for 30–90 day parallel running period.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

logger = logging.getLogger(__name__)


# ── Mode Definitions ──────────────────────────────────────────────────────

class OperationMode(str, Enum):
    ADVISORY   = "advisory"    # AI suggests, human decides
    ASSISTED   = "assisted"    # Human approves per item
    AUTONOMOUS = "autonomous"  # AI executes, human supervises
    SHADOW     = "shadow"      # Parallel run — AI not actioned


class ApprovalStatus(str, Enum):
    PENDING  = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    MODIFIED = "modified"    # human changed AI recommendation


# ── Mode Configuration ────────────────────────────────────────────────────

@dataclass
class ModeConfig:
    """
    Per-deployment mode configuration.
    Controlled by Ops Manager or Admin only.
    """
    mode:                  OperationMode = OperationMode.ADVISORY
    approval_timeout_mins: int  = 30         # pending → auto-reject after this
    require_reason_on_override: bool = True
    allow_bulk_approve:    bool = False       # approve all in one click
    autonomous_max_revenue_changes: int = 3  # max trainsets AI can move without approval
    shadow_duration_days:  int  = 30         # minimum shadow period before assisted
    assisted_duration_days: int = 30         # minimum assisted period before autonomous
    emergency_stop_enabled: bool = True
    notify_on_every_change: bool = True

    # Scenarios allowed in autonomous mode (must be explicitly whitelisted)
    autonomous_allowed_scenarios: list[str] = field(default_factory=lambda: [
        "cleaning_slot_assignment",
        "standby_rotation",
        "mileage_rebalancing",
    ])
    # Scenarios ALWAYS requiring human approval, even in autonomous mode
    always_require_approval: list[str] = field(default_factory=lambda: [
        "safety_override",
        "certificate_bypass",
        "ibl_deferral",
        "emergency_withdrawal",
    ])


# ── Plan Comparison ────────────────────────────────────────────────────────

@dataclass
class PlanDifference:
    """Records a difference between AI plan and manual/previous plan."""
    trainset_code:   str
    ai_assignment:   str    # what AI recommended
    human_assignment: str   # what human chose
    ai_confidence:   float
    ai_reasoning:    list[str]
    outcome:         str | None = None   # filled in next day
    human_was_right: bool | None = None  # post-outcome assessment


@dataclass
class ShadowRunResult:
    """Result of one shadow run (AI plan vs manual plan)."""
    run_date:         date
    ai_plan_id:       str
    manual_plan_id:   str | None
    differences:      list[PlanDifference]
    agreements:       int        # number of matching assignments
    disagreements:    int
    agreement_rate:   float      # agreements / total
    ai_score:         float
    manual_score:     float | None = None
    notes:            str = ""


# ── Approval Request ──────────────────────────────────────────────────────

@dataclass
class ApprovalRequest:
    """A single AI recommendation awaiting human approval."""
    request_id:      str = field(default_factory=lambda: str(uuid4())[:8])
    plan_id:         str = ""
    trainset_code:   str = ""
    ai_assignment:   str = ""
    confidence_pct:  float = 0.0
    ai_reasoning:    list[str] = field(default_factory=list)
    constraint_violations: list[str] = field(default_factory=list)
    status:          ApprovalStatus = ApprovalStatus.PENDING
    approved_by:     str | None = None
    approved_at:     datetime | None = None
    human_override:  str | None = None   # if modified, what human chose instead
    override_reason: str | None = None
    created_at:      datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at:      datetime | None = None


# ── Override Log ──────────────────────────────────────────────────────────

@dataclass
class OverrideEvent:
    """Records every human override of an AI recommendation."""
    event_id:        str = field(default_factory=lambda: str(uuid4())[:8])
    plan_date:       date = field(default_factory=date.today)
    trainset_code:   str = ""
    ai_recommendation: str = ""
    human_decision:  str = ""
    reason:          str = ""
    operator_id:     str = ""
    operator_role:   str = ""
    ai_confidence:   float = 0.0
    outcome:         str | None = None   # "ai_was_right" | "human_was_right" | "unclear"
    created_at:      datetime = field(default_factory=lambda: datetime.now(timezone.utc))


# ── Shadow Mode Engine ────────────────────────────────────────────────────

class ShadowModeEngine:
    """
    Runs AI planning in parallel with manual process.
    Does NOT action the AI plan — records for comparison only.
    Used during the initial 30–90 day validation period.
    """

    def __init__(self, config: ModeConfig):
        self.config   = config
        self.run_history: list[ShadowRunResult] = []

    def compare_plans(
        self,
        ai_plan: dict[str, Any],
        manual_plan: dict[str, Any] | None = None,
    ) -> ShadowRunResult:
        """
        Compare AI plan against manual plan (or previous day's plan).
        Records every difference for outcome tracking.
        """
        run_date = date.fromisoformat(ai_plan.get("plan_date", str(date.today())))

        # Build lookup: trainset → assignment
        ai_assignments = {
            item["trainset_code"]: item["assigned_status"]
            for category in ["revenue_service", "standby", "ibl", "maintenance"]
            for item in ai_plan.get(category, [])
        }

        manual_assignments: dict[str, str] = {}
        if manual_plan:
            for category in ["revenue_service", "standby", "ibl", "maintenance"]:
                for item in manual_plan.get(category, []):
                    code = item.get("trainset_code", item.get("code", ""))
                    manual_assignments[code] = category

        differences: list[PlanDifference] = []
        agreements   = 0

        for code, ai_status in ai_assignments.items():
            manual_status = manual_assignments.get(code)
            if manual_status and ai_status == manual_status:
                agreements += 1
            elif manual_status and ai_status != manual_status:
                # Find confidence for this trainset
                confidence = 0.0
                for item in ai_plan.get("revenue_service", []):
                    if item.get("trainset_code") == code:
                        confidence = item.get("confidence_pct", 0.0)
                        break

                differences.append(PlanDifference(
                    trainset_code=code,
                    ai_assignment=ai_status,
                    human_assignment=manual_status,
                    ai_confidence=confidence,
                    ai_reasoning=next(
                        (item.get("reasoning", {}).get("human_reasons", [])
                         for item in ai_plan.get("revenue_service", [])
                         if item.get("trainset_code") == code),
                        [],
                    ),
                ))

        total = agreements + len(differences)
        agreement_rate = agreements / max(total, 1)

        result = ShadowRunResult(
            run_date=run_date,
            ai_plan_id=ai_plan.get("plan_id", ""),
            manual_plan_id=manual_plan.get("plan_id") if manual_plan else None,
            differences=differences,
            agreements=agreements,
            disagreements=len(differences),
            agreement_rate=round(agreement_rate, 3),
            ai_score=ai_plan.get("score", 0.0),
        )
        self.run_history.append(result)

        logger.info(
            "Shadow run %s: agreement=%.1f%% (%d/%d) differences=%d",
            run_date, agreement_rate * 100, agreements, total, len(differences)
        )
        return result

    def is_ready_for_assisted_mode(self) -> tuple[bool, str]:
        """
        Returns (ready, reason) based on shadow mode performance.
        Requirements for promotion to ASSISTED:
          - Minimum shadow duration met
          - Agreement rate >= 85% for last 7 days
          - No safety violations in AI plan
          - Formal approval from Ops Manager
        """
        if len(self.run_history) < self.config.shadow_duration_days:
            days_remaining = self.config.shadow_duration_days - len(self.run_history)
            return False, f"Minimum shadow period not met — {days_remaining} more days required"

        recent = self.run_history[-7:]
        avg_agreement = sum(r.agreement_rate for r in recent) / len(recent)

        if avg_agreement < 0.85:
            return False, f"Agreement rate {avg_agreement:.1%} below 85% threshold (last 7 days)"

        return True, f"Ready for ASSISTED mode — {avg_agreement:.1%} agreement over last 7 days"

    def get_validation_report(self) -> dict[str, Any]:
        """Generate shadow mode validation report for Ops Manager review."""
        if not self.run_history:
            return {"status": "no_data", "runs": 0}

        total_runs   = len(self.run_history)
        total_diffs  = sum(r.disagreements for r in self.run_history)
        avg_agreement = sum(r.agreement_rate for r in self.run_history) / total_runs

        # Categorize differences
        ai_ibl_human_revenue = sum(
            1 for r in self.run_history for d in r.differences
            if d.ai_assignment == "ibl" and d.human_assignment == "revenue_service"
        )
        ai_revenue_human_ibl = sum(
            1 for r in self.run_history for d in r.differences
            if d.ai_assignment == "revenue_service" and d.human_assignment == "ibl"
        )

        ready, reason = self.is_ready_for_assisted_mode()

        return {
            "shadow_days_completed": total_runs,
            "total_differences":     total_diffs,
            "avg_agreement_rate":    round(avg_agreement, 3),
            "last_7_day_agreement":  round(
                sum(r.agreement_rate for r in self.run_history[-7:]) / min(7, total_runs), 3
            ),
            "ai_more_conservative":  ai_ibl_human_revenue,  # AI sent to IBL, human kept in revenue
            "ai_more_aggressive":    ai_revenue_human_ibl,  # AI put in revenue, human sent to IBL
            "ready_for_assisted":    ready,
            "promotion_status":      reason,
            "recommendation":        "PROMOTE to ASSISTED mode" if ready else "CONTINUE shadow validation",
        }


# ── Approval Workflow (Assisted Mode) ─────────────────────────────────────

class ApprovalWorkflow:
    """
    Manages human approval of AI recommendations in ASSISTED mode.
    Every trainset assignment requires explicit operator approval.
    """

    def __init__(self, config: ModeConfig):
        self.config   = config
        self.pending: dict[str, ApprovalRequest] = {}    # request_id → request
        self.log:     list[ApprovalRequest]       = []
        self.overrides: list[OverrideEvent]       = []

    def create_approval_batch(
        self,
        plan: dict[str, Any],
    ) -> list[ApprovalRequest]:
        """Create approval requests for all AI assignments in the plan."""
        requests = []
        expires = datetime.now(timezone.utc) + timedelta(minutes=self.config.approval_timeout_mins)

        for category in ["revenue_service", "standby", "ibl", "maintenance"]:
            for item in plan.get(category, []):
                # Determine if this requires mandatory human review
                has_violations = bool(item.get("constraint_violations"))
                always_review  = any(
                    v in self.config.always_require_approval
                    for v in item.get("constraint_violations", [])
                )

                req = ApprovalRequest(
                    plan_id=plan.get("plan_id", ""),
                    trainset_code=item.get("trainset_code", ""),
                    ai_assignment=category,
                    confidence_pct=item.get("confidence_pct", 0.0),
                    ai_reasoning=item.get("reasoning", {}).get("human_reasons", []),
                    constraint_violations=item.get("constraint_violations", []),
                    expires_at=expires,
                    status=ApprovalStatus.PENDING,
                )
                self.pending[req.request_id] = req
                requests.append(req)

        logger.info("Created %d approval requests for plan %s", len(requests), plan.get("plan_id"))
        return requests

    def approve(
        self,
        request_id: str,
        operator_id: str,
        operator_role: str,
    ) -> bool:
        """Approve an AI recommendation as-is."""
        req = self.pending.get(request_id)
        if not req or req.status != ApprovalStatus.PENDING:
            return False

        req.status      = ApprovalStatus.APPROVED
        req.approved_by = operator_id
        req.approved_at = datetime.now(timezone.utc)
        self.log.append(req)
        del self.pending[request_id]

        logger.info("Approved: %s → %s by %s", req.trainset_code, req.ai_assignment, operator_id)
        return True

    def reject_with_override(
        self,
        request_id: str,
        human_assignment: str,
        reason: str,
        operator_id: str,
        operator_role: str,
    ) -> bool:
        """Reject AI recommendation and specify human decision instead."""
        req = self.pending.get(request_id)
        if not req:
            return False

        if self.config.require_reason_on_override and not reason.strip():
            logger.warning("Override reason required but not provided for %s", req.trainset_code)
            return False

        req.status         = ApprovalStatus.MODIFIED
        req.approved_by    = operator_id
        req.approved_at    = datetime.now(timezone.utc)
        req.human_override = human_assignment
        req.override_reason = reason
        self.log.append(req)
        del self.pending[request_id]

        # Record override event for analytics
        self.overrides.append(OverrideEvent(
            plan_date=date.today(),
            trainset_code=req.trainset_code,
            ai_recommendation=req.ai_assignment,
            human_decision=human_assignment,
            reason=reason,
            operator_id=operator_id,
            operator_role=operator_role,
            ai_confidence=req.confidence_pct,
        ))

        logger.info(
            "Override: %s AI=%s → Human=%s by %s (%s)",
            req.trainset_code, req.ai_assignment, human_assignment, operator_id, reason[:50]
        )
        return True

    def approve_all_pending(self, operator_id: str, operator_role: str) -> int:
        """Bulk approve all pending requests (only allowed if config permits)."""
        if not self.config.allow_bulk_approve:
            logger.warning("Bulk approve attempted but not permitted in current config")
            return 0

        count = 0
        for req_id in list(self.pending.keys()):
            if self.approve(req_id, operator_id, operator_role):
                count += 1
        return count

    def expire_stale_requests(self) -> list[str]:
        """Expire requests that have been pending too long."""
        now      = datetime.now(timezone.utc)
        expired  = []
        for req_id, req in list(self.pending.items()):
            if req.expires_at and now > req.expires_at:
                req.status = ApprovalStatus.REJECTED
                self.log.append(req)
                del self.pending[req_id]
                expired.append(req.trainset_code)
                logger.warning("Approval expired for %s — manual planning required", req.trainset_code)
        return expired

    def get_pending_count(self) -> int:
        return len(self.pending)

    def get_override_analytics(self) -> dict[str, Any]:
        """Analyze override patterns to improve AI model."""
        if not self.overrides:
            return {"total_overrides": 0}

        total   = len(self.overrides)
        by_role = {}
        for ov in self.overrides:
            by_role[ov.operator_role] = by_role.get(ov.operator_role, 0) + 1

        top_reasons = {}
        for ov in self.overrides:
            reason_key = ov.reason[:50] if ov.reason else "no_reason"
            top_reasons[reason_key] = top_reasons.get(reason_key, 0) + 1
        top_reasons = dict(sorted(top_reasons.items(), key=lambda x: x[1], reverse=True)[:5])

        most_overridden = {}
        for ov in self.overrides:
            most_overridden[ov.trainset_code] = most_overridden.get(ov.trainset_code, 0) + 1

        return {
            "total_overrides": total,
            "by_role":         by_role,
            "top_reasons":     top_reasons,
            "most_overridden_trainsets": dict(
                sorted(most_overridden.items(), key=lambda x: x[1], reverse=True)[:5]
            ),
            "avg_ai_confidence_at_override": round(
                sum(o.ai_confidence for o in self.overrides) / total, 1
            ),
        }


# ── Emergency Stop ────────────────────────────────────────────────────────

class EmergencyStop:
    """
    Immediately halts all autonomous AI actions and reverts to manual mode.
    Can be triggered by any operator in Depot Controller role or above.
    """

    def __init__(self, mode_config: ModeConfig):
        self.config     = mode_config
        self._activated = False
        self._reason    = ""
        self._by        = ""
        self._at: datetime | None = None

    def activate(self, reason: str, operator_id: str) -> dict[str, Any]:
        """Activate emergency stop — all autonomous actions halted."""
        self._activated = True
        self._reason    = reason
        self._by        = operator_id
        self._at        = datetime.now(timezone.utc)

        logger.critical(
            "EMERGENCY STOP ACTIVATED by %s: %s", operator_id, reason
        )

        # In production: publish to Redis pub/sub so all workers see it immediately
        return {
            "emergency_stop": True,
            "activated_by":   operator_id,
            "reason":         reason,
            "timestamp":      self._at.isoformat(),
            "actions":        [
                "All autonomous optimizer actions halted",
                "All pending Celery optimization tasks cancelled",
                "System reverted to ADVISORY mode",
                "Ops Manager notified via all channels",
                "Manual planning procedures activated",
            ],
        }

    def deactivate(self, operator_id: str, new_mode: OperationMode = OperationMode.ADVISORY) -> bool:
        """Deactivate emergency stop after situation resolved."""
        if not self._activated:
            return False
        self._activated = False
        self.config.mode = new_mode
        logger.warning("Emergency stop deactivated by %s — mode set to %s", operator_id, new_mode)
        return True

    @property
    def is_active(self) -> bool:
        return self._activated


# ── Mode Manager (singleton) ──────────────────────────────────────────────

class OperationModeManager:
    """
    Central controller for the system's operation mode.
    Persisted to Redis/DB so all service instances see the same mode.
    """

    def __init__(self, config: ModeConfig | None = None):
        self.config        = config or ModeConfig()
        self.shadow_engine = ShadowModeEngine(self.config)
        self.approval_wf   = ApprovalWorkflow(self.config)
        self.emergency     = EmergencyStop(self.config)
        self._mode_history: list[dict] = []

    @property
    def current_mode(self) -> OperationMode:
        if self.emergency.is_active:
            return OperationMode.ADVISORY
        return self.config.mode

    def transition_to(
        self,
        new_mode: OperationMode,
        approved_by: str,
        approval_reference: str,
    ) -> dict[str, Any]:
        """
        Transition to a new operation mode.
        Requires Ops Manager approval and audit trail.
        """
        old_mode = self.config.mode

        # Validate transition path
        valid_transitions = {
            OperationMode.SHADOW:     [OperationMode.ADVISORY],
            OperationMode.ADVISORY:   [OperationMode.ASSISTED, OperationMode.SHADOW],
            OperationMode.ASSISTED:   [OperationMode.AUTONOMOUS, OperationMode.ADVISORY],
            OperationMode.AUTONOMOUS: [OperationMode.ASSISTED, OperationMode.ADVISORY],
        }
        if new_mode not in valid_transitions.get(old_mode, []):
            return {
                "success": False,
                "error": f"Invalid transition {old_mode} → {new_mode}. "
                         f"Valid: {[m.value for m in valid_transitions.get(old_mode, [])]}",
            }

        # Check readiness for assisted mode
        if new_mode == OperationMode.ASSISTED:
            ready, reason = self.shadow_engine.is_ready_for_assisted_mode()
            if not ready:
                return {"success": False, "error": f"Not ready for ASSISTED mode: {reason}"}

        self.config.mode = new_mode
        event = {
            "from_mode":    old_mode.value,
            "to_mode":      new_mode.value,
            "approved_by":  approved_by,
            "approval_ref": approval_reference,
            "timestamp":    datetime.now(timezone.utc).isoformat(),
        }
        self._mode_history.append(event)

        logger.warning(
            "MODE TRANSITION: %s → %s (approved by %s, ref: %s)",
            old_mode.value, new_mode.value, approved_by, approval_reference
        )
        return {"success": True, "transition": event}

    def get_status(self) -> dict[str, Any]:
        return {
            "current_mode":     self.current_mode.value,
            "emergency_active": self.emergency.is_active,
            "pending_approvals": self.approval_wf.get_pending_count(),
            "shadow_days":      len(self.shadow_engine.run_history),
            "mode_history":     self._mode_history[-5:],
            "config": {
                "approval_timeout_mins": self.config.approval_timeout_mins,
                "require_reason":        self.config.require_reason_on_override,
                "autonomous_max_changes": self.config.autonomous_max_revenue_changes,
            },
        }
