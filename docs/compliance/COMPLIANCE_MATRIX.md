# KMRL NexusAI — Compliance & Regulatory Readiness Matrix
## CERT-In · ISO 27001 · DPDPA 2023 · Railway Safety Requirements

---

## Executive Summary

KMRL NexusAI operates within India's government railway infrastructure.
Compliance obligations span three primary frameworks:

| Framework | Applicability | Status | Evidence Location |
|-----------|--------------|--------|-------------------|
| **CERT-In Directions 2022** | Mandatory (CRIT infra) | ✅ Implemented | Section A |
| **ISO/IEC 27001:2022** | Voluntary (Best Practice) | ✅ Aligned | Section B |
| **DPDPA 2023 (Digital Personal Data)** | Mandatory | ✅ Implemented | Section C |
| **RDSO Guidelines (AI in Railways)** | Advisory | ✅ Aligned | Section D |
| **CIS Controls v8** | Best Practice | ✅ Implemented | Section E |

---

## Section A — CERT-In Directions 2022 Compliance

CERT-In (Indian Computer Emergency Response Team) issued mandatory directions
for all critical information infrastructure operators on April 28, 2022.

### A1. ICT Infrastructure Synchronised with NTP (Direction 2(a))

**Requirement**: Synchronize ICT systems with National Time Protocol (NTP) server of NIC or STQC.

**Implementation**:
```yaml
# Kubernetes NTP configuration — all nodes sync to NIC NTP
apiVersion: v1
kind: ConfigMap
metadata:
  name: ntp-config
  namespace: kube-system
data:
  chrony.conf: |
    server time.stpi.in iburst    # NIC primary NTP
    server samay1.nic.in iburst   # NIC secondary NTP
    server time.gov.in iburst     # Government backup
    makestep 1.0 3
    rtcsync
    logdir /var/log/chrony
```

**Evidence**: NTP sync logs in `/var/log/chrony/tracking.log` on all nodes.
**Verification**: `chronyc tracking | grep "System time"` — should show < 1ms offset.

---

### A2. Maintain Logs for 180 Days (Direction 2(b))

**Requirement**: Maintain ICT system logs and enable log management for minimum 180 days.

**Implementation**:

```sql
-- Audit log retention: 1 year (exceeds 180-day requirement)
-- Configured in: infra/docker/docker-compose.yml
-- PostgreSQL: audit_logs table partitioned yearly, retained 2 years

-- Verify retention policy
SELECT
  schemaname, tablename, pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename))
FROM pg_tables
WHERE tablename LIKE 'audit_logs%'
ORDER BY tablename;
```

```yaml
# CloudWatch log retention: 1 year (365 days)
aws_cloudwatch_log_group:
  name: "/kmrl/nexusai/application"
  retention_in_days: 365    # exceeds 180-day requirement

# NGINX access logs: 180 days
nginx_log_rotation:
  rotate: 6
  frequency: monthly         # 6 months = 180 days
  compress: true
  delaycompress: true
```

**Evidence**: CloudWatch log groups, PostgreSQL partition retention, NGINX logrotate config.

---

### A3. Report Incidents to CERT-In Within 6 Hours (Direction 3)

**Requirement**: Report cybersecurity incidents to CERT-In within 6 hours of detection.

**Reportable incident types**: Data breach, ransomware, identity theft, website defacement, unauthorized access.

**Implementation**:

```python
# backend/app/security/cert_in_reporting.py

CERT_IN_PORTAL = "https://www.cert-in.org.in/Report.jsp"
CERT_IN_EMAIL  = "incident@cert-in.org.in"
CERT_IN_PHONE  = "+91-1800-11-4949"

MANDATORY_REPORT_TRIGGERS = [
    "unauthorized_access_detected",
    "data_exfiltration_detected",
    "ransomware_indicators",
    "ddos_attack",
    "website_defacement",
    "credential_compromise",
    "critical_infrastructure_attack",
]

async def assess_and_report_incident(incident: SecurityIncident) -> bool:
    """
    Automatically assess if incident requires CERT-In reporting.
    If yes, prepare report and alert security officer within 1 hour
    so 6-hour reporting window is met.
    """
    if incident.type not in MANDATORY_REPORT_TRIGGERS:
        return False

    # Prepare incident report
    report = {
        "organisation":         "Kochi Metro Rail Limited",
        "sector":               "Transportation / Critical Infrastructure",
        "incident_type":        incident.type,
        "detection_time":       incident.detected_at.isoformat(),
        "affected_systems":     incident.affected_systems,
        "estimated_impact":     incident.impact_assessment,
        "initial_response":     incident.response_taken,
        "contact_name":         "KMRL CISO",
        "contact_email":        "ciso@kmrl.in",
        "contact_phone":        "+91-484-2700000",
    }

    # Page security officer immediately
    await alert_security_officer(
        subject=f"CERT-In MANDATORY REPORT REQUIRED: {incident.type}",
        body=f"Report must be filed within 6 hours of detection at {incident.detected_at}.\n"
             f"Deadline: {(incident.detected_at + timedelta(hours=6)).isoformat()}\n\n"
             f"Report data:\n{json.dumps(report, indent=2)}",
        channels=["email", "sms", "whatsapp"],
    )
    return True
```

**Evidence**: Security incident log, CERT-In report submissions (stored in `docs/compliance/cert-in-reports/`).

---

### A4. Designated Point of Contact (Direction 2(c))

**Requirement**: Designate a Point of Contact for CERT-In coordination.

**Designation**:
```
Role: KMRL CISO (Chief Information Security Officer)
Name: [Designated Officer Name]
Email: ciso@kmrl.in
Phone: +91-484-2700000 (24x7)
Alternate: platform-lead@kmrl.in
```

---

## Section B — ISO/IEC 27001:2022 Control Alignment

### B1. Information Security Policies (Clause 5.2)

| Policy | Status | Review Frequency | Owner |
|--------|--------|-----------------|-------|
| Information Security Policy | ✅ Documented | Annual | CISO |
| Access Control Policy | ✅ Implemented (RBAC + Vault) | Annual | Platform Lead |
| Cryptography Policy | ✅ Implemented (TLS 1.3, Vault Transit) | Annual | Security Team |
| Physical Security Policy | See KMRL Data Center Policy | Annual | Facilities |
| Incident Response Policy | ✅ Documented (DR Runbook) | Semi-annual | Platform Lead |
| Business Continuity Policy | ✅ Documented (BCP document) | Annual | Ops Manager |
| Supplier Security Policy | ✅ AWS BAA, vendor assessments | Annual | CISO |

### B2. Risk Assessment (Clause 6.1)

**Risk Register** (top risks):

| Risk ID | Risk | Likelihood | Impact | Residual Risk | Control |
|---------|------|-----------|--------|---------------|---------|
| R-001 | AI optimizer produces unsafe induction plan | Low | Critical | Low | Hard constraint engine + human override |
| R-002 | Database breach exposing trainset operational data | Low | High | Very Low | Vault encryption + RBAC + WAF |
| R-003 | Optimizer unavailable during planning window | Medium | High | Low | Celery retry + heuristic fallback |
| R-004 | ML model drift causes poor predictions | Medium | Medium | Low | PSI drift detection + auto-retrain |
| R-005 | Insider threat (rogue operator override) | Low | High | Low | Audit logs + override approval chain |
| R-006 | Third-party dependency (OR-Tools, Anthropic) unavailable | Low | Medium | Low | Fallback heuristics for both |
| R-007 | Key personnel unavailable during planning window | Medium | Medium | Low | On-call rotation + documented runbooks |

### B3. Access Control (Annex A 5.15–5.18)

```
✅ Unique user accounts (no shared credentials)
✅ Role-based access control (6 roles)
✅ Least-privilege principle enforced
✅ Privileged access management via Vault
✅ MFA for all privileged users
✅ Access review quarterly (Keycloak audit export)
✅ Immediate revocation on role change (Keycloak + JWT expiry)
✅ Separation of duties (optimizer approval requires Ops Manager)
```

### B4. Cryptography (Annex A 8.24)

```
✅ Data in transit: TLS 1.3 (NGINX config enforced)
✅ Data at rest: AES-256 via Vault Transit for PII
✅ Database: PostgreSQL SCRAM-SHA-256 authentication
✅ JWT signing: HMAC-SHA256 with 256-bit key
✅ Backups: AWS S3 SSE-KMS encryption
✅ Key management: AWS KMS + HashiCorp Vault
✅ Certificate management: cert-manager + Let's Encrypt
✅ Key rotation: Vault Transit auto-rotation every 90 days
```

### B5. Logging and Monitoring (Annex A 8.15–8.16)

```
✅ Centralized logging: CloudWatch + Loki
✅ Security event logging: audit_logs table + CloudWatch
✅ Log integrity: CloudWatch log group encryption
✅ Retention: 365 days (exceeds ISO minimum)
✅ SIEM alerts: Prometheus alerting rules
✅ Incident detection: Automated via security tests
✅ Log review: Weekly automated anomaly detection
```

---

## Section C — DPDPA 2023 (Digital Personal Data Protection Act)

### C1. Personal Data Inventory

| Data Category | Data Elements | Storage | Retention | Legal Basis |
|--------------|--------------|---------|-----------|-------------|
| Employee data | Name, email, employee ID, role | `users` table | Active employment + 2 years | Employment contract |
| Operational logs | User actions with employee ID | `audit_logs` | 2 years | Legitimate interest (safety) |
| Authentication data | Hashed passwords, TOTP secrets | `users`, Redis | Active account only | Contractual necessity |
| Access logs | IP addresses, timestamps | CloudWatch | 180 days | Legal obligation (CERT-In) |

**Note**: KMRL NexusAI does NOT process:
- Passenger personal data
- Biometric data
- Financial data
- Health data (of employees)

### C2. Data Principal Rights Implementation

```python
# backend/app/security/dpdpa.py

async def handle_data_access_request(employee_id: str) -> dict:
    """Right of Access (Section 11 DPDPA) — respond within 72 hours."""
    return {
        "personal_data": await fetch_user_data(employee_id),
        "audit_log_summary": await fetch_audit_summary(employee_id),
        "data_categories": ["identity", "operational_actions"],
        "retention_period": "Active employment + 2 years",
        "processors": ["AWS (India region)", "Anthropic (LLM copilot queries only)"],
    }

async def handle_erasure_request(employee_id: str, reason: str) -> dict:
    """Right of Erasure (Section 12 DPDPA) — with exceptions for safety logs."""
    # Safety audit logs CANNOT be erased (legal obligation)
    # PII CAN be anonymized from non-safety records
    await anonymize_user_records(employee_id)
    return {"status": "anonymized", "safety_logs_retained": True,
            "reason": "Safety audit logs retained per Railway Safety Act requirements"}
```

### C3. Data Processor Agreement (Anthropic)

```
The LLM Copilot sends operational query text to Anthropic's API.
Queries MUST NOT contain:
  - Employee names or IDs
  - Personally identifiable information
  - Sensitive operational security data

Implementation: Copilot context includes fleet codes (TS-07) but never
employee personal details. Verified in: backend/app/llm/copilot.py
```

---

## Section D — RDSO Guidelines for AI in Railways

The Research Designs and Standards Organisation (RDSO) has issued advisory
guidelines for AI deployment in Indian railway operations.

### D1. Human-in-the-Loop Requirement

**Requirement**: AI shall not take safety-critical decisions autonomously without human oversight.

**Implementation**: Shadow Mode Controller (`backend/app/shadow_mode/controller.py`)
- Phase 1 (ADVISORY): AI suggests only — fully compliant
- Phase 2 (ASSISTED): Human approves each recommendation — compliant
- Phase 3 (AUTONOMOUS): Human can override at any time; safety checks hardcoded

**Evidence**: `OperationMode` enum, `ApprovalWorkflow` class, `EmergencyStop` class.

### D2. Explainability Requirement

**Requirement**: AI decisions affecting train operations must be explainable.

**Implementation**: SHAP-based explainability (`backend/app/optimization/engine.py`)
- Every recommendation includes `human_reasons` (plain English)
- SHAP feature importance for top-5 factors
- Hard constraint violations explicitly listed
- `ai_reasoning` JSON stored with every `induction_plan_items` record

### D3. Fail-Safe Requirement

**Requirement**: System failure must not compromise railway operations.

**Implementation**:
- Heuristic fallback when ML models unavailable
- Advisory mode always available as fallback
- Manual spreadsheet procedure documented in BCP
- Emergency stop available to any authorized operator

### D4. Auditability

**Requirement**: Complete audit trail of all AI-influenced decisions.

**Implementation**: `audit_logs` table captures every user action including AI plan approvals,
overrides, and status changes with operator ID, timestamp, IP address, and before/after values.

---

## Section E — Compliance Evidence Collection

### Quarterly Evidence Package

Compile and store in `docs/compliance/evidence/YYYY-QX/`:

```bash
#!/bin/bash
# Run quarterly: make compliance-evidence

QUARTER=$(date +%Y-Q$(( ($(date +%-m)-1)/3+1 )))
mkdir -p docs/compliance/evidence/$QUARTER

# 1. Access review export from Keycloak
echo "Exporting user access review..."
kcadm.sh get users -r kmrl > docs/compliance/evidence/$QUARTER/user-access-review.json

# 2. Failed authentication attempts (CERT-In requirement)
echo "Exporting security events..."
aws cloudwatch get-metric-statistics \
  --namespace KMRLNexusAI \
  --metric-name FailedAuthAttempts \
  --start-time $(date -d '90 days ago' -u +%Y-%m-%dT%H:%M:%SZ) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%SZ) \
  --period 86400 --statistics Sum \
  > docs/compliance/evidence/$QUARTER/auth-failures.json

# 3. Encryption verification
echo "Verifying encryption status..."
aws kms list-keys --query 'Keys[*].KeyId' \
  > docs/compliance/evidence/$QUARTER/kms-keys.json

# 4. Backup verification result
echo "Latest backup status..."
velero backup get -o json | jq '[.items[] | {name, status, startTimestamp}] | sort_by(.startTimestamp) | last(.[])' \
  > docs/compliance/evidence/$QUARTER/backup-status.json

# 5. Vulnerability scan results
echo "Running Trivy scan..."
trivy image ghcr.io/kmrl/nexusai-api:latest --format json \
  > docs/compliance/evidence/$QUARTER/trivy-results.json

# 6. Override analytics (AI governance)
psql $DATABASE_URL -c "\copy (
  SELECT DATE_TRUNC('day', created_at), COUNT(*), COUNT(DISTINCT user_id)
  FROM audit_logs WHERE action = 'trainset_status_override'
  AND created_at > NOW() - INTERVAL '90 days'
  GROUP BY 1 ORDER BY 1
) TO 'docs/compliance/evidence/$QUARTER/override-analytics.csv' CSV HEADER"

echo "Evidence package ready: docs/compliance/evidence/$QUARTER/"
```

---

## Annual Compliance Calendar

| Month | Activity | Owner |
|-------|----------|-------|
| January | DPDPA data inventory review | CISO |
| February | ISO 27001 internal audit | Platform Lead |
| March | CERT-In readiness drill | Security Team |
| April | Annual access review (all users) | Platform Lead |
| May | DR drill — full scenario | Platform Lead |
| June | Risk register review | CISO + Platform |
| July | Vendor security assessment (AWS, Anthropic) | CISO |
| August | Penetration test (external firm) | CISO |
| September | Policy review cycle | All owners |
| October | ISO 27001 surveillance audit | External auditor |
| November | FinOps annual review | Finance + Platform |
| December | Annual SLA review + compliance report | Management |
