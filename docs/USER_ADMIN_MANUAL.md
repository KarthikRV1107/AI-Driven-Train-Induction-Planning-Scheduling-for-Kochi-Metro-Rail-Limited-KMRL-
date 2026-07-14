# KMRL NexusAI — User & Admin Manual
## Version 2.4.1

---

## PART 1 — USER MANUAL

### Getting Started

**Access the platform**: https://nexusai.kmrl.in  
**Demo credentials**: depot_controller@kmrl.in / kmrl@2025

### Role Guide

| Role | What you can do |
|------|----------------|
| **Depot Controller** | Run optimizer, override trainset status, approve induction plans |
| **Maintenance Supervisor** | View/create job cards, review predictive alerts, manage work orders |
| **Operations Manager** | View all KPIs, approve plans, export reports, configure alert thresholds |
| **Cleaning Team Lead** | View/update cleaning schedules, manage bay assignments |
| **Branding Manager** | Monitor SLA compliance, view exposure hours, receive SLA alerts |
| **Admin** | Full access including user management, system config, audit logs |

---

### Nightly Induction Planning Workflow (21:00–23:00 IST)

The standard nightly workflow for the **Depot Controller**:

**Step 1 — Review pre-plan alerts** (21:00)
1. Open **Alerts** page
2. Acknowledge any critical certificate expiry or maintenance flags
3. Note trainsets flagged by AI for IBL or withdrawal

**Step 2 — Run the AI Optimizer** (21:15)
1. Click **▶ Run Optimizer** in the Command Center
2. Wait 10–30 seconds for OR-Tools to solve (~15s typical)
3. Review the **AI Recommendations** panel — top 5 trainsets ranked by confidence

**Step 3 — Review and Adjust** (21:30)
1. Expand any recommendation card to see SHAP reasoning
2. If you disagree with an assignment, go to **Fleet** page
3. Click the trainset → **Override** → select new status → **Apply**
4. Override is audit-logged with your employee ID

**Step 4 — Check Constraint Conflicts** (21:45)
1. Open **Scheduler** page
2. Review the **Constraint Conflict Detector** panel
3. AI auto-resolves most conflicts — verify the resolutions make operational sense

**Step 5 — Simulate What-If** (optional, 22:00)
1. Enable **What-If Mode** on Scheduler page
2. Select a scenario (e.g. "Maintenance Delay" for TS-03 overrun)
3. Set delay hours and click **⚡ Run What-If**
4. Review impact on fleet readiness and morning peak

**Step 6 — Export and Share** (22:30)
1. Go to **Analytics** page
2. Click **Export PDF** → "Nightly Induction Plan"
3. PDF includes full ranked list with AI reasoning for record-keeping

**Step 7 — Monitor Live** (23:00+)
1. Return to **Command Center**
2. The live WebSocket feed updates status as shunting operations execute
3. Any withdrawals during the night trigger automatic standby activation alerts

---

### Command Palette

Press `⌘K` (Mac) or `Ctrl+K` (Windows) to open the command palette:

| Shortcut | Action |
|----------|--------|
| `⌘R` | Run optimizer |
| `⌘E` | Export current view as PDF |
| `⌘D` | Jump to Depot view |
| `⌘F` | Search trainset |
| `⌘/` | Open copilot |
| `Esc` | Close overlay |

---

### AI Copilot

The NexusAI Copilot understands natural language. Ask it anything:

**Example queries:**
- *"Why was TS-07 assigned to IBL tonight?"*
- *"Which trainsets have branding SLA risk this week?"*
- *"What happens if TS-14 breaks down at 08:30 tomorrow?"*
- *"Explain the mileage imbalance across the fleet"*
- *"What are my top 3 maintenance priorities?"*
- *"Show me all trainsets with brake health below 70%"*

The copilot uses **tool calling** to retrieve live data before answering, so responses are always based on the current fleet state.

---

### Understanding AI Confidence Scores

Each recommendation card shows a **Confidence %** ring:

| Score | Meaning |
|-------|---------|
| 85–100% | High confidence — strong recommendation, accept unless local knowledge overrides |
| 65–84% | Moderate confidence — review SHAP factors before accepting |
| 40–64% | Low confidence — multiple competing factors; supervisor judgment important |
| <40% | Very low confidence — manual assignment recommended |

The confidence is derived from the **OR-Tools objective function score** normalized to 100, adjusted for SHAP feature importance.

---

### Certificate Health Indicators

| Color | Status | Action Required |
|-------|--------|-----------------|
| 🟢 Green | Valid (>7 days) | None |
| 🟡 Amber | Expiring soon (≤7 days) | Schedule renewal |
| 🔴 Red | Expired | Remove from service immediately |

The platform generates **automatic alerts** at 14 days, 7 days, 2 days, and 0 days before expiry.

---

### Interpreting SHAP Explainability

Each recommendation card (when expanded) shows **SHAP factor bars** — how much each feature contributed to the AI score:

- **Positive bar** (right) = this factor helps the trainset get assigned to revenue service
- **Negative bar** (left) = this factor works against revenue service assignment
- **Longer bar** = larger influence on the decision

Key factors:
- `mileage_balance` — distance from fleet average mileage
- `branding_sla` — urgency of branding SLA compliance
- `cleaning_ready` — whether deep cleaning was completed
- `system_health` — composite of brake/HVAC/door health
- `ml_risk_inverse` — AI failure prediction (inverted: higher = safer)

---

## PART 2 — ADMIN MANUAL

### User Management

**Create a new user** (Admin only):

```bash
# Via API
curl -X POST https://api.nexusai.kmrl.in/api/v1/admin/users \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "employee_id": "EMP-1234",
    "email": "newuser@kmrl.in",
    "full_name": "New User",
    "role": "maintenance_supervisor",
    "depot_id": "dep-001"
  }'
```

**Via Keycloak Admin Console** (recommended for production):
1. Navigate to https://sso.nexusai.kmrl.in/admin
2. Select realm: kmrl
3. Users → Add user
4. Assign role: `kmrl-maintenance-supervisor`

---

### MFA Enrollment

Users can self-enroll MFA or admins can enforce it:

1. User logs in → Profile → Security → Enable Authenticator
2. Scan the QR code with Google Authenticator / Authy
3. Enter 6-digit code to verify
4. Save backup codes in a secure location

**Admin force-enable MFA** for a role:
In Keycloak → Authentication → Required Actions → CONFIGURE_TOTP → Default Action ON

---

### Vault Secrets Rotation

Dynamic DB credentials rotate automatically every 1 hour. For manual rotation:

```bash
# Force immediate rotation
vault write -force database/rotate-root/kmrl-api-role

# View current lease info
vault list sys/leases/lookup/database/creds/kmrl-api-role/
```

Adding a new secret:
```bash
vault kv put secret/kmrl/api NEW_KEY="new_value"
```

---

### ML Model Management

**Check current model versions:**
```bash
ls -la /app/models/
# predictive_maintenance_v1.3.0/
# readiness_lstm_v1.1.0/
# rl_agent_v1.0.0/
```

**Trigger manual retraining:**
```bash
make ml-train
# OR via API:
curl -X POST https://api.nexusai.kmrl.in/api/v1/admin/ml/retrain \
  -H "Authorization: Bearer $ADMIN_TOKEN"
```

**Model drift dashboard:**  
Open Grafana → Dashboard: `kmrl-ops` → Panel: **Model Drift PSI**  
PSI > 0.2 triggers automatic retraining. PSI > 0.25 triggers an alert.

---

### Audit Logs

All user actions are logged to the `audit_logs` table:

```sql
-- Recent admin actions
SELECT u.email, a.action, a.resource_type, a.created_at
FROM audit_logs a
JOIN users u ON a.user_id = u.id
WHERE a.created_at > NOW() - INTERVAL '24h'
ORDER BY a.created_at DESC
LIMIT 50;

-- Status overrides in last 7 days
SELECT u.email, a.old_value->>'status' as old_status,
       a.new_value->>'status' as new_status,
       a.created_at
FROM audit_logs a
JOIN users u ON a.user_id = u.id
WHERE a.action = 'trainset_status_override'
  AND a.created_at > NOW() - INTERVAL '7d';
```

---

### Alert Configuration

**Add a new alert rule** (Admin → Configure Alerts):

```bash
# Via Prometheus rules
cat >> infra/docker/alerting-rules.yml << 'EOF'
  - alert: MyCustomAlert
    expr: kmrl_fleet_availability_pct < 80
    for: 3m
    labels:
      severity: critical
    annotations:
      summary: "Fleet below 80%"
EOF

make prometheus-reload
```

**Alert channels per severity:**

| Severity | Dashboard | Email | SMS | WhatsApp |
|----------|-----------|-------|-----|----------|
| Critical | ✅ | ✅ | ✅ | ✅ |
| Warning | ✅ | ✅ | ❌ | ❌ |
| Info | ✅ | ❌ | ❌ | ❌ |

---

### Backup and Restore

**Automated daily backup** (runs at 02:00 IST via Velero):
```bash
# Check latest backups
velero backup get

# Restore from backup
make restore-k8s
# Enter backup name when prompted
```

**Manual DB backup:**
```bash
make backup
# Creates: backups/kmrl_db_YYYYMMDD_HHMMSS.sql.gz
```

---

### Scaling for Peak Load (Planning Window)

The KEDA autoscaler handles optimizer worker scaling automatically.  
For manual pre-scaling before the 21:00 planning window:

```bash
# Pre-scale optimizer workers
kubectl scale deployment kmrl-optimizer-worker --replicas=4 -n kmrl-production

# Scale API for dashboard surge
kubectl scale deployment kmrl-api --replicas=5 -n kmrl-production

# Scale back at 23:00
kubectl scale deployment kmrl-optimizer-worker --replicas=2 -n kmrl-production
kubectl scale deployment kmrl-api --replicas=3 -n kmrl-production
```

---

### Support Contacts

| Team | Contact | Hours |
|------|---------|-------|
| Platform (P1) | platform-team@kmrl.in | 24×7 |
| Operations | ops@kmrl.in | 06:00–23:00 IST |
| AI/ML Team | ai-team@kmrl.in | 09:00–18:00 IST |
| Security | security@kmrl.in | 09:00–18:00 IST |
| Emergency Hotline | +91-484-KMRL-OPS | 24×7 |

**Runbooks**: https://docs.nexusai.kmrl.in/runbooks  
**Status page**: https://status.nexusai.kmrl.in
