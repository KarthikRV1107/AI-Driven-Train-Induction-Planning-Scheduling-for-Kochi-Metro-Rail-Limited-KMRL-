# KMRL NexusAI — Site Reliability Engineering Model
## Service Level Indicators, Objectives & Error Budgets

---

## SLI/SLO Definitions

### Tier 1 — Safety-Critical (NEVER BREACH)

These protect operational safety. Breach triggers immediate incident.

| SLI | Measurement | SLO | Consequence of Breach |
|-----|-------------|-----|-----------------------|
| Hard constraint enforcement | % of induction plans with zero safety violations (expired certs, open critical jobs deployed to revenue) | **100%** | P0 Incident — Emergency stop |
| Emergency stop responsiveness | Time from trigger to all autonomous actions halted | **< 5 seconds** | P0 Incident |
| Override always available | % uptime of override capability for any operator | **100%** | P0 Incident |
| Audit log completeness | % of user actions successfully written to audit_logs | **100%** | P0 Incident |

### Tier 2 — Operational (30-day error budget)

| SLI | Measurement | SLO | Monthly Error Budget |
|-----|-------------|-----|---------------------|
| Optimizer availability | % of nightly planning windows (21:00–23:00 IST) where optimizer produces a plan | **99.5%** | 3.6 hours/month |
| Optimizer solve time | % of optimize calls completing in < 35 seconds | **95%** | 5% of calls |
| Fleet availability prediction accuracy | % of plans where AI fleet availability forecast matches actual ± 5% | **92%** | 8% of plans |
| API availability | % of 5-minute windows with < 1% error rate | **99.5%** | 3.6 hours/month |
| API p95 latency | % of requests served in < 500ms | **95%** | 5% of requests |

### Tier 3 — Experience (90-day error budget)

| SLI | Measurement | SLO | Quarterly Error Budget |
|-----|-------------|-----|-----------------------|
| Dashboard load time | % of page loads < 2 seconds | **90%** | 10% of loads |
| WebSocket uptime | % of 5-min windows with active connections available | **99%** | 21.6 hours/quarter |
| ML prediction freshness | % of predictions using a model trained within last 7 days | **95%** | 5% of predictions |
| Alert delivery latency | % of critical alerts delivered within 2 minutes | **95%** | 5% of alerts |
| PDF export success rate | % of report export requests succeeding | **99%** | 1% of requests |

---

## Error Budget Policy

```
Error Budget Remaining    Action Required
─────────────────────────────────────────────────────
> 50%                     Normal operations
25–50%                    Review reliability work in sprint
10–25%                    Freeze new feature work; focus reliability
< 10%                     Full reliability sprint; no new features
0% (exhausted)            Freeze all changes; incident review required
```

**Error budget burn rate alert**: If budget burns at > 5× normal rate for 1 hour, page on-call SRE.

---

## Incident Severity Levels

| Severity | Definition | Response Time | Resolution Target | Escalation |
|----------|------------|--------------|-------------------|------------|
| **P0** | Safety constraint violated OR emergency stop triggered OR system prevents morning service | Immediate (< 5 min) | < 2 hours | CEO, GM Operations, Platform CTO |
| **P1** | Optimizer unavailable during planning window OR fleet data inaccessible | < 15 minutes | < 4 hours | Ops Manager, Platform Lead |
| **P2** | Degraded optimizer performance OR ML model unavailable (heuristic fallback active) | < 30 minutes | < 8 hours | On-call engineer |
| **P3** | Non-critical feature degraded (analytics, PDF export, copilot) | < 2 hours | < 24 hours | Platform team |
| **P4** | Cosmetic issue, minor UX bug, non-urgent | Next business day | < 1 week | Product team |

---

## On-Call Rotation

```yaml
on_call_schedule:
  primary:
    rotation: weekly
    coverage: 24x7
    role: platform-engineer
    tools: [PagerDuty, Slack #kmrl-oncall, phone]

  secondary:
    rotation: weekly
    coverage: business-hours
    role: ai-ml-engineer
    escalation_after: 15_minutes

  escalation_chain:
    - tier_1: primary-on-call (0–15 min)
    - tier_2: platform-lead   (15–30 min)
    - tier_3: ops-manager     (30–60 min)
    - tier_4: cto             (60+ min, P0/P1 only)

  contact_methods:
    primary: PagerDuty mobile app
    backup:  WhatsApp +91-98xx-xxxxxx
    final:   Direct phone call
```

---

## Incident Response Runbook

### P0: Safety Constraint Violated

```
IMMEDIATE ACTIONS (< 5 minutes):
  1. ACTIVATE emergency stop:
     POST /api/v1/admin/emergency-stop
     {"reason": "Safety constraint violated", "operator_id": "YOUR_ID"}

  2. Revert to manual planning:
     Notify Depot Controller to use manual spreadsheet process

  3. Preserve evidence:
     kubectl logs deployment/kmrl-api -n kmrl-production > /tmp/p0-$(date +%Y%m%d-%H%M).log
     kubectl exec -it postgres-0 -- pg_dump -U kmrl kmrl_nexusai > /tmp/p0-db.sql

  4. Page all tiers immediately

INVESTIGATION (< 30 minutes):
  5. Query which plan violated constraints:
     SELECT pi.*, ts.trainset_code, ip.plan_date
     FROM induction_plan_items pi
     JOIN trainsets ts ON pi.trainset_id = ts.id
     JOIN induction_plans ip ON pi.plan_id = ip.id
     WHERE pi.assigned_status = 'revenue_service'
       AND cardinality(pi.constraint_violations) > 0
     ORDER BY ip.plan_date DESC LIMIT 20;

  6. Identify root cause:
     - Was it an optimizer bug? Check constraint_violations in plan_json
     - Was it a data sync issue? Check fitness_certificates.expiry_date
     - Was it a human override that bypassed safety? Check audit_logs

RESOLUTION:
  7. Fix root cause
  8. Re-run optimizer with corrected data
  9. Manual review of corrected plan before execution
  10. Deactivate emergency stop after Ops Manager sign-off

POST-INCIDENT:
  11. Write incident report within 24 hours (template: docs/INCIDENT_TEMPLATE.md)
  12. 5-why root cause analysis
  13. Add regression test to test_suite.py
  14. Schedule post-mortem within 72 hours
```

### P1: Optimizer Unavailable During Planning Window

```
IMMEDIATE ACTIONS (< 15 minutes):
  1. Check API health:
     curl https://api.nexusai.kmrl.in/health

  2. Check optimizer worker status:
     kubectl get pods -l app=kmrl-worker-optimization -n kmrl-production
     kubectl logs -l app=kmrl-worker-optimization -n kmrl-production --tail=100

  3. Check Celery queue:
     kubectl exec -it $(kubectl get pod -l app=redis -o name | head -1) \
       -- redis-cli LLEN celery:optimization

  4. Manual trigger optimizer:
     kubectl exec -it deploy/kmrl-api -- \
       celery -A app.workers.celery_app call workers.run_nightly_optimization

  5. If optimizer fails, activate ADVISORY mode + manual planning

ESCALATION: If not resolved in 30 minutes → page Platform Lead
```

---

## Service Level Monitoring

### Prometheus SLO Recording Rules

```yaml
# prometheus/rules/slo-rules.yml
groups:
  - name: kmrl.slos
    interval: 60s
    rules:

      # Optimizer availability (30-day window)
      - record: kmrl:optimizer_availability:ratio_30d
        expr: |
          sum_over_time(
            (kmrl_optimization_score > 0)[30d:1h]
          ) / (30 * 24)

      # API error rate (5-minute windows)
      - record: kmrl:api_error_rate:ratio_5m
        expr: |
          rate(http_requests_total{status=~"5.."}[5m]) /
          rate(http_requests_total[5m])

      # Optimizer p95 solve time
      - record: kmrl:optimizer_p95_solve_time
        expr: |
          histogram_quantile(0.95,
            rate(kmrl_optimization_duration_seconds_bucket[1h])
          )

      # Error budget remaining (monthly)
      - record: kmrl:api_error_budget_remaining
        expr: |
          1 - (
            sum_over_time(kmrl:api_error_rate:ratio_5m[30d]) /
            (30 * 24 * 12)   # 12 five-minute windows per hour
          ) / 0.005          # 0.5% error budget

      # Burn rate alert (5x normal for 1h)
      - alert: ErrorBudgetBurnRateHigh
        expr: |
          kmrl:api_error_rate:ratio_5m > 5 * 0.005
        for: 1h
        labels:
          severity: warning
        annotations:
          summary: "Error budget burning 5x faster than normal"
```

---

## SLO Review Cadence

| Review | Frequency | Participants | Output |
|--------|-----------|-------------|--------|
| Error budget check | Weekly | Platform team | Budget status, burn rate |
| SLO performance review | Monthly | Platform + Ops | SLO report, adjustments |
| SLI definition review | Quarterly | All teams | Updated SLI/SLO targets |
| Incident post-mortem | After every P0/P1 | Platform + Ops + Management | Action items |
| Annual SLA review | Yearly | Management + KMRL leadership | Contractual SLA update |

---

## Capacity Planning

### Current Capacity Thresholds

| Resource | Current | Alert At | Expand At |
|----------|---------|----------|-----------|
| API pods | 3 (HPA max 10) | 8 pods sustained > 30 min | Add node pool |
| DB connections | 20 pool | 16 active | Increase pool |
| Redis memory | 1 GB | 800 MB | Upgrade tier |
| Kafka storage | 50 GB | 40 GB | Expand retention |
| ML model storage | 20 GB PVC | 15 GB | Add PVC |
| Optimizer CPU | 4 vCPU limit | 3.5 vCPU sustained | Add workers |

### Fleet Growth Capacity Impact

```
25 trainsets (current):  Optimizer < 15s, API < 200ms p95
30 trainsets (Phase 2):  Optimizer < 20s, API < 250ms p95 — no infra change
40 trainsets (Phase 3):  Optimizer < 30s, API < 300ms p95 — add 1 optimizer worker
50 trainsets (Phase 4):  Optimizer < 45s, API < 400ms p95 — distributed optimizer
```
