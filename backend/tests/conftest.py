"""
KMRL NexusAI — pytest Configuration & Shared Fixtures
=======================================================
conftest.py is automatically loaded by pytest for all test files.
"""
from __future__ import annotations

import asyncio
import os
from typing import AsyncGenerator, Generator

import pytest
import pytest_asyncio

# ── Event Loop ────────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def event_loop():
    """Create a single event loop for the entire test session."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


# ── Environment ───────────────────────────────────────────────────────────

@pytest.fixture(scope="session", autouse=True)
def set_test_env():
    """Set test environment variables before any test runs."""
    os.environ.setdefault("ENVIRONMENT",  "test")
    os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://kmrl:kmrl_test@localhost:5432/kmrl_test")
    os.environ.setdefault("REDIS_URL",    "redis://localhost:6379/0")
    os.environ.setdefault("CELERY_BROKER_URL", "redis://localhost:6379/1")
    os.environ.setdefault("CELERY_RESULT_BACKEND", "redis://localhost:6379/2")
    os.environ.setdefault("SECRET_KEY",   "test-secret-key-minimum-32-chars-padded")
    os.environ.setdefault("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
    os.environ.setdefault("ML_MODEL_PATH", "/tmp/kmrl-test-models")
    os.environ.setdefault("DEBUG", "false")
    os.environ.setdefault("LOG_LEVEL", "WARNING")
    yield


# ── FastAPI App ───────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def app():
    """Return the FastAPI application instance."""
    from app.main import app as fastapi_app
    return fastapi_app


@pytest.fixture(scope="module")
def http_client(app):
    """Synchronous HTTPX client for API tests."""
    import httpx
    with httpx.Client(app=app, base_url="http://testserver") as client:
        yield client


@pytest_asyncio.fixture(scope="module")
async def async_client(app):
    """Async HTTPX client for async API tests."""
    import httpx
    async with httpx.AsyncClient(app=app, base_url="http://testserver") as client:
        yield client


# ── Auth Token ────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def auth_token(http_client):
    """Get a valid JWT token for depot_controller role."""
    resp = http_client.post(
        "/api/v1/auth/token",
        data={"username": "depot_controller@kmrl.in", "password": "kmrl@2025"},
    )
    if resp.status_code != 200:
        pytest.skip("Auth endpoint unavailable — skipping authenticated tests")
    return resp.json()["access_token"]


@pytest.fixture(scope="module")
def auth_headers(auth_token):
    """Authorization headers dict."""
    return {"Authorization": f"Bearer {auth_token}"}


# ── Fleet Data ────────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def minimal_fleet():
    """10-trainset minimal fleet for fast tests."""
    import random
    random.seed(1)
    statuses = ["revenue_service"] * 7 + ["standby"] * 2 + ["maintenance"] * 1
    return [
        {
            "id":              f"ts-{i+1:03d}",
            "trainset_code":   f"TS-{i+1:02d}",
            "rake_number":     f"KMRL-R{i+1:03d}",
            "current_status":  statuses[i],
            "current_bay":     f"A{i+1}",
            "total_mileage_km": round(3500 + random.uniform(-500, 500), 1),
            "brake_health":    round(70 + random.uniform(0, 30), 1),
            "hvac_health":     round(75 + random.uniform(0, 25), 1),
            "door_health":     round(80 + random.uniform(0, 20), 1),
            "days_since_service": random.randint(5, 45),
            "days_since_ibl":    random.randint(10, 80),
            "open_jobs":       random.randint(0, 2),
            "critical_jobs":   0,
            "year_of_manufacture": 2015,
            "pantograph_wear": 30.0,
        }
        for i in range(10)
    ]


@pytest.fixture(scope="session")
def full_fleet():
    """25-trainset full fleet matching production spec."""
    import random
    random.seed(42)
    statuses = (["revenue_service"] * 18 + ["standby"] * 3 +
                ["ibl"] * 2 + ["maintenance"] * 2)
    return [
        {
            "id":              f"ts-{i+1:03d}",
            "trainset_code":   f"TS-{i+1:02d}",
            "rake_number":     f"KMRL-R{i+1:03d}",
            "current_status":  statuses[i],
            "current_bay":     f"{'AB'[i // 12]}{i % 12 + 1}",
            "total_mileage_km": round(3000 + random.uniform(0, 2000), 1),
            "brake_health":    round(55 + random.uniform(0, 45), 1),
            "hvac_health":     round(65 + random.uniform(0, 35), 1),
            "door_health":     round(70 + random.uniform(0, 30), 1),
            "days_since_service": random.randint(5, 90),
            "days_since_ibl":    random.randint(10, 120),
            "open_jobs":       random.randint(0, 4),
            "critical_jobs":   1 if i in [2, 6, 21] else 0,
            "year_of_manufacture": random.randint(2011, 2019),
            "pantograph_wear": round(random.uniform(20, 70), 1),
        }
        for i in range(25)
    ]


# ── Optimizer Fixtures ────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def depot_config():
    from app.optimization.engine import DepotConfig
    return DepotConfig(revenue_target=18)


@pytest.fixture(scope="session")
def trainset_states(full_fleet):
    """Convert full fleet to TrainsetState objects."""
    from app.optimization.engine import TrainsetState
    return [
        TrainsetState(
            id=ts["id"], code=ts["trainset_code"],
            fitness_valid=ts["critical_jobs"] == 0,
            critical_jobs_open=ts["critical_jobs"],
            mileage_km=ts["total_mileage_km"],
            brake_health_pct=ts["brake_health"],
            hvac_health_pct=ts["hvac_health"],
            door_health_pct=ts["door_health"],
            cleaning_done=True,
            current_bay=ts["current_bay"],
            days_since_ibl=ts["days_since_ibl"],
            predicted_failure_risk=round(
                (1 - min(ts["brake_health"], ts["hvac_health"], ts["door_health"]) / 100) * 0.6, 3
            ),
        )
        for ts in full_fleet
    ]


@pytest.fixture
def optimizer(depot_config):
    from app.optimization.engine import InductionOptimizer
    return InductionOptimizer(depot=depot_config, timeout_seconds=15)


# ── ML Fixtures ───────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def maintenance_features():
    """A sample maintenance feature dict for inference tests."""
    import random
    random.seed(7)
    from app.ml.pipeline import MAINTENANCE_FEATURES
    return {feat: round(random.uniform(0, 100), 2) for feat in MAINTENANCE_FEATURES}


@pytest.fixture(scope="session")
def trained_maintenance_model(maintenance_features):
    """A maintenance model trained on minimal synthetic data."""
    import numpy as np
    import pandas as pd
    from app.ml.pipeline import MAINTENANCE_FEATURES, PredictiveMaintenanceModel

    n = 300
    np.random.seed(0)
    X = pd.DataFrame({f: np.random.uniform(0, 100, n) for f in MAINTENANCE_FEATURES})
    model = PredictiveMaintenanceModel(horizon_days=14)

    for system in ["brake", "hvac", "door"]:
        y = pd.DataFrame({
            f"{system}_failure_in_14d": (np.random.random(n) < 0.1).astype(int)
        })
        model.train(X, y, system=system)

    return model


# ── Simulation Fixtures ───────────────────────────────────────────────────

@pytest.fixture(scope="session")
def sim_trainsets(full_fleet):
    """Convert fleet data to SimTrainset objects."""
    from app.simulation.engine import SimTrainset, TrainState

    status_map = {
        "revenue_service": TrainState.IN_SERVICE,
        "standby":         TrainState.STABLED,
        "ibl":             TrainState.IBL,
        "maintenance":     TrainState.MAINTENANCE,
    }
    return [
        SimTrainset(
            id=ts["id"], code=ts["trainset_code"],
            current_bay=ts["current_bay"],
            state=status_map.get(ts["current_status"], TrainState.STABLED),
            mileage_km=ts["total_mileage_km"],
            brake_health=ts["brake_health"],
            cleaning_done=True,
            assigned_status=ts["current_status"],
        )
        for ts in full_fleet
    ]


@pytest.fixture
def depot_layout():
    from app.simulation.engine import DepotLayout
    return DepotLayout()


# ── Markers ───────────────────────────────────────────────────────────────

def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line("markers", "slow: tests taking >5 seconds")
    config.addinivalue_line("markers", "integration: full pipeline integration tests")
    config.addinivalue_line("markers", "ml: machine learning model tests")
    config.addinivalue_line("markers", "optimizer: OR-Tools optimizer tests")
    config.addinivalue_line("markers", "api: FastAPI endpoint tests")
    config.addinivalue_line("markers", "security: authentication and authorization tests")
    config.addinivalue_line("markers", "chaos: resilience and fault-injection tests")


# ── Pytest Settings ───────────────────────────────────────────────────────

def pytest_collection_modifyitems(config, items):
    """Auto-mark tests based on file location."""
    for item in items:
        if "integration" in str(item.fspath):
            item.add_marker(pytest.mark.integration)
        if "chaos" in str(item.fspath):
            item.add_marker(pytest.mark.chaos)
        if "load" in str(item.fspath):
            item.add_marker(pytest.mark.slow)
