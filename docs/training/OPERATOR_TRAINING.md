# KMRL NexusAI — Operator Training Program
## Onboarding · Role Certification · SOP Reference

**Training Owner**: Operations Manager  
**Version**: 2.4.1  
**Certification Validity**: 12 months (annual renewal)

---

## Training Tracks by Role

| Role | Track | Duration | Certification Test |
|------|-------|----------|-------------------|
| Depot Controller | Track A (Full) | 8 hours | Written + practical |
| Maintenance Supervisor | Track B (Maintenance) | 4 hours | Written |
| Operations Manager | Track C (Management) | 3 hours | Written |
| Cleaning Team Lead | Track D (Cleaning) | 2 hours | Practical only |
| Branding Manager | Track E (Branding) | 2 hours | Written |
| Admin | All tracks + Track F | 12 hours | Full certification |

---

## Track A — Depot Controller Certification

### Module A1: Platform Fundamentals (60 min)

**Learning Objectives**:
- Understand the AI induction planning process
- Navigate all platform pages confidently
- Know what the AI can and cannot do

**Content**:

#### What NexusAI Does
```
The platform automates nightly train induction planning.
Every night between 21:00 and 23:00, you will:

1. Review the AI-generated induction plan
2. Check the reasoning behind each recommendation
3. Approve, modify, or override as needed
4. Confirm the final plan for execution

The AI makes SUGGESTIONS. You make DECISIONS.
You are always in control. The AI cannot execute anything without your approval.
```

#### The Optimization Engine
```
The AI uses a mathematical solver (Google OR-Tools) to find the best
assignment of 25 trainsets to four categories:
  - Revenue Service (target: 18 trains)
  - Standby (target: 3 trains)
  - IBL Inspection (as needed)
  - Maintenance (as needed)

It considers:
  ✓ Fitness certificate validity
  ✓ Open job cards
  ✓ Brake/HVAC/door health from sensors
  ✓ Mileage balance across fleet
  ✓ Branding contract obligations
  ✓ Cleaning completion status
  ✓ Bay positions (minimize shunting)

The AI CANNOT override:
  ✗ An expired fitness certificate
  ✗ An open critical job card
  ✗ Brake health below 50%
  These are HARD constraints — the AI will never put an unsafe
  train in revenue service, no matter what.
```

**Practical Exercise A1**:
- Log in to the platform (use training environment: training.nexusai.kmrl.in)
- Navigate to all 6 main pages
- Find a trainset with a constraint violation
- Read and explain the AI reasoning on one recommendation card

---

### Module A2: Running the Nightly Optimizer (90 min)

**Learning Objectives**:
- Run the optimizer independently
- Interpret confidence scores and reasoning
- Understand when to accept vs override

**Step-by-Step Procedure**:

```
STEP 1: Pre-planning check (21:00–21:10)
  □ Log in at 21:00 IST
  □ Go to Alerts page — review any critical alerts
  □ Acknowledge alerts that don't affect tonight's plan
  □ Note any trainsets flagged for IBL or maintenance issues

STEP 2: Run optimizer (21:10–21:15)
  □ Go to Command Center
  □ Click "▶ Run Optimizer"
  □ Wait for completion (typically 10–30 seconds)
  □ Review the AI Ticker message at top of page
  □ Note: optimizer score (aim for > 85/100)

STEP 3: Review recommendations (21:15–21:40)
  □ Open AI Scheduler page
  □ For each recommended trainset, check:
      - Confidence % (accept >85%, review 65–85%, scrutinize <65%)
      - Reasons listed (do they make sense?)
      - Any constraint violations noted
  □ Expand cards with lower confidence for full SHAP analysis

STEP 4: Decision process for each recommendation
  □ ACCEPT if:
      - Confidence > 85%
      - No constraint violations
      - Reasoning aligns with your local knowledge
  □ REVIEW FURTHER if:
      - Confidence 65–85%
      - You have operational knowledge the AI might not have
      - Recent incident with this trainset not yet in the system
  □ OVERRIDE if:
      - You disagree based on local operational knowledge
      - Confidence < 65%
      - Physical inspection revealed an issue not yet recorded

STEP 5: Enter overrides (if any)
  □ Go to Fleet page
  □ Click the trainset → Override button
  □ Select the correct status
  □ Enter a reason (MANDATORY)
  □ Click "Apply Override"
  □ The override is logged with your employee ID

STEP 6: Final approval (21:45–22:00)
  □ Review the complete plan one more time
  □ Confirm revenue count ≥ 17
  □ Confirm no expired certificates in revenue service
  □ Approve the plan (button on Scheduler page)
  □ Export PDF for records (Analytics → Export → Nightly Plan)
```

**Common Override Scenarios** (with correct reasons to enter):

| Situation | Correct Action | Reason to Enter |
|-----------|---------------|-----------------|
| Trainset recently had unreported brake issue | Override to IBL | "Brake noise reported by driver at 19:45, not yet in Maximo" |
| Branding client visiting depot tomorrow | Keep in revenue | "Client visit tomorrow — ensure TS-09 visible in service" |
| Specific trainset needed for peak hour (AC issue in another) | Swap standby | "TS-14 AC failed at 20:30 per driver report" |
| AI put heavily-loaded train in revenue | Accept (AI is right) | N/A — trust the mileage balancing |

**Practical Exercise A2**:
- Run the optimizer on training environment
- Identify 2 trainsets where you would modify the AI recommendation
- Enter overrides with appropriate reasons
- Produce and save the final PDF report

---

### Module A3: Alerts and Exceptions (45 min)

**Learning Objectives**:
- Triage and respond to operational alerts
- Know when to escalate
- Handle certificate expiry situations

**Alert Severity Guide**:

```
🔴 CRITICAL — Act within 15 minutes
  Examples:
  - Fitness certificate expired on a train in revenue service
  - AI flagged brake failure risk >80% on deployed train
  - Safety constraint violated in current plan
  Actions:
  - Withdraw affected train immediately
  - Activate standby replacement
  - Call Maintenance Supervisor
  - Document in Operations Logbook

🟡 WARNING — Act within 2 hours  
  Examples:
  - Certificate expiring in 7 days
  - Brake health declining (60–70%)
  - Bay conflict detected during shunting
  Actions:
  - Review on Alerts page
  - Acknowledge and schedule appropriate response
  - Inform relevant team (maintenance, cleaning)

ℹ️ INFO — Review before next planning window
  Examples:
  - Mileage rebalancing suggestion
  - Branding SLA at risk
  - Cleaning schedule optimization
  Actions:
  - Note for tomorrow's planning
  - No immediate action required
```

**Certificate Expiry Protocol**:
```
IF certificate expires TONIGHT (days_to_expiry = 0):
  → Immediately withdraw from service
  → Assign to IBL for emergency renewal
  → Call CMRS/RDSO for expedited renewal
  → Document withdrawal reason

IF certificate expires in 1–2 days:
  → Do NOT assign to revenue service tonight
  → Schedule IBL for tomorrow morning
  → Initiate renewal process with CMRS/RDSO
  → Inform Ops Manager

IF certificate expires in 3–7 days:
  → Can continue service but monitor closely
  → Schedule renewal appointment
  → Override in platform if needed with reason:
    "Certificate renewal scheduled for [DATE], safe to operate until then"
```

**Practical Exercise A3**:
- Acknowledge and triage 5 sample alerts
- Demonstrate correct response for a critical certificate expiry
- Show how to check which trainsets are expiring soon

---

### Module A4: Depot View and Shunting (45 min)

**Learning Objectives**:
- Read the depot digital twin
- Understand the shunting simulation
- Plan efficient shunting sequences manually

**Reading the Depot Map**:
```
Color codes on depot map:
  🟢 Green   = Revenue service (assigned for tonight)
  🟡 Amber   = Standby (ready, not in service)
  🟣 Purple  = IBL (inspection bay)
  🔴 Red     = Maintenance (not available)
  🔵 Blue    = Cleaning
  ⬛ Grey    = Empty bay

Dashed lines = planned shunting path for tonight
Yellow animated path = currently executing shunt
```

**Shunting Optimization**:
```
The AI minimizes shunting by:
  1. Preferring trainsets in Row A (front-facing) for revenue
  2. Grouping same-destination trainsets
  3. Scheduling IBL movements first (before 22:00)
  4. Scheduling cleaning trainsets for least-used paths

If you see a shunting sequence that conflicts with physical reality
(e.g., blocked track, maintenance vehicle parked):
  1. Click "Simulate Shunt" to run what-if analysis
  2. Or manually re-sequence via drag on timeline
  3. Always tell Depot Foreman before any change to shunting sequence
```

**Practical Exercise A4**:
- Identify 3 shunting movements on the depot map
- Run a "What-If: Emergency Withdrawal" simulation
- Explain what the yellow animated path indicates

---

### Module A5: BCP and Manual Planning (60 min)

**Learning Objectives**:
- Produce a complete manual induction plan without the AI
- Apply all hard constraints correctly
- Activate and deactivate BCP procedures

*Complete the BCP document exercises (docs/governance/BCP.md Section 3)*

**Practical Exercise A5**:
- Platform intentionally disabled
- Produce complete manual plan for 25 trainsets in 30 minutes
- Plan must pass all hard constraint checks
- Evaluator signs off on compliance

---

### Module A6: AI Copilot (30 min)

**Learning Objectives**:
- Use the NexusAI Copilot effectively
- Know what to ask and what to verify independently

**Effective Copilot Use**:
```
Good questions:
  ✓ "Why was TS-07 assigned to IBL tonight?"
  ✓ "Which trainsets have brake health below 70%?"
  ✓ "What happens if TS-14 breaks down at 08:30?"
  ✓ "Show me all branding contracts at SLA risk"
  ✓ "Explain the mileage imbalance this week"

Questions to verify independently:
  ! "Is it safe to put TS-22 in revenue service?"
    → Always verify in platform, not just copilot response
  ! Any safety-related question → check physical records too

The copilot uses live data. But for safety decisions,
ALWAYS verify in the platform and physical records.
```

---

## Certification Assessment

### Written Test (Track A — 25 questions, pass mark 80%)

Sample questions:

**Q1**: A trainset has brake health of 58%. The AI has recommended it for revenue service with confidence 72%. What should you do?
- a) Accept the recommendation — AI knows best
- b) Override to IBL — brake health below 60% is a hard constraint
- c) Accept but flag for maintenance next week
- d) Override to standby as a compromise

**Answer**: B — Brake health < 60% is a hard constraint; cannot enter revenue service.

**Q2**: It is 21:50 IST and the optimizer shows 15 eligible trainsets for revenue service (target 18). What is the correct action?
- a) Accept 15 — better than none
- b) Contact Maintenance Supervisor to assess deferral of maintenance holds
- c) Ignore the shortfall — it will resolve itself
- d) Immediately activate full BCP

**Answer**: B — First check if any maintenance work can be safely deferred 24 hours.

**Q3**: The platform is unavailable at 21:15 IST. You have tried calling on-call engineering twice with no answer. What should you do?
- a) Wait 30 more minutes before acting
- b) Activate BCP — retrieve manual planning form and begin manual planning
- c) Skip nightly planning — morning service will be fine
- d) Call GM Operations and wait for instructions

**Answer**: B — BCP should be activated after 5 minutes of platform unavailability during planning window.

### Practical Assessment

Evaluator observes trainee:
1. Run optimizer and explain results to evaluator ✓/✗
2. Correctly identify and override one flagged trainset ✓/✗
3. Export and explain the nightly PDF report ✓/✗
4. Respond correctly to a critical alert ✓/✗
5. Complete manual plan (BCP) in <30 minutes ✓/✗

Pass requires 4/5 practical checks.

---

## Refresher Training (Annual)

All certified operators complete 2-hour annual refresher covering:
- New platform features in last 12 months
- Notable incidents and lessons learned
- Updated RDSO/CERT-In compliance requirements
- Revised override reason codes
- New ML model capabilities

---

## Training Environment

Use `training.nexusai.kmrl.in` for all training exercises.

This environment:
- Contains realistic but synthetic fleet data
- Runs real optimizer with test data
- No changes affect production
- Training logs not included in compliance audits
- Resets daily at midnight IST

**Login**: Use your KMRL email with password `Training@2025!`

---

## Support During Learning

| Resource | Location |
|----------|----------|
| This manual | docs/training/OPERATOR_TRAINING.md |
| Video walkthroughs | SharePoint: Operations/Training/Videos/ |
| Platform user guide | Help button (?) in top-right corner |
| BCP quick reference card | Depot Control Room, laminated card |
| Training environment | training.nexusai.kmrl.in |
| Questions | platform-team@kmrl.in or ext. 4201 |
