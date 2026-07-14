# KMRL NexusAI — Disaster Recovery Runbook
## RTO/RPO Targets · Recovery Procedures · DR Drill Schedule

---

## RTO / RPO Definitions

| Component | RPO (Data Loss Tolerance) | RTO (Recovery Time Target) | Strategy |
|-----------|--------------------------|---------------------------|----------|
| **Induction Plans** | 0 — zero tolerance | < 15 minutes | Active-active DB replication |
| **Fleet Status Data** | 5 minutes | < 15 minutes | Redis Sentinel + DB replication |
| **Fitness Certificates** | 0 — zero tolerance | < 30 minutes | DB backup + point-in-time recovery |
| **ML Models** | 24 hours (retrain overnight) | < 2 hours | S3/MinIO cross-region copy |
| **Audit Logs** | 0 — zero tolerance | < 1 hour | DB replication + WAL archiving |
| **Historical Plans** | 1 hour | < 4 hours | Daily backup + WAL |
| **Telemetry Data** | 1 hour | < 4 hours | Kafka MirrorMaker + TimescaleDB |
| **Full Platform** | 15 minutes | **< 1 hour** | Multi-region active-active |

---

## Failure Scenarios & Recovery Procedures

---

### Scenario DR-01: Primary Region Total Loss (India South down)

**Trigger**: AWS India South (ap-south-1) complete outage or KMRL data center failure.

**Detection**: Cloudflare health check fails → PagerDuty alert → P0 incident.

**Recovery Steps**:

```bash
# Step 1: Confirm primary region is down (< 2 minutes)
aws ec2 describe-instance-status --region ap-south-1
# If no response within 30s → proceed with failover

# Step 2: Promote DR region (India West) to primary (< 5 minutes)
# Cloudflare: update DNS to point to india-west load balancer
# (Automated via Cloudflare Workers health check — triggers automatically)

# Step 3: Verify DR region is serving traffic (< 10 minutes)
curl -H "x-region: india-west" https://api.nexusai.kmrl.in/health
# Expected: {"status":"healthy","region":"india-west","role":"primary"}

# Step 4: Verify CockroachDB leadership transferred
kubectl exec -n kmrl-production cockroach-0 -- \
  cockroach node status --insecure
# Confirm all nodes showing "is_available=true" in india-west

# Step 5: Notify KMRL operations (< 15 minutes)
# Send SMS to Depot Controller, Ops Manager, GM Operations
# Template: "NexusAI is operating from backup region India West.
#            All data intact. Platform fully operational."

# Step 6: Verify nightly optimizer still scheduled
kubectl get cronjobs -n kmrl-production
kubectl get pods -l app=kmrl-celery-beat -n kmrl-production
# If beat pod is down, start it:
kubectl scale deployment kmrl-celery-beat --replicas=1 -n kmrl-production
```

**Estimated Recovery Time**: 8–15 minutes (mostly automated via Cloudflare failover)

**Data Loss**: 0 (CockroachDB active-active, no RPO gap)

---

### Scenario DR-02: Database Corruption

**Trigger**: PostgreSQL/CockroachDB data corruption detected via checksum mismatch.

**Detection**: `pg_dump` integrity check fails or CockroachDB consistency check alert.

**Recovery Steps**:

```bash
# Step 1: Identify corruption scope (< 15 minutes)
# Query CockroachDB consistency check
kubectl exec -n kmrl-production cockroach-0 -- \
  cockroach debug doctor cluster --url="postgresql://kmrl@cockroach:26257/kmrl_nexusai"

# Step 2: Freeze writes to affected tables
kubectl exec -n kmrl-production deploy/kmrl-api -- \
  python -c "
from app.main import app
import asyncio
# In production: set Redis flag 'db_freeze=true' so API returns 503
"

# Step 3: Point-in-time recovery from WAL
# Find last good checkpoint
aws s3 ls s3://kmrl-nexusai-backups/wal/ | sort | tail -20

# Restore to point in time (e.g., 2 hours before corruption detected)
kubectl run db-restore \
  --image=timescale/timescaledb:latest-pg16 \
  --restart=Never \
  -n kmrl-production \
  -- bash -c "
    aws s3 cp s3://kmrl-nexusai-backups/wal/base.tar.gz /var/lib/postgresql/ &&
    tar xf /var/lib/postgresql/base.tar.gz &&
    echo \"restore_command = 'aws s3 cp s3://kmrl-nexusai-backups/wal/%f %p'\" >> /var/lib/postgresql/data/recovery.conf &&
    echo \"recovery_target_time = '$(date -d '2 hours ago' '+%Y-%m-%d %H:%M:%S')'\" >> recovery.conf
  "

# Step 4: Validate restored data
psql $DATABASE_URL -c "
  SELECT COUNT(*) FROM trainsets;          -- expect 25
  SELECT COUNT(*) FROM fitness_certificates;
  SELECT MAX(created_at) FROM audit_logs;  -- should be recent
"

# Step 5: Resume writes
# Clear 'db_freeze' Redis flag
kubectl exec -n kmrl-production deploy/kmrl-api -- \
  redis-cli DEL db_freeze
```

**Estimated Recovery Time**: 30–60 minutes

**Data Loss**: Up to 1 hour (WAL archiving frequency)

---

### Scenario DR-03: Kafka Complete Failure

**Trigger**: All Kafka brokers down; consumer lag explodes; telemetry ingestion stops.

**Detection**: `kmrl_kafka_consumer_lag > 10000` alert; optimizer sees stale fleet data.

**Recovery Steps**:

```bash
# Step 1: Assess Kafka cluster health (< 5 minutes)
kubectl get pods -l app=kafka -n kmrl-production
kubectl logs -l app=kafka -n kmrl-production --tail=50

# Step 2: Restart Kafka brokers
kubectl rollout restart statefulset/kafka -n kmrl-production
kubectl rollout status statefulset/kafka --timeout=120s -n kmrl-production

# Step 3: Verify topic health
kubectl exec -n kmrl-production kafka-0 -- \
  kafka-topics --bootstrap-server localhost:9092 --describe

# Step 4: If topics lost — recreate them
kubectl apply -f infra/k8s/base/kafka-init.yaml

# Step 5: Restart Kafka consumers
kubectl rollout restart deployment/kmrl-worker-alerts -n kmrl-production
kubectl rollout restart deployment/kmrl-api -n kmrl-production

# Step 6: Check consumer lag is recovering
watch kubectl exec -n kmrl-production kafka-0 -- \
  kafka-consumer-groups --bootstrap-server localhost:9092 \
  --describe --group kmrl-nexusai

# Step 7: IMPORTANT — Optimizer can run without Kafka
# Optimizer uses DB data directly; Kafka loss = no real-time telemetry
# but induction planning remains functional from last-known DB state

# Notify team: "Kafka recovering. Telemetry ingestion paused ~Xmin.
#              Optimizer and fleet management fully functional."
```

**Estimated Recovery Time**: 10–20 minutes

**Impact**: Telemetry gap (no IoT sensor data during outage); optimizer unaffected

---

### Scenario DR-04: ML Model Serving Failure

**Trigger**: All ML model files missing/corrupt; predictions return errors.

**Detection**: `kmrl_ml_prediction_duration_seconds` spikes; API returns 500 on /maintenance/predictions.

**Recovery Steps**:

```bash
# Step 1: Verify model files
kubectl exec -n kmrl-production deploy/kmrl-api -- \
  ls -la /app/models/

# Step 2: Check if heuristic fallback is active
curl https://api.nexusai.kmrl.in/api/v1/maintenance/predictions \
  -H "Authorization: Bearer $TOKEN" | jq '.predictions[0].risk_profile.source'
# Should return "heuristic_fallback" — optimizer still works

# Step 3: Restore models from S3
kubectl exec -n kmrl-production deploy/kmrl-api -- bash -c "
  aws s3 sync s3://kmrl-nexusai-models/ /app/models/ --delete
  ls -la /app/models/
"

# Step 4: Reload models (hot reload — no restart needed)
curl -X POST https://api.nexusai.kmrl.in/api/v1/admin/ml/reload \
  -H "Authorization: Bearer $ADMIN_TOKEN"

# Step 5: Verify predictions working
curl https://api.nexusai.kmrl.in/api/v1/maintenance/predictions \
  -H "Authorization: Bearer $TOKEN" | jq '.predictions[0].risk_profile.source'
# Should return "predictive_maintenance_v1.3.0" (not heuristic)

# Step 6: If models not in S3, trigger emergency retrain
kubectl exec -n kmrl-production deploy/kmrl-worker-ml -- \
  celery -A app.workers.celery_app call workers.retrain_ml_models
# Note: retraining takes ~30 minutes; heuristic fallback active during this time
```

**Estimated Recovery Time**: 15–30 minutes (restore from S3) or 45 minutes (retrain)

**Impact**: ML predictions unavailable; optimizer uses rule-based risk scoring (heuristic fallback)

---

### Scenario DR-05: Vault Unavailable (Secrets inaccessible)

**Trigger**: HashiCorp Vault cluster down; dynamic DB credentials can't be renewed.

**Detection**: API returns 500 on DB queries after credential expiry; Vault health check fails.

**Recovery Steps**:

```bash
# Step 1: Check Vault cluster status
kubectl get pods -l app=vault -n vault-system
kubectl exec -n vault-system vault-0 -- vault status

# Step 2: If Vault is sealed (e.g., after restart), unseal with AWS KMS
# (AWS KMS auto-unseal should handle this automatically)
kubectl exec -n vault-system vault-0 -- \
  vault operator unseal -recover

# Step 3: If Vault completely unavailable, switch to env var fallback
# Set emergency credentials in Kubernetes secret
kubectl create secret generic kmrl-secrets-emergency \
  --namespace kmrl-production \
  --from-literal=DATABASE_URL="postgresql+asyncpg://kmrl:EMERGENCY_PASS@postgres-svc:5432/kmrl_nexusai" \
  --dry-run=client -o yaml | kubectl apply -f -

# Patch deployment to use emergency secret
kubectl patch deployment kmrl-api -n kmrl-production \
  --patch '{"spec":{"template":{"spec":{"containers":[{"name":"api","envFrom":[{"secretRef":{"name":"kmrl-secrets-emergency"}}]}]}}}}'

# Step 4: Notify security team — credential rotation paused
# All DB connections now using static emergency credentials
# ROTATE THESE CREDENTIALS as soon as Vault is restored

# Step 5: Restore Vault from backup
velero restore create vault-restore \
  --from-backup kmrl-daily-backup-$(date +%Y%m%d) \
  --include-namespaces vault-system \
  --wait

# Step 6: Re-enable Vault-based secrets
# Revert deployment to use vault-based secrets
kubectl rollout restart deployment/kmrl-api -n kmrl-production
```

**Estimated Recovery Time**: 20–45 minutes

**Impact**: Dynamic credential rotation paused; emergency static credentials in use

---

## Backup Verification Procedure (Monthly)

```bash
#!/bin/bash
# Run monthly: make backup-verify

set -e
echo "=== KMRL NexusAI Backup Verification ==="
echo "Date: $(date)"

# 1. List available backups
echo ""
echo "--- Available Velero Backups ---"
velero backup get | head -10

# 2. Verify latest backup integrity
LATEST=$(velero backup get -o json | jq -r '.items[0].metadata.name')
echo ""
echo "--- Verifying backup: $LATEST ---"
velero backup describe $LATEST --details | grep -E "Status|Items|Errors"

# 3. Test restore to isolated namespace
echo ""
echo "--- Test restore to kmrl-dr-test namespace ---"
velero restore create dr-test-$(date +%Y%m%d) \
  --from-backup $LATEST \
  --include-namespaces kmrl-production \
  --namespace-mappings kmrl-production:kmrl-dr-test \
  --wait

kubectl get pods -n kmrl-dr-test
kubectl get pvc -n kmrl-dr-test

# 4. Verify data integrity in restored namespace
kubectl run db-verify \
  --image=postgres:16 \
  --restart=Never \
  -n kmrl-dr-test \
  -- psql $TEST_DATABASE_URL -c "
    SELECT 'trainsets' as table_name, COUNT(*) FROM trainsets
    UNION ALL SELECT 'induction_plans', COUNT(*) FROM induction_plans
    UNION ALL SELECT 'fitness_certificates', COUNT(*) FROM fitness_certificates
    UNION ALL SELECT 'audit_logs', COUNT(*) FROM audit_logs;
  "

# 5. Cleanup
kubectl delete namespace kmrl-dr-test
echo ""
echo "=== Backup verification PASSED ==="
echo "RPO validated. Restore tested successfully."
```

---

## DR Drill Schedule

| Drill | Frequency | Scope | Duration | Owner |
|-------|-----------|-------|----------|-------|
| Failover to DR region | Quarterly | Full platform | 2 hours | Platform Lead |
| Database PITR restore | Monthly | DB only | 1 hour | DBA |
| Kafka recovery | Monthly | Messaging layer | 30 min | Platform Engineer |
| ML model restore | Monthly | ML service | 30 min | ML Engineer |
| Emergency stop drill | Monthly | UI + API | 15 min | Ops Manager |
| Full DR drill (all scenarios) | Bi-annual | Everything | Full day | CTO + all teams |

### Post-Drill Report Template

```markdown
## DR Drill Report — [Date]

Drill Type: [Scenario DR-0X]
Conducted By: [Names]
Duration: [Actual vs Target RTO]

### Results
- RTO Achieved: [X minutes] (Target: [Y minutes]) — PASS/FAIL
- RPO Validated: [X minutes data loss] (Target: [Y minutes]) — PASS/FAIL
- Data Integrity: PASS/FAIL
- Automation % (steps not requiring manual intervention): X%

### Issues Found
1. [Issue description] → [Corrective action]

### Runbook Updates Required
- [Specific steps that need updating]

Next Drill: [Date]
```

---

## Contact Escalation Matrix

| Scenario | First Contact | Escalate After | Second Contact | Escalate After | Final |
|----------|--------------|----------------|----------------|----------------|-------|
| P0 Safety | On-call Eng | 5 min | Platform Lead | 15 min | GM Operations |
| P1 Optimizer | On-call Eng | 15 min | Platform Lead | 30 min | Ops Manager |
| P2 Degraded | On-call Eng | 30 min | Platform Lead | 2 hours | — |
| DR Region Failover | Auto (Cloudflare) | 10 min | Platform Lead | 30 min | CTO |
| Security Breach | Security team | Immediate | CISO | Immediate | CEO |
