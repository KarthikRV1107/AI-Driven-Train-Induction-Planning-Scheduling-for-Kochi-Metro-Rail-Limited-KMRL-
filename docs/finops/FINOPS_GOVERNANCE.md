# KMRL NexusAI — FinOps Governance Framework
## Cloud Cost Management · Budget Controls · Optimization Policy

---

## Cost Allocation Structure

```
kmrl-nexusai (root)
├── compute/
│   ├── api-servers          EKS worker nodes running API pods
│   ├── optimizer-workers    Compute-intensive nodes for OR-Tools
│   ├── ml-workers           High-memory nodes for PyTorch/XGBoost
│   └── beat-scheduler       Single tiny pod (minimal cost)
├── data/
│   ├── primary-database     RDS PostgreSQL / CockroachDB
│   ├── cache                ElastiCache Redis
│   ├── kafka                MSK (Managed Kafka)
│   └── object-storage       S3 (models, reports, backups)
├── networking/
│   ├── load-balancer        ALB for API + Frontend
│   ├── waf                  AWS WAF v2 (per request)
│   ├── data-transfer        Cross-AZ + cross-region
│   └── cloudfront           CDN for frontend assets
├── security/
│   ├── vault                HashiCorp Vault nodes
│   ├── keycloak             Keycloak pods
│   └── kms                  AWS KMS (Vault auto-unseal)
├── observability/
│   ├── prometheus           Storage for metrics
│   ├── grafana              Dashboard hosting
│   ├── jaeger               Trace storage
│   └── cloudwatch           AWS managed logging
└── dr/
    ├── dr-region-compute    India West replica
    └── velero-backup        S3 backup storage
```

---

## Monthly Budget Targets (Production)

| Category | Monthly Budget (₹) | Alert at | Hard Stop at |
|----------|-------------------|----------|--------------|
| Compute (API + workers) | ₹45,000 | ₹40,000 | ₹55,000 |
| Database (CockroachDB/RDS) | ₹35,000 | ₹32,000 | ₹42,000 |
| Cache (Redis) | ₹18,000 | ₹16,000 | ₹22,000 |
| Messaging (Kafka/MSK) | ₹28,000 | ₹25,000 | ₹35,000 |
| Networking (ALB+WAF+CDN) | ₹12,000 | ₹10,000 | ₹15,000 |
| Security (Vault+KMS) | ₹8,000 | ₹7,000 | ₹10,000 |
| Observability | ₹6,000 | ₹5,500 | ₹8,000 |
| DR Region | ₹22,000 | ₹20,000 | ₹28,000 |
| Object Storage (S3/MinIO) | ₹5,000 | ₹4,500 | ₹7,000 |
| **Total** | **₹1,79,000** | **₹1,60,000** | **₹2,22,000** |

---

## Cost Optimization Strategies

### Implemented

```yaml
spot_instances:
  enabled: true
  applies_to: [ml-workers, optimizer-workers]
  savings: "60–80% vs on-demand"
  fallback: on-demand if spot unavailable
  config:
    interruption_handler: enabled     # graceful Celery task migration
    max_spot_price: 0.7x on-demand

reserved_instances:
  enabled: true
  applies_to: [api-servers, primary-database, redis]
  term: 1-year
  savings: "~40% vs on-demand"
  payment: all-upfront

keda_autoscaling:
  optimizer_workers:
    min_replicas: 0          # scale to zero 23:00–20:30
    max_replicas: 6          # peak during 21:00–23:00
    queue_threshold: 3       # scale up when 3+ tasks waiting
    daily_savings_estimate: "~21 hours idle = 65% compute savings"

s3_intelligent_tiering:
  ml_models: enabled        # models older than 30 days → Glacier
  reports: enabled          # PDFs older than 90 days → Glacier
  monthly_savings: ~₹1,500
```

### Scheduled Optimizations

```bash
# Scale optimizer workers to 0 at 23:30 IST (planning window ends)
# Cron: 18:00 UTC daily
kubectl scale deployment kmrl-worker-optimization --replicas=0 -n kmrl-production

# Scale back up at 20:30 IST (30 min before planning window)
# Cron: 15:00 UTC daily
kubectl scale deployment kmrl-worker-optimization --replicas=2 -n kmrl-production

# Scale ML worker to 0 after nightly retrain completes (typically 04:30 IST)
# Handled by KEDA based on Redis queue depth
```

### Right-Sizing Recommendations (Review Quarterly)

```
Component              Current        Recommended    Saving
──────────────────────────────────────────────────────────
API pods (×3)          n2-std-8       n2-std-4       ₹12,000/mo (if CPU < 40%)
ML worker              n2-highmem-16  n2-highmem-8   ₹8,000/mo (if training < 4h)
Redis                  r7g.large      r7g.medium     ₹5,000/mo (if memory < 500MB)
CockroachDB nodes      n2-std-8 ×6    n2-std-4 ×6   ₹15,000/mo (Phase 1-2 only)
```

---

## Cost Dashboard (Grafana)

```json
{
  "title": "KMRL NexusAI FinOps",
  "panels": [
    {
      "title": "Monthly Spend vs Budget",
      "type": "gauge",
      "datasource": "AWS Cost Explorer",
      "fieldConfig": {
        "defaults": {
          "thresholds": {
            "steps": [
              {"value": 0,      "color": "green"},
              {"value": 160000, "color": "yellow"},
              {"value": 179000, "color": "orange"},
              {"value": 222000, "color": "red"}
            ]
          },
          "max": 250000,
          "unit": "currencyINR"
        }
      }
    },
    {
      "title": "Cost by Service (30 days)",
      "type": "piechart",
      "targets": [{
        "query": "SELECT service, sum(cost) FROM aws_cost_usage WHERE period='30d' GROUP BY service"
      }]
    },
    {
      "title": "Optimizer Worker Cost vs Usage",
      "type": "timeseries",
      "description": "Cost spikes should align with 21:00–23:00 planning window only"
    },
    {
      "title": "Spot Instance Savings",
      "type": "stat",
      "description": "Monthly savings from spot instances vs on-demand"
    },
    {
      "title": "Reserved Instance Utilization",
      "type": "bargauge",
      "description": "RI utilization must stay > 80% to justify commitment"
    },
    {
      "title": "Cost per Induction Plan",
      "type": "stat",
      "description": "Total compute cost / number of plans generated = unit economics"
    }
  ]
}
```

---

## Resource Quota (Kubernetes)

```yaml
# Enforces hard limits on namespace resource consumption
apiVersion: v1
kind: ResourceQuota
metadata:
  name: kmrl-production-quota
  namespace: kmrl-production
spec:
  hard:
    # Compute
    requests.cpu:    "20"
    limits.cpu:      "50"
    requests.memory: "30Gi"
    limits.memory:   "80Gi"
    # Pods
    pods:            "60"
    # Storage
    requests.storage: "500Gi"
    persistentvolumeclaims: "20"
    # Services
    services:         "20"
    services.nodeports: "0"       # no NodePort services allowed
    services.loadbalancers: "2"  # max 2 load balancers
---
apiVersion: v1
kind: LimitRange
metadata:
  name: kmrl-container-limits
  namespace: kmrl-production
spec:
  limits:
    - type: Container
      default:
        cpu:    "500m"
        memory: "512Mi"
      defaultRequest:
        cpu:    "100m"
        memory: "128Mi"
      max:
        cpu:    "8"
        memory: "12Gi"
      min:
        cpu:    "50m"
        memory: "64Mi"
```

---

## Cost Governance Policy

### Approval Required For

| Change | Approval | Threshold |
|--------|----------|-----------|
| New cloud service | Platform Lead | Any |
| Reserved instance purchase | CTO | > ₹50,000/year |
| Instance type upgrade | Platform Lead | > ₹5,000/month impact |
| Multi-region expansion | CTO + Finance | > ₹30,000/month impact |
| External SaaS tool | Platform Lead | > ₹2,000/month |

### Monthly FinOps Review

**Attendees**: Platform Lead, DevOps Engineer, Finance Controller

**Agenda**:
1. Actual vs budget (10 min)
2. Top 3 cost drivers (10 min)
3. Spot/RI utilization (5 min)
4. Optimization opportunities (10 min)
5. Next month forecast (5 min)

**Output**: FinOps report emailed to management by 5th of each month.

---

## Cost Anomaly Detection

```yaml
# AWS Cost Anomaly Detection alerts
anomaly_monitors:
  - name: kmrl-compute-anomaly
    type: DIMENSIONAL
    dimension: SERVICE
    threshold_expression:
      impact:
        type: PERCENTAGE
        threshold: 20    # alert if any service spikes > 20% vs 7-day average
    notification:
      emails: [platform-lead@kmrl.in, finance@kmrl.in]
      slack: "#kmrl-finops"

  - name: kmrl-daily-budget-alert
    type: COST_BUDGET
    budget_limit: 6000   # ₹6,000/day = ₹1,80,000/month
    notification_threshold: 80  # alert at 80% of daily budget
```

---

## Unit Economics Tracking

Track the cost efficiency of AI operations:

```sql
-- Cost per induction plan (run monthly)
SELECT
  DATE_TRUNC('month', ip.created_at) AS month,
  COUNT(*)                            AS plans_generated,
  -- Cloud cost comes from AWS Cost Explorer API
  -- For now: estimate based on optimizer worker runtime
  COUNT(*) * 0.50                     AS estimated_compute_cost_inr,
  ROUND(AVG(ip.score), 2)            AS avg_optimizer_score,
  ROUND(COUNT(*) * 0.50 / COUNT(*), 2) AS cost_per_plan_inr
FROM induction_plans ip
WHERE ip.optimization_status = 'completed'
GROUP BY DATE_TRUNC('month', ip.created_at)
ORDER BY month DESC;

-- ML model cost efficiency
SELECT
  model_name,
  COUNT(*)                         AS predictions_made,
  COUNT(*) FILTER (WHERE is_actioned) AS predictions_acted_on,
  ROUND(COUNT(*) FILTER (WHERE is_actioned)::numeric / COUNT(*) * 100, 1) AS action_rate_pct
FROM ml_predictions
WHERE prediction_at > NOW() - INTERVAL '30 days'
GROUP BY model_name;
```
