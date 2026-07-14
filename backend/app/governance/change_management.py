"""
KMRL NexusAI — AI Governance & Change Management Workflows
============================================================
Formal governance processes for:
  - ML model approval before production deployment
  - Optimizer weight change approval
  - Operation mode transitions (shadow → assisted → autonomous)
  - Emergency override governance
  - Audit signoff trails
  - Release management & rollback approval
"""
from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

logger = logging.getLogger(__name__)


# ── Enums ──────────────────────────────────────────────────────────────────

class ApprovalState(str, Enum):
    DRAFT      = "draft"
    SUBMITTED  = "submitted"
    IN_REVIEW  = "in_review"
    APPROVED   = "approved"
    REJECTED   = "rejected"
    WITHDRAWN  = "withdrawn"
    EXPIRED    = "expired"


class ChangeType(str, Enum):
    ML_MODEL_DEPLOY    = "ml_model_deploy"
    OPTIMIZER_WEIGHTS  = "optimizer_weights"
    MODE_TRANSITION    = "mode_transition"
    FEATURE_RELEASE    = "feature_release"
    INFRA_CHANGE       = "infra_change"
    SECURITY_PATCH     = "security_patch"
    EMERGENCY_CHANGE   = "emergency_change"
    ROLLBACK           = "rollback"


class RiskLevel(str, Enum):
    LOW      = "low"      # cosmetic, no operational impact
    MEDIUM   = "medium"   # operational impact, easily reversible
    HIGH     = "high"     # significant operational impact
    CRITICAL = "critical" # safety or compliance impact


# ── Data Classes ────────────────────────────────────────────────────────────

@dataclass
class Approver:
    role:       str
    name:       str
    employee_id: str
    approved_at: datetime | None = None
    comments:   str = ""
    is_mandatory: bool = True


@dataclass
class ChangeRequest:
    """Formal change request requiring governance approval."""
    id:              str = field(default_factory=lambda: f"CR-{datetime.now().strftime('%Y%m%d')}-{str(uuid4())[:4].upper()}")
    change_type:     ChangeType = ChangeType.FEATURE_RELEASE
    risk_level:      RiskLevel = RiskLevel.MEDIUM
    title:           str = ""
    description:     str = ""
    justification:   str = ""
    rollback_plan:   str = ""
    test_evidence:   str = ""
    submitter_id:    str = ""
    state:           ApprovalState = ApprovalState.DRAFT
    required_approvers: list[Approver] = field(default_factory=list)
    created_at:      datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    planned_date:    date | None = None
    approved_at:     datetime | None = None
    deployed_at:     datetime | None = None
    artifact_hash:   str = ""      # SHA-256 of deployed artifact
    audit_trail:     list[dict] = field(default_factory=list)

    def add_audit_event(self, actor: str, action: str, detail: str = "") -> None:
        self.audit_trail.append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "actor":     actor,
            "action":    action,
            "detail":    detail,
        })

    @property
    def all_approved(self) -> bool:
        mandatory = [a for a in self.required_approvers if a.is_mandatory]
        return all(a.approved_at is not None for a in mandatory)

    @property
    def is_emergency(self) -> bool:
        return self.change_type == ChangeType.EMERGENCY_CHANGE


# ── ML Model Governance ─────────────────────────────────────────────────────

@dataclass
class MLModelApproval:
    """
    Formal approval record for ML model deployment.
    Required before any model goes to production.
    """
    approval_id:     str = field(default_factory=lambda: f"ML-APR-{str(uuid4())[:8].upper()}")
    model_name:      str = ""
    model_version:   str = ""
    model_type:      str = ""     # predictive_maintenance | readiness | anomaly | rl_agent
    artifact_path:   str = ""
    artifact_hash:   str = ""     # SHA-256 of model files
    training_date:   date | None = None
    training_data_period: str = ""   # e.g. "2024-01-01 to 2025-05-31 (500 samples)"

    # Performance metrics from validation
    metrics: dict[str, float] = field(default_factory=dict)
    # e.g. {"roc_auc": 0.89, "avg_precision": 0.72, "n_test_samples": 150}

    # Drift baseline (reference distribution for future PSI checks)
    drift_baseline_hash: str = ""

    # Safety checks
    bias_assessment:     str = ""    # assessed fairness across trainset age/manufacturer
    failure_mode_analysis: str = ""  # what happens when model is wrong?
    fallback_verified:   bool = False  # heuristic fallback tested?

    # Approvals required
    ml_engineer_approved: bool = False
    ml_engineer_id:       str = ""
    ml_engineer_approved_at: datetime | None = None

    platform_lead_approved: bool = False
    platform_lead_id:       str = ""
    platform_lead_approved_at: datetime | None = None

    ops_manager_approved:   bool = False
    ops_manager_id:         str = ""
    ops_manager_approved_at: datetime | None = None

    state: ApprovalState = ApprovalState.DRAFT
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    notes: str = ""

    @property
    def is_fully_approved(self) -> bool:
        return all([
            self.ml_engineer_approved,
            self.platform_lead_approved,
            self.ops_manager_approved,
        ])

    def meets_minimum_performance(self) -> tuple[bool, list[str]]:
        """Check if model meets minimum performance gates for deployment."""
        failures = []
        thresholds = {
            "roc_auc":       0.75,
            "avg_precision": 0.60,
        }
        for metric, threshold in thresholds.items():
            val = self.metrics.get(metric, 0.0)
            if val < threshold:
                failures.append(f"{metric} = {val:.3f} < minimum {threshold}")
        return len(failures) == 0, failures


class MLModelGovernanceService:
    """Manages the ML model approval lifecycle."""

    def __init__(self):
        self._pending: dict[str, MLModelApproval] = {}
        self._approved: list[MLModelApproval] = []

    def submit_for_approval(self, approval: MLModelApproval) -> str:
        """Submit model for approval review."""
        # Compute artifact hash
        approval.artifact_hash = self._compute_hash(approval.artifact_path)
        approval.state = ApprovalState.SUBMITTED

        # Auto-check: performance gate
        meets_gate, failures = approval.meets_minimum_performance()
        if not meets_gate:
            approval.state = ApprovalState.REJECTED
            approval.notes = f"Auto-rejected: performance gate failures: {failures}"
            logger.warning("ML model auto-rejected: %s — %s", approval.model_name, failures)
            return approval.approval_id

        # Auto-check: fallback verified
        if not approval.fallback_verified:
            approval.notes += "\nWARNING: Heuristic fallback not verified — must be confirmed before final approval"

        self._pending[approval.approval_id] = approval
        logger.info("ML model submitted for approval: %s v%s", approval.model_name, approval.model_version)
        return approval.approval_id

    def approve_ml_engineer(
        self, approval_id: str, engineer_id: str, notes: str = ""
    ) -> bool:
        appr = self._pending.get(approval_id)
        if not appr:
            return False
        appr.ml_engineer_approved    = True
        appr.ml_engineer_id          = engineer_id
        appr.ml_engineer_approved_at = datetime.now(timezone.utc)
        if notes:
            appr.notes += f"\nML Engineer ({engineer_id}): {notes}"
        logger.info("ML model approved by ML engineer %s: %s", engineer_id, appr.model_name)
        return True

    def approve_platform_lead(
        self, approval_id: str, lead_id: str, notes: str = ""
    ) -> bool:
        appr = self._pending.get(approval_id)
        if not appr:
            return False
        appr.platform_lead_approved    = True
        appr.platform_lead_id          = lead_id
        appr.platform_lead_approved_at = datetime.now(timezone.utc)
        if notes:
            appr.notes += f"\nPlatform Lead ({lead_id}): {notes}"
        return True

    def approve_ops_manager(
        self, approval_id: str, manager_id: str, notes: str = ""
    ) -> bool:
        appr = self._pending.get(approval_id)
        if not appr:
            return False
        appr.ops_manager_approved    = True
        appr.ops_manager_id          = manager_id
        appr.ops_manager_approved_at = datetime.now(timezone.utc)

        if appr.is_fully_approved:
            appr.state = ApprovalState.APPROVED
            self._approved.append(appr)
            del self._pending[approval_id]
            logger.warning(
                "ML MODEL APPROVED FOR PRODUCTION: %s v%s (hash=%s)",
                appr.model_name, appr.model_version, appr.artifact_hash[:12]
            )

        return True

    def reject(self, approval_id: str, rejector_id: str, reason: str) -> bool:
        appr = self._pending.get(approval_id)
        if not appr:
            return False
        appr.state = ApprovalState.REJECTED
        appr.notes += f"\nREJECTED by {rejector_id}: {reason}"
        self._approved.append(appr)
        del self._pending[approval_id]
        logger.warning("ML model rejected by %s: %s — %s", rejector_id, appr.model_name, reason)
        return True

    @staticmethod
    def _compute_hash(path: str) -> str:
        """Compute SHA-256 of model artifact for integrity verification."""
        import os
        if not os.path.exists(path):
            return f"path_not_found:{path}"
        h = hashlib.sha256()
        try:
            with open(path, "rb") as f:
                for chunk in iter(lambda: f.read(8192), b""):
                    h.update(chunk)
            return h.hexdigest()
        except Exception:
            return "hash_failed"


# ── Change Management ────────────────────────────────────────────────────────

class ChangeManagementService:
    """
    Manages change requests for all platform modifications.
    Enforces approval gates based on risk level.
    """

    # Approval matrix: risk level → required approvers
    APPROVAL_MATRIX = {
        RiskLevel.LOW: [
            Approver("platform_engineer", "", "", is_mandatory=True),
        ],
        RiskLevel.MEDIUM: [
            Approver("platform_lead", "", "", is_mandatory=True),
            Approver("ops_manager", "", "", is_mandatory=False),
        ],
        RiskLevel.HIGH: [
            Approver("platform_lead", "", "", is_mandatory=True),
            Approver("ops_manager", "", "", is_mandatory=True),
        ],
        RiskLevel.CRITICAL: [
            Approver("platform_lead", "", "", is_mandatory=True),
            Approver("ops_manager", "", "", is_mandatory=True),
            Approver("cto", "", "", is_mandatory=True),
        ],
    }

    # Blackout windows — no production changes
    BLACKOUT_HOURS = [(20, 23)]   # 20:00–23:00 IST (planning window)
    BLACKOUT_DAYS: list[str] = []  # e.g. public holidays

    def __init__(self):
        self._requests: dict[str, ChangeRequest] = {}

    def create_change_request(
        self,
        change_type: ChangeType,
        risk_level: RiskLevel,
        title: str,
        description: str,
        justification: str,
        rollback_plan: str,
        test_evidence: str,
        submitter_id: str,
        planned_date: date | None = None,
    ) -> ChangeRequest:
        """Create a new change request."""
        cr = ChangeRequest(
            change_type=change_type,
            risk_level=risk_level,
            title=title,
            description=description,
            justification=justification,
            rollback_plan=rollback_plan,
            test_evidence=test_evidence,
            submitter_id=submitter_id,
            planned_date=planned_date,
            required_approvers=[
                Approver(a.role, a.name, a.employee_id, is_mandatory=a.is_mandatory)
                for a in self.APPROVAL_MATRIX[risk_level]
            ],
        )
        cr.add_audit_event(submitter_id, "created", f"CR {cr.id} created")
        self._requests[cr.id] = cr
        logger.info("Change request created: %s (%s) by %s", cr.id, risk_level.value, submitter_id)
        return cr

    def submit_for_review(self, cr_id: str, submitter_id: str) -> bool:
        """Submit draft CR for approver review."""
        cr = self._requests.get(cr_id)
        if not cr or cr.state != ApprovalState.DRAFT:
            return False

        # Validate rollback plan exists
        if not cr.rollback_plan.strip():
            logger.warning("CR %s rejected — no rollback plan", cr_id)
            return False

        # Check blackout window
        if self._in_blackout_window() and not cr.is_emergency:
            logger.warning("CR %s cannot be deployed — blackout window active", cr_id)
            return False

        cr.state = ApprovalState.SUBMITTED
        cr.add_audit_event(submitter_id, "submitted", "Submitted for review")
        return True

    def approve(
        self,
        cr_id: str,
        approver_id: str,
        approver_role: str,
        comments: str = "",
    ) -> tuple[bool, str]:
        """Record an approval from an approver."""
        cr = self._requests.get(cr_id)
        if not cr:
            return False, "CR not found"
        if cr.state not in (ApprovalState.SUBMITTED, ApprovalState.IN_REVIEW):
            return False, f"CR in state {cr.state.value} — cannot approve"

        # Find matching approver slot
        for approver in cr.required_approvers:
            if approver.role == approver_role and approver.approved_at is None:
                approver.employee_id  = approver_id
                approver.approved_at  = datetime.now(timezone.utc)
                approver.comments     = comments
                cr.state = ApprovalState.IN_REVIEW
                cr.add_audit_event(approver_id, "approved", f"Role: {approver_role}")
                break
        else:
            return False, f"No pending approval slot for role {approver_role}"

        # Check if fully approved
        if cr.all_approved:
            cr.state = ApprovalState.APPROVED
            cr.approved_at = datetime.now(timezone.utc)
            cr.add_audit_event("system", "fully_approved", "All required approvals received")
            logger.warning("CHANGE REQUEST FULLY APPROVED: %s — %s", cr.id, cr.title)

        return True, "Approval recorded"

    def reject(self, cr_id: str, rejector_id: str, reason: str) -> bool:
        cr = self._requests.get(cr_id)
        if not cr:
            return False
        cr.state = ApprovalState.REJECTED
        cr.add_audit_event(rejector_id, "rejected", reason)
        return True

    def record_deployment(self, cr_id: str, deployer_id: str, artifact_hash: str) -> bool:
        """Record that a change was deployed."""
        cr = self._requests.get(cr_id)
        if not cr or cr.state != ApprovalState.APPROVED:
            return False
        cr.deployed_at    = datetime.now(timezone.utc)
        cr.artifact_hash  = artifact_hash
        cr.add_audit_event(deployer_id, "deployed", f"Hash: {artifact_hash[:12]}")
        logger.warning("CHANGE DEPLOYED: %s by %s (hash=%s)", cr.id, deployer_id, artifact_hash[:12])
        return True

    def create_emergency_change(
        self,
        title: str,
        description: str,
        justification: str,
        rollback_plan: str,
        submitter_id: str,
    ) -> ChangeRequest:
        """Emergency changes — require CTO + Ops Manager approval post-hoc."""
        cr = self.create_change_request(
            change_type=ChangeType.EMERGENCY_CHANGE,
            risk_level=RiskLevel.CRITICAL,
            title=f"[EMERGENCY] {title}",
            description=description,
            justification=justification,
            rollback_plan=rollback_plan,
            test_evidence="Emergency — post-deployment testing required",
            submitter_id=submitter_id,
        )
        cr.state = ApprovalState.IN_REVIEW
        cr.add_audit_event(submitter_id, "emergency_deployed", "Post-hoc approval required within 24h")
        logger.critical("EMERGENCY CHANGE CREATED: %s — approvals required within 24h", cr.id)
        return cr

    @staticmethod
    def _in_blackout_window() -> bool:
        """Check if current time falls within a deployment blackout window."""
        now_ist = datetime.now(timezone.utc) + timedelta(hours=5, minutes=30)
        for start_h, end_h in ChangeManagementService.BLACKOUT_HOURS:
            if start_h <= now_ist.hour < end_h:
                return True
        return False

    def get_pending_approvals(self, approver_role: str) -> list[ChangeRequest]:
        """Get all CRs waiting for a specific role's approval."""
        return [
            cr for cr in self._requests.values()
            if cr.state in (ApprovalState.SUBMITTED, ApprovalState.IN_REVIEW)
            and any(
                a.role == approver_role and a.approved_at is None
                for a in cr.required_approvers
            )
        ]

    def get_audit_summary(self, from_date: date, to_date: date) -> dict[str, Any]:
        """Governance audit summary for compliance reporting."""
        relevant = [
            cr for cr in self._requests.values()
            if cr.created_at.date() >= from_date and cr.created_at.date() <= to_date
        ]
        return {
            "period":            f"{from_date} to {to_date}",
            "total_changes":     len(relevant),
            "by_risk_level":     {
                level.value: sum(1 for cr in relevant if cr.risk_level == level)
                for level in RiskLevel
            },
            "by_state":          {
                state.value: sum(1 for cr in relevant if cr.state == state)
                for state in ApprovalState
            },
            "emergency_changes": sum(1 for cr in relevant if cr.is_emergency),
            "avg_approval_time_hours": self._avg_approval_time(relevant),
            "blackout_violations": 0,   # should always be 0
        }

    @staticmethod
    def _avg_approval_time(changes: list[ChangeRequest]) -> float:
        approved = [
            cr for cr in changes
            if cr.approved_at and cr.state == ApprovalState.APPROVED
        ]
        if not approved:
            return 0.0
        times = [
            (cr.approved_at - cr.created_at).total_seconds() / 3600
            for cr in approved
        ]
        return round(sum(times) / len(times), 1)
