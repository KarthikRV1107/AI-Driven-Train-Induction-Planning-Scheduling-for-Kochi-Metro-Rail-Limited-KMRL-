"""
KMRL NexusAI — FastAPI Application
====================================
REST + WebSocket API  |  v1
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta, timezone
from typing import Annotated, Any
from uuid import UUID

import redis.asyncio as aioredis
from fastapi import (
    Depends, FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect,
    status,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from passlib.context import CryptContext
from prometheus_fastapi_instrumentator import Instrumentator
from pydantic import BaseModel, Field

from app.core.config import settings
from app.llm.copilot import build_copilot_router

logger = logging.getLogger(__name__)

# ── Startup / Shutdown ────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting KMRL NexusAI API v%s", settings.APP_VERSION)
    app.state.redis = await aioredis.from_url(settings.REDIS_URL, decode_responses=True)
    app.state.ws_manager = WebSocketManager()
    yield
    await app.state.redis.aclose()
    logger.info("KMRL NexusAI API shutdown complete")


# ── App ───────────────────────────────────────────────────────────────────

app = FastAPI(
    title="KMRL NexusAI API",
    description="AI-Driven Train Induction Planning & Scheduling Platform",
    version=settings.APP_VERSION,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)
app.include_router(build_copilot_router())

# ── Middleware ────────────────────────────────────────────────────────────

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_HOSTS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(GZipMiddleware, minimum_size=1000)

# ── Prometheus ────────────────────────────────────────────────────────────
if settings.PROMETHEUS_ENABLED:
    Instrumentator().instrument(app).expose(app)

# ── Auth ──────────────────────────────────────────────────────────────────

pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/token")


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_ctx.verify(plain, hashed)

def hash_password(password: str) -> str:
    return pwd_ctx.hash(password)

def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode["exp"] = expire
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)

async def get_current_user(token: Annotated[str, Depends(oauth2_scheme)]) -> dict:
    credentials_exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid authentication credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exc
        return {"user_id": user_id, "role": payload.get("role"), "depot_id": payload.get("depot_id")}
    except JWTError:
        raise credentials_exc


# ── Schemas ───────────────────────────────────────────────────────────────

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user_id: str
    role: str

class TrainsetResponse(BaseModel):
    id: str
    trainset_code: str
    rake_number: str
    current_status: str
    current_bay: str | None
    total_mileage_km: float
    is_active: bool
    depot_code: str | None
    fitness_summary: dict
    ai_risk_score: float | None
    last_updated: str

class InductionPlanRequest(BaseModel):
    plan_date: date = Field(default_factory=date.today)
    depot_id: str
    override_revenue_target: int | None = None
    force_trainset_ids: list[str] = Field(default_factory=list)

class InductionPlanResponse(BaseModel):
    plan_id: str
    plan_date: str
    status: str
    score: float
    solve_time_ms: float
    revenue_service: list[dict]
    standby: list[dict]
    ibl: list[dict]
    maintenance: list[dict]
    total_shunting_ops: int
    mileage_variance: float
    sla_compliance_pct: float
    conflict_alerts: list[dict]
    explanation: str
    created_at: str

class AlertResponse(BaseModel):
    id: str
    alert_code: str
    severity: str
    trainset_code: str | None
    title: str
    description: str | None
    is_acknowledged: bool
    created_at: str

class KPIResponse(BaseModel):
    fleet_availability_pct: float
    revenue_service_count: int
    standby_count: int
    ibl_count: int
    maintenance_count: int
    total_shunting_ops_today: int
    avg_mileage_km: float
    mileage_std_km: float
    active_alerts_critical: int
    active_alerts_warning: int
    sla_compliance_pct: float
    mtbf_days: float
    mttr_hours: float
    ai_confidence_avg: float

class MaintenancePredictionResponse(BaseModel):
    trainset_id: str
    trainset_code: str
    composite_failure_risk: float
    risk_level: str
    recommendation: str
    systems: dict
    assessed_at: str

class DepotLayoutResponse(BaseModel):
    depot_code: str
    depot_name: str
    total_bays: int
    occupied_bays: int
    bays: list[dict]

class SimulationRequest(BaseModel):
    depot_id: str
    scenario: str = "shunting_optimization"
    parameters: dict = Field(default_factory=dict)


# ── WebSocket Manager ─────────────────────────────────────────────────────

class WebSocketManager:
    """Manages live WebSocket connections for real-time dashboard updates."""

    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.active_connections.append(ws)
        logger.info("WS client connected. Total: %d", len(self.active_connections))

    def disconnect(self, ws: WebSocket):
        self.active_connections.remove(ws)

    async def broadcast(self, message: dict):
        disconnected = []
        for ws in self.active_connections:
            try:
                await ws.send_json(message)
            except Exception:
                disconnected.append(ws)
        for ws in disconnected:
            self.active_connections.remove(ws)

    async def send_to(self, ws: WebSocket, message: dict):
        try:
            await ws.send_json(message)
        except Exception:
            self.disconnect(ws)


# ── Exception Handlers ────────────────────────────────────────────────────

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.detail, "status_code": exc.status_code, "path": str(request.url)},
    )

@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    logger.error("Unhandled exception: %s", exc, exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error", "status_code": 500},
    )


# ── Health ────────────────────────────────────────────────────────────────

@app.get("/health", tags=["System"])
async def health_check(request: Request):
    try:
        await request.app.state.redis.ping()
        redis_ok = True
    except Exception:
        redis_ok = False
    return {
        "status": "healthy" if redis_ok else "degraded",
        "version": settings.APP_VERSION,
        "environment": settings.ENVIRONMENT,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "services": {"redis": "ok" if redis_ok else "error"},
    }

@app.get("/", tags=["System"])
async def root():
    return {"service": "KMRL NexusAI API", "version": settings.APP_VERSION, "docs": "/docs"}


# ── Auth Routes ───────────────────────────────────────────────────────────

@app.post("/api/v1/auth/token", response_model=TokenResponse, tags=["Auth"])
async def login(form_data: Annotated[OAuth2PasswordRequestForm, Depends()]):
    """Authenticate and receive JWT access token."""
    # TODO: replace with real DB lookup
    DEMO_USERS = {
        "depot_controller@kmrl.in": {
            "password": "kmrl@2025",
            "role": "depot_controller",
            "user_id": "usr-001",
            "depot_id": "dep-001",
        }
    }
    user = DEMO_USERS.get(form_data.username)
    if not user or form_data.password != user["password"]:
        raise HTTPException(status_code=401, detail="Incorrect username or password")

    token = create_access_token({
        "sub": user["user_id"],
        "role": user["role"],
        "depot_id": user["depot_id"],
    })
    return TokenResponse(
        access_token=token,
        expires_in=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user_id=user["user_id"],
        role=user["role"],
    )

@app.post("/api/v1/auth/refresh", tags=["Auth"])
async def refresh_token(current_user: Annotated[dict, Depends(get_current_user)]):
    token = create_access_token({"sub": current_user["user_id"], "role": current_user["role"]})
    return {"access_token": token, "token_type": "bearer"}


# ── Fleet Routes ──────────────────────────────────────────────────────────

@app.get("/api/v1/fleet", tags=["Fleet"])
async def list_fleet(
    current_user: Annotated[dict, Depends(get_current_user)],
    depot_id: str | None = None,
    status_filter: str | None = None,
):
    """List all trainsets with current operational status."""
    # Returns mock data — replace with DB query
    trainsets = _get_mock_fleet_data()
    if status_filter:
        trainsets = [t for t in trainsets if t["current_status"] == status_filter]
    return {"trainsets": trainsets, "total": len(trainsets), "timestamp": datetime.now(timezone.utc).isoformat()}

@app.get("/api/v1/fleet/{trainset_code}", tags=["Fleet"])
async def get_trainset(
    trainset_code: str,
    current_user: Annotated[dict, Depends(get_current_user)],
):
    """Get full detail for a single trainset including certificates, jobs, mileage."""
    fleet = _get_mock_fleet_data()
    ts = next((t for t in fleet if t["trainset_code"] == trainset_code), None)
    if not ts:
        raise HTTPException(status_code=404, detail=f"Trainset {trainset_code} not found")
    return ts

@app.patch("/api/v1/fleet/{trainset_code}/status", tags=["Fleet"])
async def update_trainset_status(
    trainset_code: str,
    body: dict,
    current_user: Annotated[dict, Depends(get_current_user)],
    request: Request,
):
    """Override trainset status (depot controller / ops manager only)."""
    allowed_roles = {"depot_controller", "operations_manager", "admin"}
    if current_user["role"] not in allowed_roles:
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    new_status = body.get("status")
    valid_statuses = {"revenue_service", "standby", "ibl", "maintenance", "cleaning", "stabling"}
    if new_status not in valid_statuses:
        raise HTTPException(status_code=400, detail=f"Invalid status: {new_status}")

    # Broadcast to WebSocket clients
    await request.app.state.ws_manager.broadcast({
        "event": "trainset_status_update",
        "trainset_code": trainset_code,
        "new_status": new_status,
        "updated_by": current_user["user_id"],
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })

    return {"trainset_code": trainset_code, "status": new_status, "updated": True}


# ── Induction Plan Routes ─────────────────────────────────────────────────

@app.post("/api/v1/induction/optimize", tags=["Induction"])
async def run_optimization(
    body: InductionPlanRequest,
    current_user: Annotated[dict, Depends(get_current_user)],
    request: Request,
):
    """
    Run the AI optimization engine and return a ranked induction plan.
    This is the core endpoint — triggers OR-Tools + ML inference.
    """
    allowed_roles = {"depot_controller", "operations_manager", "admin"}
    if current_user["role"] not in allowed_roles:
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    from app.optimization.engine import (
        DepotConfig, InductionOptimizer, TrainsetState, ExplainableAI
    )

    # Build trainset states from mock/DB data
    trainset_states = _build_trainset_states()

    depot_config = DepotConfig(
        revenue_target=body.override_revenue_target or 18,
    )

    optimizer = InductionOptimizer(depot=depot_config, timeout_seconds=settings.OPTIMIZER_TIMEOUT_SECONDS)
    result = optimizer.optimize(trainset_states, plan_date=body.plan_date)

    # Generate XAI reasons for top recommendations
    fleet_avg = sum(ts.mileage_km for ts in trainset_states) / len(trainset_states)
    for item in result.revenue_service[:5]:
        ts = next((t for t in trainset_states if t.code == item.trainset_code), None)
        if ts:
            _, factors = InductionOptimizer(depot=depot_config).\
                checker.compute_soft_score(ts, fleet_avg, depot_config)
            item.ai_reasoning["human_reasons"] = ExplainableAI.generate_reasons(
                ts, fleet_avg, factors, item.assigned_status
            )

    # Cache plan
    cache_key = f"induction_plan:{body.plan_date}:{body.depot_id}"
    import json
    await request.app.state.redis.setex(
        cache_key, 3600,
        json.dumps({
            "score": result.score,
            "revenue_count": len(result.revenue_service),
            "status": result.status,
        })
    )

    # Broadcast to WebSocket
    await request.app.state.ws_manager.broadcast({
        "event": "induction_plan_ready",
        "plan_date": str(result.plan_date),
        "score": result.score,
        "revenue_count": len(result.revenue_service),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })

    return {
        "plan_id": f"PLN-{date.today().strftime('%Y%m%d')}-001",
        "plan_date": str(result.plan_date),
        "status": result.status,
        "score": result.score,
        "solve_time_ms": result.solve_time_ms,
        "optimizer_version": result.optimizer_version,
        "revenue_service": [
            {
                "rank": item.priority_rank,
                "trainset_code": item.trainset_code,
                "confidence_pct": item.confidence_pct,
                "reasoning": item.ai_reasoning,
                "constraint_violations": item.constraint_violations,
            }
            for item in result.revenue_service
        ],
        "standby": [{"trainset_code": i.trainset_code, "confidence_pct": i.confidence_pct} for i in result.standby],
        "ibl": [{"trainset_code": i.trainset_code, "constraint_violations": i.constraint_violations} for i in result.ibl],
        "maintenance": [{"trainset_code": i.trainset_code, "constraint_violations": i.constraint_violations} for i in result.maintenance],
        "total_shunting_ops": result.total_shunting_ops,
        "mileage_variance_km": result.mileage_variance,
        "sla_compliance_pct": result.sla_compliance_pct,
        "conflict_alerts": result.conflict_alerts,
        "explanation": result.explanation,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

@app.get("/api/v1/induction/plans", tags=["Induction"])
async def list_plans(
    current_user: Annotated[dict, Depends(get_current_user)],
    from_date: date | None = None,
    to_date: date | None = None,
):
    """List historical induction plans."""
    return {"plans": [], "total": 0}

@app.get("/api/v1/induction/plans/{plan_date}", tags=["Induction"])
async def get_plan(
    plan_date: date,
    current_user: Annotated[dict, Depends(get_current_user)],
    request: Request,
):
    """Get cached plan for a specific date."""
    cache_key = f"induction_plan:{plan_date}:dep-001"
    cached = await request.app.state.redis.get(cache_key)
    if cached:
        import json
        return {"plan_date": str(plan_date), "cached": True, "data": json.loads(cached)}
    raise HTTPException(status_code=404, detail=f"No plan found for {plan_date}")


# ── Maintenance Routes ────────────────────────────────────────────────────

@app.get("/api/v1/maintenance/predictions", tags=["Maintenance"])
async def get_maintenance_predictions(
    current_user: Annotated[dict, Depends(get_current_user)],
):
    """Get AI failure predictions for all trainsets."""
    from app.ml.pipeline import MLService
    service = MLService.get_instance()

    predictions = []
    fleet = _get_mock_fleet_data()
    for ts in fleet[:10]:  # limit for demo
        features = {
            "brake_health_pct": ts.get("brake_health", 90),
            "hvac_health_pct": ts.get("hvac_health", 90),
            "door_health_pct": ts.get("door_health", 90),
            "total_mileage_km": ts.get("total_mileage_km", 5000),
            "days_since_last_service": ts.get("days_since_service", 30),
            "days_since_ibl": ts.get("days_since_ibl", 45),
            "open_job_cards_count": ts.get("open_jobs", 0),
            "critical_jobs_count": ts.get("critical_jobs", 0),
            "age_years": 5,
        }
        profile = service.get_trainset_risk_profile(features, ts["id"])
        predictions.append({
            "trainset_code": ts["trainset_code"],
            **profile,
        })

    return {"predictions": predictions, "assessed_at": datetime.now(timezone.utc).isoformat()}

@app.get("/api/v1/maintenance/jobs", tags=["Maintenance"])
async def list_maintenance_jobs(
    current_user: Annotated[dict, Depends(get_current_user)],
    status: str | None = None,
    priority: str | None = None,
):
    """List open maintenance jobs and job cards."""
    return {"jobs": _get_mock_jobs(), "total": 11}

@app.post("/api/v1/maintenance/jobs", tags=["Maintenance"])
async def create_maintenance_job(
    body: dict,
    current_user: Annotated[dict, Depends(get_current_user)],
):
    """Create a new maintenance job."""
    return {"job_id": "JOB-2847", "status": "created", **body}


# ── Alerts Routes ─────────────────────────────────────────────────────────

@app.get("/api/v1/alerts", tags=["Alerts"])
async def list_alerts(
    current_user: Annotated[dict, Depends(get_current_user)],
    severity: str | None = None,
    acknowledged: bool | None = None,
    limit: int = 50,
):
    """List active alerts."""
    alerts = _get_mock_alerts()
    if severity:
        alerts = [a for a in alerts if a["severity"] == severity]
    if acknowledged is not None:
        alerts = [a for a in alerts if a["is_acknowledged"] == acknowledged]
    return {"alerts": alerts[:limit], "total": len(alerts)}

@app.patch("/api/v1/alerts/{alert_id}/acknowledge", tags=["Alerts"])
async def acknowledge_alert(
    alert_id: str,
    current_user: Annotated[dict, Depends(get_current_user)],
):
    return {"alert_id": alert_id, "acknowledged": True, "by": current_user["user_id"]}


# ── KPI Routes ────────────────────────────────────────────────────────────

@app.get("/api/v1/kpis", response_model=KPIResponse, tags=["Analytics"])
async def get_kpis(current_user: Annotated[dict, Depends(get_current_user)]):
    """Real-time operational KPIs."""
    return KPIResponse(
        fleet_availability_pct=92.0,
        revenue_service_count=18,
        standby_count=3,
        ibl_count=2,
        maintenance_count=2,
        total_shunting_ops_today=14,
        avg_mileage_km=148.3,
        mileage_std_km=12.4,
        active_alerts_critical=2,
        active_alerts_warning=5,
        sla_compliance_pct=97.0,
        mtbf_days=42.0,
        mttr_hours=3.2,
        ai_confidence_avg=93.7,
    )

@app.get("/api/v1/analytics/mileage", tags=["Analytics"])
async def get_mileage_analytics(
    current_user: Annotated[dict, Depends(get_current_user)],
    days: int = 30,
):
    """Mileage distribution and balancing analytics."""
    fleet = _get_mock_fleet_data()
    mileages = [ts["total_mileage_km"] for ts in fleet]
    avg = sum(mileages) / len(mileages)
    return {
        "fleet_avg_km": round(avg, 1),
        "std_dev_km": round((sum((m - avg) ** 2 for m in mileages) / len(mileages)) ** 0.5, 1),
        "max_km": max(mileages),
        "min_km": min(mileages),
        "per_trainset": [
            {"code": ts["trainset_code"], "mileage_km": ts["total_mileage_km"]}
            for ts in fleet
        ],
    }

@app.get("/api/v1/analytics/availability-trend", tags=["Analytics"])
async def get_availability_trend(
    current_user: Annotated[dict, Depends(get_current_user)],
    days: int = 30,
):
    """Fleet availability trend over time."""
    import random
    today = date.today()
    trend = [
        {
            "date": str(today - timedelta(days=days - i)),
            "availability_pct": round(88 + random.uniform(-2, 4), 1),
            "revenue_count": random.randint(17, 20),
        }
        for i in range(days)
    ]
    return {"trend": trend, "period_days": days}


# ── Depot Routes ──────────────────────────────────────────────────────────

@app.get("/api/v1/depot/{depot_code}/layout", tags=["Depot"])
async def get_depot_layout(
    depot_code: str,
    current_user: Annotated[dict, Depends(get_current_user)],
):
    """Get current depot bay occupancy."""
    return _get_mock_depot_layout(depot_code)

@app.post("/api/v1/depot/simulate", tags=["Depot"])
async def simulate_shunting(
    body: SimulationRequest,
    current_user: Annotated[dict, Depends(get_current_user)],
):
    """Run a depot simulation (what-if shunting analysis)."""
    return {
        "scenario": body.scenario,
        "simulated_shunting_ops": 11,
        "reduction_vs_current": 3,
        "estimated_time_mins": 47,
        "conflicts": [],
        "recommendation": "Reorder Row B movements to reduce TS-18 conflicts",
    }


# ── Certificates Routes ────────────────────────────────────────────────────

@app.get("/api/v1/certificates", tags=["Certificates"])
async def list_certificates(
    current_user: Annotated[dict, Depends(get_current_user)],
    expiring_within_days: int | None = None,
    status: str | None = None,
):
    """List fitness certificates with expiry tracking."""
    certs = _get_mock_certificates()
    if expiring_within_days:
        threshold = date.today() + timedelta(days=expiring_within_days)
        certs = [c for c in certs if date.fromisoformat(c["expiry_date"]) <= threshold]
    return {"certificates": certs, "total": len(certs)}


# ── WebSocket ─────────────────────────────────────────────────────────────

@app.websocket("/ws/live")
async def websocket_live(ws: WebSocket, token: str = ""):
    """
    WebSocket endpoint for real-time dashboard updates.
    Streams: telemetry, alerts, induction events, status changes.
    """
    manager: WebSocketManager = ws.app.state.ws_manager
    await manager.connect(ws)
    try:
        await manager.send_to(ws, {
            "event": "connected",
            "message": "KMRL NexusAI live feed connected",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        while True:
            data = await ws.receive_json()
            # Handle client events (subscribe, ping, override)
            if data.get("type") == "ping":
                await manager.send_to(ws, {"type": "pong", "timestamp": datetime.now(timezone.utc).isoformat()})
            elif data.get("type") == "subscribe":
                topics = data.get("topics", [])
                await manager.send_to(ws, {"type": "subscribed", "topics": topics})
    except WebSocketDisconnect:
        manager.disconnect(ws)
        logger.info("WS client disconnected. Total: %d", len(manager.active_connections))


# ── Mock Data Helpers ─────────────────────────────────────────────────────
# In production these are replaced by async DB queries + Redis cache

import random

def _get_mock_fleet_data() -> list[dict]:
    statuses = (
        ["revenue_service"] * 18 + ["standby"] * 3 +
        ["ibl"] * 2 + ["maintenance"] * 2
    )
    random.seed(42)
    return [
        {
            "id": f"ts-{i+1:03d}",
            "trainset_code": f"TS-{i+1:02d}",
            "rake_number": f"KMRL-R{i+1:03d}",
            "current_status": statuses[i],
            "current_bay": f"{'AB'[i % 2]}{i % 12 + 1}",
            "total_mileage_km": round(4000 + random.uniform(-800, 800), 1),
            "brake_health": round(60 + random.uniform(10, 40), 1),
            "hvac_health": round(70 + random.uniform(5, 30), 1),
            "door_health": round(75 + random.uniform(5, 25), 1),
            "days_since_service": random.randint(5, 60),
            "days_since_ibl": random.randint(10, 100),
            "open_jobs": random.randint(0, 5),
            "critical_jobs": random.randint(0, 2) if i in [2, 7, 21] else 0,
            "is_active": True,
            "last_updated": datetime.now(timezone.utc).isoformat(),
        }
        for i in range(25)
    ]

def _build_trainset_states():
    """Convert mock fleet data to optimizer TrainsetState objects."""
    from app.optimization.engine import TrainsetState
    fleet = _get_mock_fleet_data()
    random.seed(42)
    return [
        TrainsetState(
            id=ts["id"],
            code=ts["trainset_code"],
            fitness_valid=ts["critical_jobs"] == 0,
            signalling_clear=True,
            telecom_clear=True,
            critical_jobs_open=ts["critical_jobs"],
            mileage_km=ts["total_mileage_km"],
            brake_health_pct=ts["brake_health"],
            hvac_health_pct=ts["hvac_health"],
            door_health_pct=ts["door_health"],
            cleaning_done=random.random() > 0.3,
            current_bay=ts["current_bay"],
            branding_priority=random.randint(0, 100),
            branding_exposure_deficit_hrs=random.uniform(0, 20),
            days_since_ibl=ts["days_since_ibl"],
            predicted_failure_risk=round(random.uniform(0.05, 0.4), 3),
        )
        for ts in fleet
    ]

def _get_mock_jobs() -> list[dict]:
    return [
        {"id": f"JOB-{2840+i}", "trainset_code": f"TS-{i+1:02d}", "system": sys,
         "priority": pri, "status": "open", "is_critical": i < 3}
        for i, (sys, pri) in enumerate([
            ("Brake System", "critical"), ("Door Sensor", "critical"),
            ("HVAC Compressor", "critical"), ("Pantograph", "high"),
            ("Bogie", "medium"), ("Door Motor", "high"),
        ])
    ]

def _get_mock_alerts() -> list[dict]:
    return [
        {"id": f"ALT-{i}", "alert_code": code, "severity": sev,
         "trainset_code": ts, "title": title, "description": desc,
         "is_acknowledged": i > 4,
         "created_at": (datetime.now(timezone.utc) - timedelta(minutes=i * 8)).isoformat()}
        for i, (code, sev, ts, title, desc) in enumerate([
            ("CERT_EXPIRY", "critical", "TS-22", "Fitness Certificate Expiring in 2 Days", "Immediate IBL inspection required before next revenue run."),
            ("BRAKE_WEAR", "critical", "TS-07", "Brake Wear AI Alert", "Predictive model flags 88% confidence of wear limit breach in 8–12 days."),
            ("BAY_CONFLICT", "warning", "TS-18", "Bay Conflict Row B", "Shunting conflict at 22:30 — AI rescheduled."),
            ("JOB_OVERRUN", "warning", "TS-03", "Maintenance Job Overrun", "Job card KMRL-2847 not cleared. Est. completion 03:45 IST."),
            ("BRANDING_SLA", "info", "TS-09", "Branding SLA Risk", "Zoho contract 72hrs below weekly exposure target."),
            ("MILEAGE_LOW", "info", "TS-11", "Mileage Rebalance", "31km below fleet average — recommend additional service window."),
            ("CLEANING_OPT", "info", None, "Cleaning Schedule Optimized", "7 trainsets scheduled for deep clean 23:00–02:00."),
        ])
    ]

def _get_mock_certificates() -> list[dict]:
    today = date.today()
    return [
        {"trainset_code": "TS-22", "cert_type": "rolling_stock_fitness",
         "expiry_date": str(today + timedelta(days=2)), "status": "expiring_soon"},
        {"trainset_code": "TS-07", "cert_type": "brake_health",
         "expiry_date": str(today - timedelta(days=3)), "status": "expired"},
        {"trainset_code": "TS-14", "cert_type": "telecom_clearance",
         "expiry_date": str(today + timedelta(days=7)), "status": "expiring_soon"},
        {"trainset_code": "TS-01", "cert_type": "rolling_stock_fitness",
         "expiry_date": str(today + timedelta(days=42)), "status": "valid"},
    ]

def _get_mock_depot_layout(depot_code: str) -> dict:
    return {
        "depot_code": depot_code,
        "depot_name": "Muttom Depot",
        "total_bays": 25,
        "occupied_bays": 22,
        "bays": [
            {"bay_code": f"{'AB'[i // 12]}{i % 12 + 1}",
             "bay_type": "ibl" if i < 4 else "cleaning" if i < 7 else "stabling",
             "is_occupied": i < 22,
             "trainset_code": f"TS-{i+1:02d}" if i < 22 else None}
            for i in range(25)
        ]
    }
