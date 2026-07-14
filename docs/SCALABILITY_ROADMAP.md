# KMRL NexusAI — Scalability Roadmap
## 2025–2027 Technical Evolution Plan

---

## Current State (Phase 1 — v2.4.1)

```
Fleet:   25 trainsets · 4-car rakes
Depots:  1 (Muttom, Aluva)
Regions: India South (single-region)
Users:   ~20 concurrent operators
Uptime:  99.5% target
```

---

## Phase 2 — Fleet Expansion (Q3 2025)

**Scope**: Fleet grows from 25 → 30 trainsets. Aluva depot gains IBL expansion.

### Changes Required

**Configuration only** (no code changes):
```bash
# Update environment variables
FLEET_SIZE=30
FLEET_SIZE_TARGET=40
```

**Database**: Add 5 new trainset records + bay configurations

**Optimizer**: OR-Tools CP-SAT scales linearly — no changes needed for +5 trainsets.
Tested with 40-trainset fleet in `TestOptimizerPerformance.test_40_trainset_optimization_feasible`.

**ML Models**: Retrain with expanded dataset. Feature engineering unchanged.

**Infrastructure**:
```yaml
# Update Helm values
replicaCount:
  api: 3        # unchanged
  workerOptimization: 2   # unchanged — KEDA handles peak
```

**Estimated migration time**: 2 hours (DB seed + config + retrain)

---

## Phase 3 — Multi-Depot Architecture (Q1 2026)

**Scope**: 40 trainsets across 2 depots (Muttom + new Kalamassery depot).

### Architecture Changes

```
Before (Phase 1-2):              After (Phase 3):
┌─────────────────┐              ┌──────────────────────────┐
│  Single Depot   │              │   Federated Multi-Depot  │
│  OR-Tools opt.  │     ──→      │ ┌──────────┬──────────┐  │
│  Single plan    │              │ │  Muttom  │Kalamassery│ │
└─────────────────┘              │ │  20 sets │  20 sets │  │
                                 │ └────┬─────┴─────┬────┘  │
                                 │      └─────┬──────┘       │
                                 │    Central Coordinator    │
                                 └──────────────────────────┘
```

### Optimizer Changes

New `MultiDepotOptimizer` class wrapping two `InductionOptimizer` instances:

```python
class MultiDepotOptimizer:
    def __init__(self, depots: list[DepotConfig]):
        self.optimizers = {d.code: InductionOptimizer(d) for d in depots}
    
    def optimize_federation(
        self, 
        trainsets_by_depot: dict[str, list[TrainsetState]]
    ) -> dict[str, OptimizationResult]:
        # Phase 1: local optimization per depot
        local_results = {
            code: self.optimizers[code].optimize(ts)
            for code, ts in trainsets_by_depot.items()
        }
        
        # Phase 2: cross-depot transfer suggestions
        # (trainsets with very low mileage could transfer to higher-demand depot)
        transfers = self._suggest_transfers(local_results)
        
        return {"local": local_results, "transfers": transfers}
```

### Database Changes

New tables:
- `depot_transfers` — inter-depot trainset movements
- `cross_depot_plans` — federated optimization results

New indexes on `trainsets.depot_id` (already exists).

### Kafka Topics

Add per-depot topics:
- `kmrl.muttom.telemetry`
- `kmrl.kalamassery.telemetry`
- `kmrl.fleet.coordination` (cross-depot messages)

### UI Changes

- Depot selector in sidebar
- "Fleet Transfer" action on Depot view
- Cross-depot mileage balance heatmap
- Federation score on optimizer output

---

## Phase 4 — Full Corridor Expansion (2027)

**Scope**: 40+ trainsets, 3+ depots, real-time digital twin, LLM copilot at production scale.

### Advanced AI Capabilities

#### 1. Autonomous Anomaly Investigation
```
Current:  Alert raised → human investigates
Phase 4:  Alert raised → Copilot auto-investigates using tools →
          Suggests action → Human approves/overrides
```

Implementation:
```python
class AutonomousInvestigator:
    async def investigate(self, alert: Alert) -> Investigation:
        # Use Claude with full tool access to:
        # 1. Pull relevant telemetry (get_telemetry_window)
        # 2. Check maintenance history (get_maintenance_jobs)
        # 3. Run simulation (run_what_if_simulation)
        # 4. Cross-reference similar past incidents (search_history)
        # 5. Generate ranked recommendations with confidence
        pass
```

#### 2. Natural Language Schedule Modification
```
User: "Move the 09:30 CUSAT service to TS-11 — TS-14 needs an early clean"
System: Validates feasibility → Shows impact → Applies with confirmation
```

#### 3. Predictive Service Planning (7-day horizon)
```
Current:  Nightly optimization (24h horizon)
Phase 4:  Weekly optimization (168h horizon) using:
          - Passenger demand forecasting (from AFC data)
          - Weather impact model
          - Event-based demand spikes (festivals, matches)
          - Maintenance schedule integration
```

### Distributed Optimization Cluster

For 40+ trainsets and weekly horizons, single-node OR-Tools may require:

```
Option A: Increase timeout to 120s
  - Simple, no code change
  - Risk: 2x longer planning window

Option B: Partition by route (2 sub-problems solved in parallel)
  - SMA Line optimizer + SLV/CUSAT optimizer
  - Final coordinator merges solutions
  - Estimated: 15-20s for 40 trains

Option C: Genetic Algorithm hybrid
  - OR-Tools for feasibility seeding
  - GA for multi-day horizon optimization
  - Estimated: 45-60s for weekly plan
```

**Recommendation**: Option B for Phase 4 (proven in practice, bounded complexity).

### Performance Targets by Phase

| Metric | Phase 1 (Now) | Phase 2 | Phase 3 | Phase 4 |
|--------|---------------|---------|---------|---------|
| Fleet size | 25 | 30 | 40 | 50+ |
| Optimizer solve time | <30s | <30s | <35s | <45s |
| API p95 latency | <500ms | <500ms | <600ms | <750ms |
| Concurrent users | 20 | 30 | 50 | 100 |
| Data retention | 1 year | 2 years | 5 years | 10 years |
| ML retrain frequency | Daily | Daily | 12-hourly | 6-hourly |
| Uptime SLA | 99.5% | 99.5% | 99.9% | 99.95% |

---

## Infrastructure Scaling Path

### Kubernetes Node Pools

```yaml
# Phase 1-2: Single node pool
node-pools:
  - name: general
    machine-type: n2-standard-8
    min: 3, max: 8

# Phase 3: Specialized pools
node-pools:
  - name: api
    machine-type: n2-standard-4
    min: 3, max: 12
  - name: compute-intensive   # optimizer + ML
    machine-type: n2-highcpu-16
    min: 1, max: 6
  - name: ml-gpu              # Phase 4 LSTM training
    machine-type: n1-standard-8 + nvidia-tesla-t4
    min: 0, max: 2    # scale to zero when idle

# Phase 4: Multi-region
regions:
  india-south:
    node-pools: [api, compute-intensive, ml-gpu]
  india-west:
    node-pools: [api, compute-intensive]  # DR: no GPU needed
```

### Database Growth Projections

| Year | Telemetry rows/day | Total DB size | Strategy |
|------|-------------------|---------------|----------|
| 2025 | ~1M | ~50 GB | PostgreSQL + TimescaleDB |
| 2026 | ~2M | ~200 GB | Add compression, extend partitions |
| 2027 | ~4M | ~500 GB | CockroachDB multi-region |

```sql
-- Phase 2: Enable TimescaleDB compression
SELECT add_compression_policy('telemetry_readings', INTERVAL '7 days');
SELECT add_retention_policy('telemetry_readings', INTERVAL '1 year');

-- Phase 4: Continuous aggregates for faster dashboard queries
CREATE MATERIALIZED VIEW telemetry_hourly
WITH (timescaledb.continuous) AS
SELECT time_bucket('1 hour', time) AS bucket,
       trainset_id, sensor_type,
       avg(value) as avg_val, max(value) as max_val
FROM telemetry_readings
GROUP BY bucket, trainset_id, sensor_type;
```

---

## Cost Optimization

### Phase 1-2 Monthly Estimate (AWS ap-south-1)

| Service | Config | Est. Monthly Cost |
|---------|--------|-------------------|
| EKS cluster | 3× n2-standard-8 | ~₹45,000 |
| RDS PostgreSQL | db.r6g.xlarge, Multi-AZ | ~₹35,000 |
| ElastiCache Redis | cache.r7g.large, 2 nodes | ~₹18,000 |
| MSK Kafka | kafka.m5.large × 3 | ~₹28,000 |
| ALB + WAF | per request | ~₹8,000 |
| S3 + CloudWatch | storage + logs | ~₹5,000 |
| **Total** | | **~₹1,39,000/month** |

### Cost Reduction Strategies

```
1. Spot instances for ML workers (60-80% savings)
   → Celery workers on spot, regular for API/Beat

2. Reserved instances for stable workloads (40% savings)
   → API nodes, Redis on 1-year RI

3. KEDA scale-to-zero for optimizer workers off-peak
   → Workers at 0 replicas 23:00-20:30 (21h/day idle avoided)

4. S3 Intelligent-Tiering for ML model artifacts
   → Models >30 days → Glacier

Estimated optimized monthly cost: ~₹85,000–95,000
```
