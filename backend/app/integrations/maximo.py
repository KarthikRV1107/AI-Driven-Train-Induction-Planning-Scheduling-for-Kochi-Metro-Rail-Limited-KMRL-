"""
KMRL NexusAI — IBM Maximo Integration Adapter
===============================================
Bi-directional sync between KMRL NexusAI and IBM Maximo EAM:

  Pull (Maximo → NexusAI):
    - Work orders (MXWO)
    - Asset health records (MXASSET)
    - Planned maintenance schedules (MXPM)
    - Job plan templates (MXJOBPLAN)

  Push (NexusAI → Maximo):
    - AI-generated work order recommendations
    - Predictive maintenance alerts
    - Induction plan confirmations
    - Asset condition updates

Protocol: Maximo REST API (OSLC) + Webhook events
Auth:     API Key via Vault secret
Sync:     Celery task every 15 minutes + event-driven webhook
"""
from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import httpx

logger = logging.getLogger(__name__)


# ── Maximo Field Mappings ─────────────────────────────────────────────────

MAXIMO_TO_NEXUSAI_STATUS = {
    "WAPPR":  "open",           # Waiting for Approval
    "APPR":   "open",           # Approved
    "INPRG":  "in_progress",    # In Progress
    "WMATL":  "in_progress",    # Waiting for Material
    "WSCH":   "open",           # Waiting to be Scheduled
    "COMP":   "completed",      # Completed
    "CLOSE":  "completed",      # Closed
    "CAN":    "deferred",       # Cancelled
}

MAXIMO_TO_NEXUSAI_PRIORITY = {
    "1": "critical",
    "2": "high",
    "3": "medium",
    "4": "low",
    "5": "low",
}

NEXUSAI_TO_MAXIMO_STATUS = {v: k for k, v in MAXIMO_TO_NEXUSAI_STATUS.items() if k != "CAN"}
NEXUSAI_TO_MAXIMO_PRIORITY = {v: k for k, v in MAXIMO_TO_NEXUSAI_PRIORITY.items()}

# Maximo asset class → NexusAI system affected mapping
MAXIMO_CLASS_TO_SYSTEM = {
    "TRAIN-BRAKE":      "brake",
    "TRAIN-HVAC":       "hvac",
    "TRAIN-DOOR":       "door",
    "TRAIN-PANTO":      "pantograph",
    "TRAIN-BOGIE":      "bogie",
    "TRAIN-SIGNAL":     "signalling",
    "TRAIN-TELECOM":    "telecom",
    "TRAIN-BODY":       "body",
}


# ── Data Classes ──────────────────────────────────────────────────────────

@dataclass
class MaximoWorkOrder:
    """Represents a Maximo Work Order (MXWO)."""
    wonum:        str
    description:  str
    assetnum:     str           # maps to trainset_code
    siteid:       str           # depot code
    status:       str           # Maximo status code
    priority:     str           # 1-5
    worktype:     str           # PM, CM, EM, INS
    reportdate:   str
    targstartdate: str | None
    targcompdate:  str | None
    classstructureid: str | None
    estdur:       float | None   # estimated hours
    actstart:     str | None
    actfinish:    str | None
    description_longdescription: str | None = None

    @property
    def nexusai_status(self) -> str:
        return MAXIMO_TO_NEXUSAI_STATUS.get(self.status, "open")

    @property
    def nexusai_priority(self) -> str:
        return MAXIMO_TO_NEXUSAI_PRIORITY.get(str(self.priority), "medium")

    @property
    def system_affected(self) -> str:
        return MAXIMO_CLASS_TO_SYSTEM.get(
            self.classstructureid or "", "general"
        )

    @property
    def is_critical(self) -> bool:
        return self.priority in ("1", "2") and self.worktype == "EM"


@dataclass
class MaximoAsset:
    """Represents a Maximo Asset record for a trainset."""
    assetnum:     str
    siteid:       str
    description:  str
    status:       str
    installation_date: str | None
    serialnum:    str | None
    manufacturer: str | None
    ytdcost:      float | None
    totalcost:    float | None
    criticality:  str | None    # 1=Critical, 2=Essential, 3=Non-Critical


# ── Maximo REST Client ────────────────────────────────────────────────────

class MaximoClient:
    """
    Async client for IBM Maximo OSLC REST API.
    Handles authentication, pagination, and error recovery.
    """

    def __init__(self, base_url: str, api_key: str, site_id: str = "MUTTOM"):
        self.base_url = base_url.rstrip("/")
        self.api_key  = api_key
        self.site_id  = site_id
        self._session_cookie: str | None = None

    @property
    def _headers(self) -> dict:
        return {
            "apikey":       self.api_key,
            "Accept":       "application/json",
            "Content-Type": "application/json",
            "x-public-uri": self.base_url,
        }

    async def _get(self, resource: str, params: dict | None = None) -> dict:
        """GET request to Maximo OSLC endpoint."""
        url = f"{self.base_url}/oslc/os/{resource}"
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(url, headers=self._headers, params=params or {})
            resp.raise_for_status()
            return resp.json()

    async def _post(self, resource: str, data: dict) -> dict:
        """POST request to create/update a Maximo record."""
        url = f"{self.base_url}/oslc/os/{resource}"
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(url, headers=self._headers, json=data)
            resp.raise_for_status()
            return resp.json() if resp.content else {}

    async def _patch(self, resource: str, wonum: str, data: dict) -> bool:
        """PATCH request to update an existing record."""
        url = f"{self.base_url}/oslc/os/{resource}/{wonum}"
        headers = {**self._headers, "x-method-override": "PATCH", "patchtype": "MERGE"}
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(url, headers=headers, json=data)
            return resp.status_code in (200, 204)

    # ── Work Orders ───────────────────────────────────────────────────────

    async def get_work_orders(
        self,
        site_id: str | None = None,
        status_filter: list[str] | None = None,
        modified_since: str | None = None,
        limit: int = 100,
    ) -> list[MaximoWorkOrder]:
        """Fetch work orders with optional filters."""
        where_clauses = [f"siteid=\"{site_id or self.site_id}\""]

        if status_filter:
            status_ors = " or ".join(f"status=\"{s}\"" for s in status_filter)
            where_clauses.append(f"({status_ors})")

        if modified_since:
            where_clauses.append(f"changedate>=\"{modified_since}\"")

        params = {
            "oslc.where":   " and ".join(where_clauses),
            "oslc.select":  "wonum,description,assetnum,siteid,status,priority,worktype,"
                            "reportdate,targstartdate,targcompdate,classstructureid,"
                            "estdur,actstart,actfinish,description.longdescription",
            "oslc.pageSize": str(limit),
            "lean":         "1",
        }

        try:
            data    = await self._get("mxwo", params)
            members = data.get("member", [])
            return [self._parse_work_order(wo) for wo in members]
        except Exception as exc:
            logger.error("Maximo work order fetch failed: %s", exc)
            return []

    async def get_work_order(self, wonum: str) -> MaximoWorkOrder | None:
        """Fetch a single work order by number."""
        params = {
            "oslc.where":  f"wonum=\"{wonum}\"",
            "oslc.select": "*",
            "lean":        "1",
        }
        try:
            data    = await self._get("mxwo", params)
            members = data.get("member", [])
            return self._parse_work_order(members[0]) if members else None
        except Exception as exc:
            logger.error("Maximo WO fetch failed for %s: %s", wonum, exc)
            return None

    async def get_open_critical_work_orders(self, trainset_code: str) -> list[MaximoWorkOrder]:
        """Get open critical/emergency work orders for a trainset."""
        return await self.get_work_orders(
            status_filter=["WAPPR", "APPR", "INPRG", "WMATL"],
        )

    # ── Assets ────────────────────────────────────────────────────────────

    async def get_asset(self, assetnum: str) -> MaximoAsset | None:
        """Fetch asset record for a trainset."""
        params = {
            "oslc.where":  f"assetnum=\"{assetnum}\"",
            "oslc.select": "assetnum,siteid,description,status,installdate,"
                           "serialnum,manufacturer,ytdcost,totalcost",
            "lean":        "1",
        }
        try:
            data    = await self._get("mxasset", params)
            members = data.get("member", [])
            if not members:
                return None
            a = members[0]
            return MaximoAsset(
                assetnum=a.get("assetnum", ""),
                siteid=a.get("siteid", ""),
                description=a.get("description", ""),
                status=a.get("status", ""),
                installation_date=a.get("installdate"),
                serialnum=a.get("serialnum"),
                manufacturer=a.get("manufacturer"),
                ytdcost=a.get("ytdcost"),
                totalcost=a.get("totalcost"),
                criticality=a.get("assetcriticality"),
            )
        except Exception as exc:
            logger.error("Maximo asset fetch failed for %s: %s", assetnum, exc)
            return None

    # ── Push AI Recommendations → Maximo ─────────────────────────────────

    async def create_predictive_work_order(
        self,
        trainset_code: str,
        system: str,
        description: str,
        risk_score: float,
        ai_reference: str,
    ) -> str | None:
        """
        Create a Maximo work order from an AI predictive maintenance alert.
        Returns the new WONUM if successful.
        """
        priority    = "1" if risk_score > 0.7 else "2" if risk_score > 0.4 else "3"
        class_id    = {v: k for k, v in MAXIMO_CLASS_TO_SYSTEM.items()}.get(system, "TRAIN-GENERAL")

        payload = {
            "siteid":       self.site_id,
            "assetnum":     trainset_code,
            "worktype":     "PM",          # Preventive Maintenance
            "status":       "WAPPR",       # Waiting for Approval
            "priority":     int(priority),
            "description":  f"AI PREDICTIVE: {description}",
            "classstructureid": class_id,
            "description_longdescription": (
                f"Auto-generated by KMRL NexusAI Predictive Maintenance Engine.\n"
                f"AI Reference: {ai_reference}\n"
                f"Risk Score: {risk_score:.1%}\n"
                f"System: {system}\n"
                f"Generated: {datetime.now(timezone.utc).isoformat()}"
            ),
            "targstartdate": datetime.now(timezone.utc).isoformat(),
        }

        try:
            result = await self._post("mxwo", payload)
            wonum  = result.get("wonum")
            logger.info("Created Maximo WO %s for %s/%s (risk=%.0f%%)", wonum, trainset_code, system, risk_score * 100)
            return wonum
        except Exception as exc:
            logger.error("Failed to create Maximo WO: %s", exc)
            return None

    async def update_work_order_status(self, wonum: str, new_status: str) -> bool:
        """Update Maximo WO status from NexusAI."""
        maximo_status = NEXUSAI_TO_MAXIMO_STATUS.get(new_status, "INPRG")
        return await self._patch("mxwo", wonum, {"status": maximo_status})

    # ── Parsers ───────────────────────────────────────────────────────────

    @staticmethod
    def _parse_work_order(data: dict) -> MaximoWorkOrder:
        return MaximoWorkOrder(
            wonum=data.get("wonum", ""),
            description=data.get("description", ""),
            assetnum=data.get("assetnum", ""),
            siteid=data.get("siteid", ""),
            status=data.get("status", "WAPPR"),
            priority=str(data.get("priority", "3")),
            worktype=data.get("worktype", "CM"),
            reportdate=data.get("reportdate", ""),
            targstartdate=data.get("targstartdate"),
            targcompdate=data.get("targcompdate"),
            classstructureid=data.get("classstructureid"),
            estdur=data.get("estdur"),
            actstart=data.get("actstart"),
            actfinish=data.get("actfinish"),
            description_longdescription=data.get("description", {}).get(
                "longdescription") if isinstance(data.get("description"), dict) else None,
        )


# ── Sync Service ──────────────────────────────────────────────────────────

class MaximoSyncService:
    """
    Orchestrates bi-directional sync between Maximo and NexusAI.
    Called by Celery task every 15 minutes.
    """

    def __init__(self, maximo_client: MaximoClient | None = None):
        self.client  = maximo_client
        self._synced = 0
        self._errors = 0

    async def sync_work_orders(
        self,
        since_minutes: int = 20,
    ) -> dict[str, Any]:
        """Pull work order updates from Maximo and update NexusAI DB."""
        if not self.client:
            return {"status": "skipped", "reason": "Maximo client not configured"}

        from datetime import timedelta
        since = (datetime.now(timezone.utc) - timedelta(minutes=since_minutes)).isoformat()

        work_orders = await self.client.get_work_orders(modified_since=since)
        results     = {"synced": 0, "errors": 0, "work_orders": []}

        for wo in work_orders:
            try:
                # In production: upsert to maintenance_jobs table
                results["work_orders"].append({
                    "wonum":      wo.wonum,
                    "trainset":   wo.assetnum,
                    "status":     wo.nexusai_status,
                    "priority":   wo.nexusai_priority,
                    "system":     wo.system_affected,
                    "is_critical": wo.is_critical,
                })
                results["synced"] += 1
                self._synced += 1
            except Exception as exc:
                logger.error("WO sync error for %s: %s", wo.wonum, exc)
                results["errors"] += 1
                self._errors += 1

        logger.info("Maximo sync: %d WOs synced, %d errors", results["synced"], results["errors"])
        return results

    async def push_ai_recommendations(
        self,
        predictions: list[dict],
        risk_threshold: float = 0.6,
    ) -> list[str]:
        """Push high-risk AI predictions to Maximo as work orders."""
        if not self.client:
            return []

        created_wonums = []
        for pred in predictions:
            risk = pred.get("composite_failure_risk", 0.0)
            if risk < risk_threshold:
                continue

            for system, system_data in pred.get("systems", {}).items():
                system_risk = system_data.get("failure_probability", 0.0)
                if system_risk < risk_threshold:
                    continue

                wonum = await self.client.create_predictive_work_order(
                    trainset_code=pred.get("trainset_code", ""),
                    system=system,
                    description=f"Predicted {system} failure — {system_risk:.0%} probability",
                    risk_score=system_risk,
                    ai_reference=f"NEXUSAI-{datetime.now().strftime('%Y%m%d-%H%M')}",
                )
                if wonum:
                    created_wonums.append(wonum)

        return created_wonums

    async def get_trainset_open_criticals(self, trainset_code: str) -> int:
        """Return count of open critical Maximo WOs for a trainset."""
        if not self.client:
            return 0
        wos = await self.client.get_open_critical_work_orders(trainset_code)
        return sum(1 for wo in wos if wo.is_critical and wo.assetnum == trainset_code)


# ── Celery Task Integration ───────────────────────────────────────────────

async def run_maximo_sync_task() -> dict[str, Any]:
    """
    Async function called by Celery task every 15 minutes.
    Pulls WO updates and pushes AI recommendations.
    """
    import os
    from app.ml.pipeline import MLService

    maximo_url    = os.getenv("MAXIMO_BASE_URL", "")
    maximo_apikey = os.getenv("MAXIMO_API_KEY", "")

    if not maximo_url or not maximo_apikey:
        logger.info("Maximo integration not configured — skipping sync")
        return {"status": "skipped", "reason": "MAXIMO_BASE_URL/API_KEY not set"}

    client  = MaximoClient(maximo_url, maximo_apikey)
    service = MaximoSyncService(client)

    # Pull WO updates
    pull_result = await service.sync_work_orders(since_minutes=20)

    # Push AI predictions above threshold
    ml_service  = MLService.get_instance()
    # In production: fetch fleet features from DB
    push_wonums = []  # await service.push_ai_recommendations(predictions)

    return {
        "pull": pull_result,
        "push": {"created_wonums": push_wonums},
        "synced_at": datetime.now(timezone.utc).isoformat(),
    }


# ── Webhook Handler ───────────────────────────────────────────────────────

class MaximoWebhookHandler:
    """
    Handles incoming Maximo webhook events (OSLC event notifications).
    Maximo sends POST to /api/v1/integrations/maximo/webhook on WO changes.
    """

    SUPPORTED_EVENTS = {"workorder.status.changed", "workorder.completed", "asset.condition.updated"}

    async def handle(self, payload: dict) -> dict[str, Any]:
        """Process incoming Maximo webhook event."""
        event_type = payload.get("eventtype", "")
        if event_type not in self.SUPPORTED_EVENTS:
            return {"status": "ignored", "event": event_type}

        logger.info("Maximo webhook: %s", event_type)

        if event_type == "workorder.completed":
            wonum    = payload.get("wonum", "")
            assetnum = payload.get("assetnum", "")
            logger.info("WO completed: %s for trainset %s", wonum, assetnum)
            # In production: update job_cards status + trigger re-evaluation

        elif event_type == "workorder.status.changed":
            wonum    = payload.get("wonum", "")
            new_stat = payload.get("status", "")
            logger.info("WO status change: %s → %s", wonum, new_stat)

        elif event_type == "asset.condition.updated":
            assetnum = payload.get("assetnum", "")
            logger.info("Asset condition updated: %s", assetnum)
            # Trigger ML risk re-evaluation

        return {"status": "processed", "event": event_type}

    def verify_signature(self, payload_bytes: bytes, signature: str, secret: str) -> bool:
        """Verify Maximo webhook HMAC-SHA256 signature."""
        import hmac
        expected = hmac.new(
            secret.encode(), payload_bytes, hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(expected, signature)
