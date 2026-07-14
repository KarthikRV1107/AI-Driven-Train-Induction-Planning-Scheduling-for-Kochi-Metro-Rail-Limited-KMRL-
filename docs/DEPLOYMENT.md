# KMRL NexusAI — Production Deployment Guide

## Prerequisites

| Tool | Version | Purpose |
|------|---------|---------|
| Docker | ≥ 24.0 | Container runtime |
| Docker Compose | ≥ 2.20 | Local orchestration |
| kubectl | ≥ 1.29 | Kubernetes CLI |
| Helm | ≥ 3.14 | K8s package manager |
| Python | ≥ 3.12 | Backend runtime |
| Node.js | ≥ 20 LTS | Frontend build |
| psql | ≥ 16 | Database management |

---

## 1. Local Development (Docker Compose)

```bash
# Clone repository
git clone https://github.com/kmrl/nexusai.git
cd nexusai

# Environment setup
cp .env.example .env
# Edit .env — update secrets for local dev

# Start all services
docker-compose -f infra/docker/docker-compose.yml up -d

# Check service health
docker-compose ps
curl http://localhost:8000/health

# View logs
docker-compose logs -f api
docker-compose logs -f worker-optimization

# Run DB migrations
docker-compose exec api alembic upgrade head

# Seed demo data
docker-compose exec api python scripts/seed_demo_data.py

# Access services:
#   Platform:   http://localhost:3000
#   API docs:   http://localhost:8000/docs
#   Kafka UI:   http://localhost:8080
#   Flower:     http://localhost:5555  (admin/kmrl2025)
#   Grafana:    http://localhost:3001  (admin/kmrl_grafana)
#   Prometheus: http://localhost:9090
```

---

## 2. First-Time ML Model Training

```bash
# Enter the API container
docker-compose exec api bash

# Train predictive maintenance models
python -c "
from app.ml.pipeline import PredictiveMaintenanceModel
import pandas as pd, numpy as np

# Load real data (replace with actual DB fetch)
n = 5000
np.random.seed(42)
from app.ml.pipeline import MAINTENANCE_FEATURES
X = pd.DataFrame({f: np.random.uniform(0, 100, n) for f in MAINTENANCE_FEATURES})
model = PredictiveMaintenanceModel(horizon_days=14)
for system in ['brake', 'hvac', 'door']:
    y = pd.DataFrame({f'{system}_failure_in_14d': (np.random.random(n) < 0.08).astype(int)})
    metrics = model.train(X, y, system=system)
    print(f'{system}: {metrics}')
model.save()
print('Models saved successfully')
"

# Verify models saved
ls -la /app/models/
```

---

## 3. Kubernetes Deployment (Production)

### 3.1 Cluster Setup

```bash
# Verify cluster connection
kubectl cluster-info
kubectl get nodes

# Create namespace
kubectl create namespace kmrl-production

# Install NGINX Ingress Controller
helm repo add ingress-nginx https://kubernetes.github.io/ingress-nginx
helm install ingress-nginx ingress-nginx/ingress-nginx \
  --namespace ingress-nginx --create-namespace

# Install cert-manager (TLS)
helm repo add jetstack https://charts.jetstack.io
helm install cert-manager jetstack/cert-manager \
  --namespace cert-manager --create-namespace \
  --set installCRDs=true

# Create Let's Encrypt ClusterIssuer
kubectl apply -f infra/k8s/base/cert-issuer.yaml
```

### 3.2 Secrets Setup

```bash
# Create secrets (NEVER commit these to git)
kubectl create secret generic kmrl-secrets \
  --namespace kmrl-production \
  --from-literal=DATABASE_URL="postgresql+asyncpg://kmrl:PROD_PASSWORD@postgres-svc:5432/kmrl_nexusai" \
  --from-literal=REDIS_URL="redis://:PROD_REDIS_PASSWORD@redis-svc:6379/0" \
  --from-literal=SECRET_KEY="$(openssl rand -hex 32)" \
  --from-literal=SMTP_PASSWORD="your-smtp-password" \
  --from-literal=WHATSAPP_API_TOKEN="your-whatsapp-token"

# Image pull secret (GHCR)
kubectl create secret docker-registry ghcr-pull-secret \
  --namespace kmrl-production \
  --docker-server=ghcr.io \
  --docker-username=YOUR_GITHUB_USERNAME \
  --docker-password=YOUR_GITHUB_PAT
```

### 3.3 Deploy via Helm

```bash
# Add custom Helm repo (optional)
helm repo add kmrl https://charts.kmrl.in

# Deploy to production
helm upgrade --install kmrl-prod ./infra/helm/kmrl \
  --namespace kmrl-production \
  --values infra/helm/kmrl/values.yaml \
  --values infra/helm/kmrl/values-production.yaml \
  --set image.api.tag="2.4.1" \
  --set image.frontend.tag="2.4.1" \
  --wait --timeout=15m

# Verify rollout
kubectl rollout status deployment/kmrl-api -n kmrl-production
kubectl rollout status deployment/kmrl-frontend -n kmrl-production
kubectl get pods -n kmrl-production
```

### 3.4 Run DB Migrations (Production)

```bash
kubectl run db-migrate \
  --image=ghcr.io/kmrl/nexusai-api:2.4.1 \
  --restart=Never \
  --namespace=kmrl-production \
  --env="DATABASE_URL=$(kubectl get secret kmrl-secrets -n kmrl-production -o jsonpath='{.data.DATABASE_URL}' | base64 -d)" \
  --command -- alembic upgrade head

kubectl wait pod/db-migrate --for=condition=Completed --timeout=120s -n kmrl-production
kubectl logs pod/db-migrate -n kmrl-production
kubectl delete pod/db-migrate -n kmrl-production
```

---

## 4. Environment Variables Reference

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DATABASE_URL` | ✅ | — | PostgreSQL async connection string |
| `REDIS_URL` | ✅ | — | Redis connection URL |
| `SECRET_KEY` | ✅ | — | JWT signing secret (min 32 chars) |
| `KAFKA_BOOTSTRAP_SERVERS` | ✅ | localhost:9092 | Kafka broker list |
| `CELERY_BROKER_URL` | ✅ | — | Celery broker (Redis) |
| `ML_MODEL_PATH` | ❌ | /app/models | Path to saved ML models |
| `OPTIMIZER_TIMEOUT_SECONDS` | ❌ | 30 | OR-Tools solve timeout |
| `FLEET_SIZE` | ❌ | 25 | Current fleet count |
| `SMTP_HOST` | ❌ | smtp.gmail.com | Alert email SMTP host |
| `WHATSAPP_API_URL` | ❌ | — | WhatsApp notification gateway |
| `SENTRY_DSN` | ❌ | — | Sentry error tracking DSN |
| `ENVIRONMENT` | ❌ | development | development/staging/production |

---

## 5. Monitoring & Observability

### Grafana Dashboards

| Dashboard | URL | Purpose |
|-----------|-----|---------|
| Operations | `/d/kmrl-ops` | Fleet availability, shunting, KPIs |
| API Performance | `/d/kmrl-api` | Request rate, latency, errors |
| ML Models | `/d/kmrl-ml` | Prediction accuracy, drift |
| Infrastructure | `/d/kmrl-infra` | CPU, memory, DB connections |

### Key Prometheus Metrics

```promql
# API request rate
rate(http_requests_total{job="kmrl-api"}[5m])

# Optimization solve time p95
histogram_quantile(0.95, rate(optimization_solve_duration_seconds_bucket[10m]))

# Fleet availability
kmrl_fleet_availability_pct

# Active alerts
kmrl_active_alerts_total{severity="critical"}

# ML prediction latency
histogram_quantile(0.95, rate(ml_prediction_duration_seconds_bucket[5m]))
```

### Log Aggregation

```bash
# Stream API logs (production)
kubectl logs -f deployment/kmrl-api -n kmrl-production --all-containers

# Celery worker logs
kubectl logs -f deployment/kmrl-worker-optimization -n kmrl-production

# Query structured logs (when using Loki/Grafana)
{namespace="kmrl-production", app="kmrl-api"} |= "ERROR"
```

---

## 6. Backup & Recovery

### PostgreSQL Backup

```bash
# Manual backup
kubectl exec -n kmrl-production $(kubectl get pod -l app=postgres -n kmrl-production -o name | head -1) \
  -- pg_dump -U kmrl kmrl_nexusai | gzip > kmrl_db_$(date +%Y%m%d_%H%M%S).sql.gz

# Automated: configure Velero or pg_cron for nightly snapshots
# Recommended: AWS RDS with automated backups (7-day retention)
```

### Redis Backup

```bash
# Trigger RDB snapshot
kubectl exec -n kmrl-production $(kubectl get pod -l app=redis -n kmrl-production -o name) \
  -- redis-cli BGSAVE
```

---

## 7. Rollback Procedures

```bash
# Helm rollback (immediate)
helm rollback kmrl-prod --namespace kmrl-production

# Rollback to specific revision
helm history kmrl-prod -n kmrl-production
helm rollback kmrl-prod 3 -n kmrl-production

# Kubernetes deployment rollback
kubectl rollout undo deployment/kmrl-api -n kmrl-production
kubectl rollout status deployment/kmrl-api -n kmrl-production
```

---

## 8. Scaling

```bash
# Manual scale API
kubectl scale deployment kmrl-api --replicas=5 -n kmrl-production

# Scale optimization workers during planning window (21:00–23:00)
kubectl scale deployment kmrl-worker-optimization --replicas=4 -n kmrl-production

# Check HPA status
kubectl get hpa -n kmrl-production
```

---

## 9. Security Checklist

- [ ] SECRET_KEY generated with `openssl rand -hex 32`
- [ ] All secrets in Kubernetes Secrets (not ConfigMaps)
- [ ] TLS certificates via cert-manager
- [ ] NGINX rate limiting enabled
- [ ] Network policies enforcing pod-to-pod restrictions
- [ ] Non-root containers (`runAsUser: 1000`)
- [ ] Container image scanning (Trivy) in CI
- [ ] Regular `npm audit` and `safety check` runs
- [ ] Audit logging enabled for all user actions
- [ ] JWT tokens expire in 60 minutes
- [ ] RBAC: each role has minimum required permissions

---

## 10. Scalability Roadmap (2025–2027)

| Phase | Timeline | Scope |
|-------|----------|-------|
| **Phase 1** | Current | 25 trainsets, 1 depot (Muttom) |
| **Phase 2** | Q3 2025 | 30 trainsets, add Aluva depot |
| **Phase 3** | Q1 2026 | 40 trainsets, multi-depot federated planning |
| **Phase 4** | 2027 | Full corridor expansion, real-time digital twin |

### Multi-Depot Architecture (Phase 3)

```
                    ┌──────────────────────┐
                    │   Central Optimizer  │
                    │   (Fleet-wide view)  │
                    └──────────┬───────────┘
                               │
            ┌──────────────────┼──────────────────┐
            │                  │                  │
    ┌───────▼──────┐  ┌────────▼─────┐  ┌────────▼─────┐
    │ Muttom Depot │  │  Aluva Depot │  │  Depot 3     │
    │  15 trains   │  │  15 trains   │  │  10 trains   │
    └──────────────┘  └──────────────┘  └──────────────┘
```

Each depot runs a local optimizer, with a central coordinator
resolving cross-depot transfers and fleet-level mileage balancing.

---

## Support

- **Platform issues**: platform-team@kmrl.in
- **Operations**: ops@kmrl.in  
- **Emergency**: +91-484-KMRL-OPS
- **Documentation**: https://docs.nexusai.kmrl.in
