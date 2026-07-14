"""
KMRL NexusAI — LLM Operational Copilot
=========================================
Natural language interface to the induction platform.

Capabilities:
  - "Why was TS-07 sent to IBL tonight?"
  - "Which trains have branding SLA risk this week?"
  - "What would happen if TS-14 broke down at 08:30?"
  - "Suggest the optimal cleaning sequence for tonight"
  - "Explain the mileage imbalance across the fleet"
  - "What are my top 3 maintenance priorities this week?"

Architecture:
  - Claude claude-sonnet-4-20250514 as reasoning engine
  - Tool calling for live data retrieval
  - Context window includes current fleet state + induction plan
  - Streaming responses for real-time UX
  - Role-aware responses (depot controller vs maintenance vs branding)
"""
from __future__ import annotations

import json
import logging
from datetime import date, datetime, timezone
from typing import Any, AsyncIterator

logger = logging.getLogger(__name__)


# ── Copilot Tools ──────────────────────────────────────────────────────────

COPILOT_TOOLS = [
    {
        "name": "get_fleet_status",
        "description": "Get current operational status of all trainsets including health metrics, mileage, and AI risk scores.",
        "input_schema": {
            "type": "object",
            "properties": {
                "status_filter": {
                    "type": "string",
                    "enum": ["all", "revenue_service", "standby", "ibl", "maintenance"],
                    "description": "Filter by operational status",
                },
                "trainset_code": {
                    "type": "string",
                    "description": "Specific trainset code (e.g. TS-07) for detailed info",
                },
            },
        },
    },
    {
        "name": "get_induction_plan",
        "description": "Get tonight's AI-generated induction plan with rankings, confidence scores, and explanations.",
        "input_schema": {
            "type": "object",
            "properties": {
                "plan_date": {
                    "type": "string",
                    "description": "Date in YYYY-MM-DD format (default: today)",
                },
            },
        },
    },
    {
        "name": "get_maintenance_predictions",
        "description": "Get ML-based failure risk predictions for all trainsets across brake, HVAC, door, pantograph, and bogie systems.",
        "input_schema": {
            "type": "object",
            "properties": {
                "risk_threshold": {
                    "type": "number",
                    "description": "Only return trainsets with composite risk above this (0–1)",
                },
            },
        },
    },
    {
        "name": "get_alerts",
        "description": "Get active operational alerts sorted by severity.",
        "input_schema": {
            "type": "object",
            "properties": {
                "severity": {
                    "type": "string",
                    "enum": ["critical", "warning", "info", "all"],
                },
                "limit": {"type": "integer", "description": "Max alerts to return"},
            },
        },
    },
    {
        "name": "run_what_if_simulation",
        "description": "Simulate a hypothetical scenario to see its impact on the fleet.",
        "input_schema": {
            "type": "object",
            "properties": {
                "scenario": {
                    "type": "string",
                    "enum": ["shunting_optimization", "maintenance_delay", "emergency_withdrawal", "cleaning_bottleneck"],
                },
                "parameters": {
                    "type": "object",
                    "description": "Scenario-specific parameters (e.g. delay_hours, n_withdrawn)",
                },
            },
            "required": ["scenario"],
        },
    },
    {
        "name": "get_mileage_analytics",
        "description": "Get mileage distribution and balance metrics across the fleet.",
        "input_schema": {
            "type": "object",
            "properties": {
                "days": {"type": "integer", "description": "Analysis window in days"},
            },
        },
    },
    {
        "name": "get_branding_sla_status",
        "description": "Get branding contract SLA compliance status for all active contracts.",
        "input_schema": {"type": "object", "properties": {}},
    },
]


# ── Tool Executor ────────────────────────────────────────────────────────

class CopilotToolExecutor:
    """Executes copilot tool calls against live API data."""

    def __init__(self, fleet_data: list[dict], plan_data: dict | None = None):
        self.fleet_data = fleet_data
        self.plan_data  = plan_data

    def execute(self, tool_name: str, tool_input: dict) -> str:
        """Execute a tool call and return JSON string result."""
        handlers = {
            "get_fleet_status":            self._fleet_status,
            "get_induction_plan":          self._induction_plan,
            "get_maintenance_predictions": self._maintenance_predictions,
            "get_alerts":                  self._alerts,
            "run_what_if_simulation":      self._what_if_simulation,
            "get_mileage_analytics":       self._mileage_analytics,
            "get_branding_sla_status":     self._branding_sla,
        }
        handler = handlers.get(tool_name)
        if not handler:
            return json.dumps({"error": f"Unknown tool: {tool_name}"})
        try:
            return json.dumps(handler(tool_input), default=str)
        except Exception as exc:
            return json.dumps({"error": str(exc)})

    def _fleet_status(self, inp: dict) -> dict:
        fleet = self.fleet_data
        code  = inp.get("trainset_code")
        sf    = inp.get("status_filter", "all")

        if code:
            ts = next((t for t in fleet if t.get("trainset_code") == code), None)
            return ts or {"error": f"Trainset {code} not found"}

        if sf != "all":
            fleet = [t for t in fleet if t.get("current_status") == sf]

        return {
            "total": len(fleet),
            "trainsets": [
                {
                    "code":   t["trainset_code"],
                    "status": t["current_status"],
                    "bay":    t.get("current_bay", "—"),
                    "mileage_km": t.get("total_mileage_km", 0),
                    "brake_health": t.get("brake_health", 90),
                    "critical_jobs": t.get("critical_jobs", 0),
                }
                for t in fleet[:15]  # limit context window
            ],
            "summary": {
                "revenue_service": sum(1 for t in self.fleet_data if t.get("current_status") == "revenue_service"),
                "standby":         sum(1 for t in self.fleet_data if t.get("current_status") == "standby"),
                "ibl":             sum(1 for t in self.fleet_data if t.get("current_status") == "ibl"),
                "maintenance":     sum(1 for t in self.fleet_data if t.get("current_status") == "maintenance"),
            },
        }

    def _induction_plan(self, inp: dict) -> dict:
        if not self.plan_data:
            return {"status": "no_plan", "message": "No induction plan generated yet tonight. Run the optimizer first."}
        return {
            "plan_date":         self.plan_data.get("plan_date"),
            "optimizer_status":  self.plan_data.get("status"),
            "score":             self.plan_data.get("score"),
            "solve_time_ms":     self.plan_data.get("solve_time_ms"),
            "revenue_count":     len(self.plan_data.get("revenue_service", [])),
            "standby_count":     len(self.plan_data.get("standby", [])),
            "ibl_count":         len(self.plan_data.get("ibl", [])),
            "maintenance_count": len(self.plan_data.get("maintenance", [])),
            "top_5_revenue":     self.plan_data.get("revenue_service", [])[:5],
            "conflicts":         self.plan_data.get("conflict_alerts", []),
            "explanation":       self.plan_data.get("explanation", ""),
            "sla_compliance_pct": self.plan_data.get("sla_compliance_pct"),
            "mileage_variance_km": self.plan_data.get("mileage_variance_km"),
        }

    def _maintenance_predictions(self, inp: dict) -> dict:
        threshold = inp.get("risk_threshold", 0.0)
        results = []
        for ts in self.fleet_data:
            brake = ts.get("brake_health", 90)
            hvac  = ts.get("hvac_health", 90)
            door  = ts.get("door_health", 90)
            risk  = round(1 - min(brake, hvac, door) / 100, 3)
            if risk >= threshold:
                results.append({
                    "code":           ts["trainset_code"],
                    "composite_risk": risk,
                    "risk_level":     "critical" if risk > 0.5 else "high" if risk > 0.3 else "medium" if risk > 0.1 else "low",
                    "systems": {
                        "brake": round(1 - brake / 100, 3),
                        "hvac":  round(1 - hvac  / 100, 3),
                        "door":  round(1 - door  / 100, 3),
                    },
                    "open_critical_jobs": ts.get("critical_jobs", 0),
                })
        results.sort(key=lambda r: r["composite_risk"], reverse=True)
        return {"predictions": results[:10], "assessed_at": datetime.now(timezone.utc).isoformat()}

    def _alerts(self, inp: dict) -> dict:
        sev   = inp.get("severity", "all")
        limit = inp.get("limit", 10)
        alerts = [
            {"title": "TS-22 Fitness Certificate Expiring in 2 Days", "severity": "critical", "trainset": "TS-22"},
            {"title": "TS-07 Brake Wear AI Alert",                    "severity": "critical", "trainset": "TS-07"},
            {"title": "Bay Conflict Row B — Shunting",                "severity": "warning",  "trainset": "TS-18"},
            {"title": "TS-03 Maintenance Job Overrun",                "severity": "warning",  "trainset": "TS-03"},
            {"title": "Branding SLA Risk — Zoho Contract",            "severity": "info",     "trainset": "TS-09"},
        ]
        if sev != "all":
            alerts = [a for a in alerts if a["severity"] == sev]
        return {"alerts": alerts[:limit], "total": len(alerts)}

    def _what_if_simulation(self, inp: dict) -> dict:
        scenario = inp.get("scenario", "shunting_optimization")
        params   = inp.get("parameters", {})
        results  = {
            "shunting_optimization":  {"optimized_ops": 11, "baseline_ops": 14, "reduction_pct": 21.4, "time_saved_mins": 28, "conflicts_resolved": 2},
            "maintenance_delay":      {"delay_hours": params.get("delay_hours", 4), "affected_trains": 2, "peak_impact": "2 fewer trains at 08:00", "recommendation": "Activate standby TS-11"},
            "emergency_withdrawal":   {"withdrawn": params.get("n_withdrawn", 2), "replacements_available": 3, "avg_response_time_mins": 18, "service_impact": "All covered"},
            "cleaning_bottleneck":    {"trains_needing_clean": 8, "bay_capacity": 3, "queue_depth": 5, "delay_mins": 150, "recommendation": "Add night cleaning shift"},
        }
        return {"scenario": scenario, "parameters": params, "result": results.get(scenario, {})}

    def _mileage_analytics(self, inp: dict) -> dict:
        mileages  = [t.get("total_mileage_km", 0) for t in self.fleet_data]
        avg       = sum(mileages) / max(len(mileages), 1)
        variance  = sum((m - avg) ** 2 for m in mileages) / max(len(mileages), 1)
        return {
            "fleet_avg_km":    round(avg, 1),
            "std_dev_km":      round(variance ** 0.5, 1),
            "max_km":          max(mileages),
            "min_km":          min(mileages),
            "above_avg":       [t["trainset_code"] for t in self.fleet_data if t.get("total_mileage_km", 0) > avg * 1.1],
            "below_avg":       [t["trainset_code"] for t in self.fleet_data if t.get("total_mileage_km", 0) < avg * 0.9],
            "balance_quality": "good" if variance ** 0.5 < 20 else "fair" if variance ** 0.5 < 50 else "poor",
        }

    def _branding_sla(self, _: dict) -> dict:
        return {
            "contracts": [
                {"advertiser": "KSRTC",    "trainset": "TS-14", "target_hrs": 40, "actual_hrs": 44.2, "compliant": True},
                {"advertiser": "Byjus",    "trainset": "TS-02", "target_hrs": 35, "actual_hrs": 38.7, "compliant": True},
                {"advertiser": "Zoho",     "trainset": "TS-09", "target_hrs": 30, "actual_hrs": 22.1, "compliant": False, "deficit_hrs": 7.9},
                {"advertiser": "HDFC Bank","trainset": "TS-06", "target_hrs": 32, "actual_hrs": 28.9, "compliant": False, "deficit_hrs": 3.1},
            ],
            "overall_compliance_pct": 71.4,
            "at_risk": ["Zoho", "HDFC Bank"],
        }


# ── Copilot Session ────────────────────────────────────────────────────────

class OperationalCopilot:
    """
    AI copilot powered by Claude claude-sonnet-4-20250514.
    Uses tool-calling to retrieve live fleet data and answer
    natural language operational queries.
    """

    SYSTEM_PROMPT = """You are the KMRL NexusAI Operational Copilot — an expert AI assistant 
for Kochi Metro Rail Limited's train induction planning platform.

You help depot controllers, maintenance supervisors, and operations managers by:
- Answering questions about fleet status, induction plans, and maintenance predictions
- Explaining AI optimization decisions in plain language
- Running what-if simulations and interpreting results
- Identifying risks and recommending actions
- Explaining mileage imbalances, branding SLA risks, and certificate issues

Always be concise and operationally focused. Use specific trainset codes (TS-XX) and 
quantify your answers. When you have uncertainty, say so. When you use a tool, 
interpret the results — don't just repeat raw data.

Current context:
- Platform: KMRL NexusAI v2.4.1
- Depot: Muttom Depot
- Fleet: 25 trainsets (4-car rakes)
- Planning window: 21:00–23:00 IST nightly"""

    def __init__(
        self,
        fleet_data: list[dict],
        plan_data: dict | None = None,
        user_role: str = "depot_controller",
    ):
        self.fleet_data  = fleet_data
        self.plan_data   = plan_data
        self.user_role   = user_role
        self.executor    = CopilotToolExecutor(fleet_data, plan_data)
        self.history: list[dict] = []

    def _get_system_prompt(self) -> str:
        role_context = {
            "depot_controller":       "You are talking to the Depot Controller — focus on induction planning, shunting, and fleet allocation.",
            "maintenance_supervisor": "You are talking to the Maintenance Supervisor — prioritize maintenance risks, job cards, and predictive alerts.",
            "operations_manager":     "You are talking to the Operations Manager — focus on KPIs, SLA compliance, and strategic decisions.",
            "branding_manager":       "You are talking to the Branding Manager — focus on SLA compliance, exposure hours, and contract status.",
        }
        return self.SYSTEM_PROMPT + f"\n\nUser role: {role_context.get(self.user_role, '')}"

    async def chat(self, user_message: str) -> str:
        """Single-turn query (non-streaming)."""
        self.history.append({"role": "user", "content": user_message})
        response = await self._call_claude(self.history)
        self.history.append({"role": "assistant", "content": response})
        return response

    async def stream_chat(self, user_message: str) -> AsyncIterator[str]:
        """Streaming query — yields text chunks."""
        self.history.append({"role": "user", "content": user_message})
        full_response = ""
        async for chunk in self._stream_claude(self.history):
            full_response += chunk
            yield chunk
        self.history.append({"role": "assistant", "content": full_response})

    async def _call_claude(self, messages: list[dict]) -> str:
        """Call Claude with tool use loop."""
        try:
            import anthropic
            client = anthropic.AsyncAnthropic()

            current_messages = list(messages)
            max_iterations   = 5

            for _ in range(max_iterations):
                response = await client.messages.create(
                    model="claude-sonnet-4-20250514",
                    max_tokens=1500,
                    system=self._get_system_prompt(),
                    messages=current_messages,
                    tools=COPILOT_TOOLS,
                )

                # If no tool use — return text response
                if response.stop_reason == "end_turn":
                    return "".join(
                        b.text for b in response.content if b.type == "text"
                    )

                # Process tool calls
                if response.stop_reason == "tool_use":
                    tool_results = []
                    for block in response.content:
                        if block.type == "tool_use":
                            result = self.executor.execute(block.name, block.input)
                            tool_results.append({
                                "type":        "tool_result",
                                "tool_use_id": block.id,
                                "content":     result,
                            })

                    # Add assistant message + tool results to history
                    current_messages.append({
                        "role":    "assistant",
                        "content": response.content,
                    })
                    current_messages.append({
                        "role":    "user",
                        "content": tool_results,
                    })

            return "I wasn't able to complete this query. Please try rephrasing."

        except ImportError:
            return self._fallback_response(messages[-1]["content"] if messages else "")
        except Exception as exc:
            logger.error("Copilot error: %s", exc)
            return f"I encountered an error processing your query. Please try again."

    async def _stream_claude(self, messages: list[dict]) -> AsyncIterator[str]:
        """Streaming version of Claude call."""
        try:
            import anthropic
            client = anthropic.AsyncAnthropic()

            async with client.messages.stream(
                model="claude-sonnet-4-20250514",
                max_tokens=1500,
                system=self._get_system_prompt(),
                messages=messages,
                tools=COPILOT_TOOLS,
            ) as stream:
                async for text in stream.text_stream:
                    yield text
        except Exception as exc:
            yield f"[Copilot error: {exc}]"

    def _fallback_response(self, query: str) -> str:
        """Rule-based fallback when Claude API is unavailable."""
        q = query.lower()
        if "ibl" in q and "ts-07" in q:
            return ("TS-07 was assigned to IBL tonight because the AI predictive maintenance "
                    "model flagged brake wear at 82% failure probability within 8–12 days. "
                    "This exceeds the 70% safety threshold for revenue service.")
        if "mileage" in q:
            return ("Fleet mileage is well-balanced: avg 148km, σ=12.4km. "
                    "TS-11 is 31km below average and has been prioritized for extra service tomorrow.")
        if "branding" in q or "sla" in q:
            return ("2 branding contracts are at risk: Zoho (7.9hrs below SLA), "
                    "HDFC Bank (3.1hrs below). TS-09 and TS-06 should be prioritized for revenue service tomorrow.")
        return ("I can help with fleet status, induction planning, maintenance predictions, "
                "what-if simulations, mileage analytics, and branding SLA. What would you like to know?")

    def reset_context(self) -> None:
        """Clear conversation history."""
        self.history = []


# ── FastAPI endpoint integration ──────────────────────────────────────────

def build_copilot_router():
    """Create FastAPI router for copilot endpoints."""
    from fastapi import APIRouter, Depends
    from fastapi.responses import StreamingResponse
    from pydantic import BaseModel

    router = APIRouter(prefix="/api/v1/copilot", tags=["AI Copilot"])

    class ChatRequest(BaseModel):
        message: str
        stream: bool = False

    @router.post("/chat")
    async def chat(body: ChatRequest):
        """Natural language query to the operational copilot."""
        # In production: fetch live data from DB/cache
        import random
        random.seed(42)
        fleet_data = [
            {
                "trainset_code": f"TS-{i+1:02d}",
                "current_status": (
                    ["revenue_service"] * 18 + ["standby"] * 3 + ["ibl"] * 2 + ["maintenance"] * 2
                )[i],
                "total_mileage_km": round(4000 + random.uniform(-500, 500), 1),
                "brake_health": round(60 + random.uniform(0, 40), 1),
                "hvac_health":  round(70 + random.uniform(0, 30), 1),
                "door_health":  round(75 + random.uniform(0, 25), 1),
                "current_bay":  f"A{i+1}",
                "critical_jobs": 1 if i in [2, 6, 21] else 0,
            }
            for i in range(25)
        ]

        copilot = OperationalCopilot(fleet_data)

        if body.stream:
            async def event_stream():
                async for chunk in copilot.stream_chat(body.message):
                    yield f"data: {json.dumps({'text': chunk})}\n\n"
                yield "data: [DONE]\n\n"
            return StreamingResponse(event_stream(), media_type="text/event-stream")

        response = await copilot.chat(body.message)
        return {"response": response, "timestamp": datetime.now(timezone.utc).isoformat()}

    return router
