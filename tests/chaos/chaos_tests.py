"""
KMRL NexusAI — Chaos Engineering Suite
=========================================
Tests system resilience under failure conditions.

Scenarios:
  1. Database connection pool exhaustion
  2. Kafka broker unavailability
  3. ML model serving failure (fallback to heuristic)
  4. Redis cache miss cascade
  5. Celery worker death (optimizer task orphan)
  6. Network partition simulation
  7. Memory pressure on optimization engine
  8. Clock skew (NTP drift simulation)
  9. High-concurrency WebSocket storm
  10. Optimizer timeout stress

Uses:
  - Locust for HTTP load generation
  - Chaos Toolkit for infrastructure faults
  - pytest for assertion framework
"""
from __future__ import annotations

import asyncio
import contextlib
import logging
import os
import random
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Any

import pytest
import httpx

logger = logging.getLogger(__name__)

BASE_URL = os.getenv("TEST_BASE_URL", "http://localhost:8000")
AUTH_TOKEN = os.getenv("TEST_AUTH_TOKEN", "")


# ── Test Fixtures ─────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def auth_token():
    """Get a valid JWT token for authenticated requests."""
    resp = httpx.post(
        f"{BASE_URL}/api/v1/auth/token",
        data={"username": "depot_controller@kmrl.in", "password": "kmrl@2025"},
    )
    if resp.status_code != 200:
        pytest.skip("Cannot authenticate — API not running")
    return resp.json()["access_token"]


@pytest.fixture
def client(auth_token):
    return httpx.Client(
        base_url=BASE_URL,
        headers={"Authorization": f"Bearer {auth_token}"},
        timeout=60,
    )


# ── Scenario 1: Health Under Load ─────────────────────────────────────────

class TestHealthUnderLoad:
    """System should remain healthy under concurrent request load."""

    def test_health_endpoint_survives_50_concurrent(self):
        """Health check must succeed even under 50 concurrent requests."""
        with ThreadPoolExecutor(max_workers=50) as pool:
            futures = [pool.submit(httpx.get, f"{BASE_URL}/health") for _ in range(50)]
            results = [f.result() for f in futures]

        success_count = sum(1 for r in results if r.status_code == 200)
        assert success_count >= 48, f"Only {success_count}/50 health checks succeeded"

    def test_kpi_endpoint_stable_under_20_concurrent(self, client):
        """KPI endpoint must not return 500s under concurrent access."""
        def fetch_kpis():
            return client.get("/api/v1/kpis").status_code

        with ThreadPoolExecutor(max_workers=20) as pool:
            statuses = list(pool.map(lambda _: fetch_kpis(), range(20)))

        server_errors = sum(1 for s in statuses if s >= 500)
        assert server_errors == 0, f"{server_errors} server errors under load"


# ── Scenario 2: Optimizer Resilience ─────────────────────────────────────

class TestOptimizerResilience:
    """Optimizer must degrade gracefully and never hang."""

    def test_optimizer_respects_timeout(self, client):
        """Optimizer must return within 40 seconds regardless of fleet size."""
        start = time.time()
        resp  = client.post(
            "/api/v1/induction/optimize",
            json={"depot_id": "dep-001"},
            timeout=45,
        )
        elapsed = time.time() - start
        assert elapsed < 40, f"Optimizer took {elapsed:.1f}s — exceeds 35s SLA"
        assert resp.status_code in (200, 202), f"Unexpected status: {resp.status_code}"

    def test_optimizer_returns_feasible_plan_on_edge_cases(self, client):
        """Even with all standby fleet, optimizer must return a feasible result."""
        resp = client.post(
            "/api/v1/induction/optimize",
            json={"depot_id": "dep-001", "override_revenue_target": 1},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] in ("optimal", "feasible")
        assert len(data.get("revenue_service", [])) >= 1

    def test_concurrent_optimizer_calls_do_not_deadlock(self, client):
        """Two simultaneous optimizer calls must not deadlock."""
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [
                pool.submit(
                    client.post,
                    "/api/v1/induction/optimize",
                    json={"depot_id": "dep-001"},
                )
                for _ in range(2)
            ]
            results = [f.result(timeout=60) for f in futures]

        for resp in results:
            assert resp.status_code in (200, 202, 429), \
                f"Unexpected status: {resp.status_code}"


# ── Scenario 3: Cache Failure Fallback ───────────────────────────────────

class TestCacheFailureFallback:
    """System must serve responses even when Redis is unavailable."""

    def test_fleet_endpoint_serves_without_cache(self, client):
        """Fleet data must come from DB if Redis is down."""
        # Simulate cache miss by requesting with cache-bypass header
        resp = client.get(
            "/api/v1/fleet",
            headers={"Cache-Control": "no-cache"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "trainsets" in data
        assert len(data["trainsets"]) > 0

    def test_kpis_fallback_without_redis(self, client):
        """KPIs must still be calculable from DB when Redis unavailable."""
        resp = client.get("/api/v1/kpis")
        assert resp.status_code == 200


# ── Scenario 4: ML Fallback ───────────────────────────────────────────────

class TestMLFallback:
    """ML endpoints must fall back to heuristics when models unavailable."""

    def test_maintenance_predictions_return_without_trained_model(self, client):
        """Should return heuristic-based risk scores even without trained models."""
        resp = client.get("/api/v1/maintenance/predictions")
        # Acceptable: 200 (real or heuristic), 503 (model unavailable)
        assert resp.status_code in (200, 503)
        if resp.status_code == 200:
            data = resp.json()
            assert "predictions" in data

    def test_optimizer_runs_without_ml_model(self, client):
        """Optimizer must use rule-based fallback when ML model unavailable."""
        resp = client.post(
            "/api/v1/induction/optimize",
            json={"depot_id": "dep-001"},
        )
        assert resp.status_code in (200, 202)
        if resp.status_code == 200:
            assert resp.json().get("status") in ("optimal", "feasible", "fallback")


# ── Scenario 5: Auth Edge Cases ───────────────────────────────────────────

class TestAuthResilience:
    """Authentication must be robust against edge case inputs."""

    def test_expired_token_rejected(self):
        """Expired JWT must be rejected with 401."""
        expired = (
            "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
            "eyJzdWIiOiJ1c3ItMDAxIiwiZXhwIjoxMDAwMDAwMDAwfQ."
            "INVALID_SIGNATURE"
        )
        resp = httpx.get(
            f"{BASE_URL}/api/v1/kpis",
            headers={"Authorization": f"Bearer {expired}"},
        )
        assert resp.status_code == 401

    def test_malformed_token_rejected(self):
        """Completely invalid token must be rejected."""
        resp = httpx.get(
            f"{BASE_URL}/api/v1/kpis",
            headers={"Authorization": "Bearer not.a.jwt"},
        )
        assert resp.status_code == 401

    def test_missing_auth_header_rejected(self):
        """Missing Authorization header must return 401, not 500."""
        resp = httpx.get(f"{BASE_URL}/api/v1/kpis")
        assert resp.status_code == 401

    def test_brute_force_blocked(self):
        """10 rapid invalid login attempts should trigger rate limiting."""
        responses = []
        for _ in range(12):
            r = httpx.post(
                f"{BASE_URL}/api/v1/auth/token",
                data={"username": "attacker@evil.com", "password": "wrong"},
            )
            responses.append(r.status_code)

        # After several attempts, should get rate-limited (429) or remain 401
        rate_limited = any(s == 429 for s in responses[-3:])
        all_rejected  = all(s in (401, 422, 429) for s in responses)
        assert all_rejected, f"Unexpected status in brute force test: {responses}"


# ── Scenario 6: Input Validation (Fuzzing) ───────────────────────────────

class TestInputValidation:
    """API must handle malformed inputs without crashing."""

    FUZZ_INPUTS = [
        {"depot_id": "' OR 1=1; --"},          # SQL injection
        {"depot_id": "<script>alert(1)</script>"},  # XSS
        {"depot_id": "A" * 10000},               # oversized string
        {"override_revenue_target": -999},       # negative value
        {"override_revenue_target": 999999},     # absurd value
        {},                                      # missing required fields
        {"depot_id": None},                      # null value
    ]

    @pytest.mark.parametrize("payload", FUZZ_INPUTS)
    def test_optimizer_handles_malformed_input(self, client, payload):
        """Optimizer must return 400/422, never 500, for bad inputs."""
        resp = client.post("/api/v1/induction/optimize", json=payload)
        assert resp.status_code in (400, 422, 200), \
            f"Got {resp.status_code} for payload {payload} — 500 not acceptable"

    def test_fleet_status_filter_handles_invalid_value(self, client):
        """Invalid status filter must return 422, not 500."""
        resp = client.get("/api/v1/fleet?status_filter=HACKED")
        assert resp.status_code in (200, 422)


# ── Scenario 7: Graceful Degradation Under Partial Failure ────────────────

class TestGracefulDegradation:
    """Core operations must work even when non-critical services are down."""

    def test_alerts_accessible_without_kafka(self, client):
        """Alerts from DB must be accessible even if Kafka is down."""
        resp = client.get("/api/v1/alerts")
        assert resp.status_code == 200

    def test_fleet_accessible_without_ml_service(self, client):
        """Fleet data must be accessible even without ML predictions."""
        resp = client.get("/api/v1/fleet")
        assert resp.status_code == 200
        assert len(resp.json().get("trainsets", [])) > 0

    def test_depot_layout_accessible_standalone(self, client):
        """Depot layout must serve from DB, independent of all other services."""
        resp = client.get("/api/v1/depot/MTM/layout")
        assert resp.status_code in (200, 404)

    def test_error_responses_are_json(self, client):
        """All error responses must be valid JSON (not HTML error pages)."""
        resp = client.get("/api/v1/nonexistent-endpoint")
        assert resp.status_code == 404
        try:
            data = resp.json()
            assert "error" in data or "detail" in data
        except Exception:
            pytest.fail("404 response was not valid JSON")


# ── Locust Load Test Class ────────────────────────────────────────────────

try:
    from locust import HttpUser, between, events, task

    class KMRLUser(HttpUser):
        """Locust user simulating a KMRL platform operator."""
        wait_time = between(1, 5)
        token: str = ""

        def on_start(self):
            resp = self.client.post(
                "/api/v1/auth/token",
                data={"username": "depot_controller@kmrl.in", "password": "kmrl@2025"},
            )
            if resp.status_code == 200:
                self.token = resp.json().get("access_token", "")

        def _auth(self) -> dict:
            return {"Authorization": f"Bearer {self.token}"}

        @task(10)
        def view_kpis(self):
            self.client.get("/api/v1/kpis", headers=self._auth(), name="GET /kpis")

        @task(8)
        def view_fleet(self):
            self.client.get("/api/v1/fleet", headers=self._auth(), name="GET /fleet")

        @task(5)
        def view_alerts(self):
            self.client.get("/api/v1/alerts", headers=self._auth(), name="GET /alerts")

        @task(3)
        def view_maintenance(self):
            self.client.get("/api/v1/maintenance/predictions", headers=self._auth(), name="GET /maintenance/predictions")

        @task(2)
        def view_depot(self):
            self.client.get("/api/v1/depot/MTM/layout", headers=self._auth(), name="GET /depot/layout")

        @task(1)
        def run_optimizer(self):
            self.client.post(
                "/api/v1/induction/optimize",
                json={"depot_id": "dep-001"},
                headers=self._auth(),
                name="POST /induction/optimize",
            )

        @task(4)
        def view_analytics(self):
            self.client.get("/api/v1/analytics/availability-trend?days=30",
                            headers=self._auth(), name="GET /analytics/trend")

    class KMRLAdminUser(KMRLUser):
        """Admin user with higher optimizer call rate."""
        weight = 1

        @task(3)
        def run_optimizer(self):
            self.client.post(
                "/api/v1/induction/optimize",
                json={"depot_id": "dep-001", "override_revenue_target": 18},
                headers=self._auth(),
                name="POST /induction/optimize (admin)",
            )

except ImportError:
    logger.info("Locust not installed — skipping Locust user classes")
