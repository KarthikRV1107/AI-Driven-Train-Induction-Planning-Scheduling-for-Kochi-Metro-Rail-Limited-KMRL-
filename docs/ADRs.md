# KMRL NexusAI — Architecture Decision Records (ADRs)

ADRs document the reasoning behind significant technical decisions.

---

## ADR-001: OR-Tools CP-SAT for Induction Optimization

**Status**: Accepted  
**Date**: 2025-01-15  
**Deciders**: Platform Team, Operations Team

### Context
The nightly induction planning problem involves assigning 25+ trainsets to 4 status categories
(revenue, standby, IBL, maintenance) subject to hard constraints (certificates, job cards, bay
capacity) and soft objectives (mileage balance, branding SLA, shunting minimization).

### Decision
Use **Google OR-Tools CP-SAT** (Constraint Programming - Boolean Satisfiability) solver.

### Alternatives Considered

| Option | Pros | Cons |
|--------|------|------|
| **OR-Tools CP-SAT** ✅ | Guaranteed optimal/feasible, handles 40+ fleet, <30s solve | Requires mathematical formulation |
| PuLP (LP) | Simple API | Cannot handle discrete assignment naturally |
| Greedy heuristic | Fast, simple | Sub-optimal, cannot prove feasibility |
| Genetic algorithm | Flexible | Non-deterministic, slow convergence |
| PyOMO | Rich modeling | Large dependency, slower for this problem size |

### Consequences
- Optimizer guaranteed to return feasible solution within 30-second timeout
- Scales to 40-trainset fleet without code changes (increase `FLEET_SIZE`)
- Hard constraints are provably enforced — no safety violations possible
- Requires mathematical encoding of new constraints when operational rules change

---

## ADR-002: Hybrid ML Architecture (XGBoost + PyTorch LSTM)

**Status**: Accepted  
**Date**: 2025-01-20

### Context
Two distinct prediction problems require different approaches:
1. **Failure probability** — tabular features, interpretability required → tree models
2. **Deployment readiness** — sequential daily patterns, temporal dependency → sequence models

### Decision
- **XGBoost** for predictive maintenance (brake/HVAC/door failure probability)
- **PyTorch LSTM + Attention** for 30-day readiness sequence forecasting
- **Isolation Forest** for real-time telemetry anomaly detection

### Reasoning
XGBoost chosen over neural networks for maintenance because:
- Native SHAP support for explainability (regulatory requirement)
- Works well with tabular mixed-type features
- No GPU required for inference
- Faster to retrain nightly (< 5 minutes)

PyTorch LSTM chosen for readiness because:
- Temporal patterns in 30-day health sequences not captured by tabular models
- Attention mechanism highlights which historical days most influenced prediction
- Transfer learning potential as fleet grows

### Consequences
- Two separate training pipelines to maintain
- SHAP explanations generated per recommendation
- Inference < 50ms per trainset (XGBoost) + < 100ms (LSTM)

---

## ADR-003: Apache Kafka for Event Bus

**Status**: Accepted  
**Date**: 2025-01-10

### Context
Multiple data sources (IoT sensors, IBM Maximo, UNS streams) need to be ingested
concurrently with guaranteed delivery and replay capability.

### Decision
Apache Kafka with 3 brokers, topic partitioning by trainset ID.

### Alternatives Considered

| Option | Reason Rejected |
|--------|----------------|
| RabbitMQ | No log-based replay, message loss on consumer failure |
| Redis Pub/Sub | No persistence, no consumer groups |
| AWS SQS | Vendor lock-in, no on-premise support for KMRL gov infra |
| **Kafka** ✅ | Log-based, replay, consumer groups, battle-tested |

### Consequences
- 6 topics covering telemetry, alerts, induction events, maintenance
- Kafka MirrorMaker 2 replicates to DR region
- 7-day retention for telemetry data
- Requires Zookeeper management (Kafka 3.6 uses KRaft in production config)

---

## ADR-004: PostgreSQL + TimescaleDB for Data Layer

**Status**: Accepted  
**Date**: 2025-01-08

### Context
Platform needs both relational data (trainsets, certificates, plans) and
time-series data (telemetry readings, mileage logs, KPI snapshots).

### Decision
PostgreSQL 16 with TimescaleDB extension for telemetry hypertables.

### Alternatives Considered

| Option | Reason Rejected |
|--------|----------------|
| MySQL | Weaker JSON support, no time-series extension |
| MongoDB | No ACID transactions across entities |
| InfluxDB + PostgreSQL | Two databases to manage, JOIN complexity |
| **TimescaleDB** ✅ | Single DB, automatic partitioning, SQL-native |
| CockroachDB | Added in multi-region phase (ADR-009) |

### Partitioning Strategy
- `mileage_logs` — monthly range partitions
- `alerts` — yearly range partitions
- `audit_logs` — yearly range partitions
- `ml_predictions` — yearly range partitions
- `telemetry_readings` — TimescaleDB hypertable (automatic chunking by time)

---

## ADR-005: Next.js 15 App Router for Frontend

**Status**: Accepted  
**Date**: 2025-01-12

### Context
Operational dashboard needs SSR for first-load performance, RSC for server-side
data fetching, and real-time WebSocket updates.

### Decision
Next.js 15 with App Router, TypeScript, Tailwind CSS, custom design system.

### Alternatives Considered
- **Remix** — Good DX but smaller ecosystem
- **SvelteKit** — Excellent performance but team familiarity lower
- **Vite + React SPA** — No SSR, worse initial load on large dashboards
- **Next.js 15** ✅ — RSC, streaming, App Router, strong ecosystem

### Design System Decision
Custom design system over shadcn/Radix defaults because:
- Railway operations aesthetic requires high-density information
- Dark-mode-first with custom color tokens
- Animation requirements (Framer Motion patterns)
- No generic-looking components — "funded startup" requirement

---

## ADR-006: Celery + Redis for Task Queue

**Status**: Accepted  
**Date**: 2025-01-10

### Context
Several tasks must run asynchronously and on schedule:
- Nightly optimization (21:00 IST)
- ML retraining (03:00 IST)
- Certificate expiry checks (every 6h)
- Alert dispatch (email/SMS/WhatsApp)

### Decision
Celery 5 with Redis broker, Celery Beat for scheduling.

### Reasoning
- Proven at scale with Python ecosystem
- Redis already in stack (cache) — no additional dependency
- Flower UI for worker monitoring
- Per-queue routing: optimization, ml, alerts, telemetry
- Celery Beat replaces cron — schedule changes don't require deployment

### Consequences
- Beat scheduler must run as single replica (enforced in K8s)
- Workers autoscale via KEDA based on Redis queue depth
- Flower dashboard accessible at port 5555

---

## ADR-007: JWT + Keycloak SSO + TOTP MFA

**Status**: Accepted  
**Date**: 2025-01-25

### Context
Government-grade security requires SSO federation (Azure AD for KMRL staff),
MFA for all users with access to induction planning, and JWT for stateless API auth.

### Decision
Three-layer auth:
1. **Keycloak** (SSO gateway — OIDC provider)
2. **KMRL custom JWT** (issued after Keycloak verification)
3. **TOTP MFA** (RFC 6238, enforced for Depot Controller and above)

### Alternatives Considered
- Auth0 — SaaS, data residency concern for government infra
- Okta — Cost prohibitive for KMRL scale
- Firebase Auth — No on-premise option
- **Keycloak** ✅ — Open source, self-hosted, Azure AD federation support

### Token Lifetime
- Access token: 60 minutes
- Refresh token: 7 days
- MFA challenge: 5 minutes (consumed once)

---

## ADR-008: HashiCorp Vault for Secrets Management

**Status**: Accepted  
**Date**: 2025-02-01

### Context
Static secrets in environment variables are a security liability. Database credentials
in config files have led to breaches in similar government projects.

### Decision
HashiCorp Vault with:
- Dynamic PostgreSQL credentials (auto-rotated hourly)
- KV v2 for static secrets (JWT key, SMTP password)
- Transit engine for PII field encryption at rest
- Kubernetes auth method (pod identity, no tokens in config)
- AWS KMS auto-unseal (no manual unseal needed)

### Consequences
- DB connection pool requires credential refresh logic (handled in `vault.py`)
- Vault HA (3 nodes Raft) prevents single-point-of-failure
- Fall-back to env vars when Vault unreachable (dev environments)

---

## ADR-009: CockroachDB for Multi-Region Active-Active

**Status**: Accepted (Phase 3)  
**Date**: 2025-04-01

### Context
Phase 3 multi-region deployment requires active-active database replication between
India South (primary) and India West (DR). PostgreSQL replication is read-only replica only.

### Decision
Migrate to **CockroachDB** for multi-region deployments.

### Reasoning
- Distributed SQL with automatic geo-partitioning
- Active-active writes in both regions
- PostgreSQL-compatible wire protocol (no ORM changes)
- Automatic failover < 5 seconds
- Single-region PostgreSQL remains for Phase 1/2

### Migration Path
1. Phase 1-2: Standard PostgreSQL 16 + TimescaleDB
2. Phase 3: CockroachDB cluster (6 nodes, 3 per region)
3. Migration via `IMPORT INTO` from PostgreSQL dump

---

## ADR-010: Reinforcement Learning for Weight Adaptation

**Status**: Accepted  
**Date**: 2025-03-01

### Context
The optimizer's soft-constraint weights (mileage balance, branding SLA, cleaning,
system health, IBL recency, ML risk) were initially set by domain experts.
Over time, operational patterns shift and weights should adapt.

### Decision
DQN-based weight adaptation agent that:
- Observes post-day operational outcomes (withdrawals, delays, SLA)
- Computes reward signal from outcome quality
- Updates soft-constraint weights via Q-learning
- Saves state to persist learning across retraining cycles

### Alternatives Considered
- Manual weight tuning — requires expert time, doesn't scale
- Bayesian optimization — batch update only, not online
- Full PPO/A3C — overkill for 13-action discrete space
- **DQN** ✅ — handles discrete action space, proven for operations RL

### Constraints
- RL must not violate hard constraints (it only adjusts soft weights)
- Exploration is bounded (ε-greedy with minimum ε=0.05)
- Weights normalized to sum to 100 and remain positive

---

## ADR-011: OpenTelemetry for Observability

**Status**: Accepted  
**Date**: 2025-02-15

### Context
Distributed system across 10+ services requires unified tracing to diagnose
latency and errors. Multiple monitoring vendors considered.

### Decision
OpenTelemetry SDK with OTLP export to Jaeger (traces) + Prometheus (metrics).

### Reasoning
- Vendor-neutral — no lock-in to specific APM vendor
- Auto-instrumentation for FastAPI, SQLAlchemy, HTTPX
- Trace correlation with structured logs (trace ID in every log line)
- OTLP protocol: single endpoint for both traces and metrics

### Sampling
- Development: 100% sampling
- Production: 10% trace sampling (parent-based, tail sampling for errors)

---

*ADRs are living documents. When a decision is revisited, update Status to "Superseded by ADR-XXX" rather than deleting.*
