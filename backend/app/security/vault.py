"""
KMRL NexusAI — HashiCorp Vault Secrets Manager
================================================
Replaces hard-coded environment variables with dynamic
secrets fetched from Vault at runtime.

Features:
  - Dynamic database credentials (auto-rotated every 1h)
  - Static secrets (API keys, JWT secret)
  - Transit secrets engine (encrypt-at-rest for PII)
  - Kubernetes auth method (pod identity)
  - Auto-renewal of leases before expiry
  - Fallback to environment variables when Vault unavailable
"""
from __future__ import annotations

import asyncio
import logging
import os
import time
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

VAULT_ADDR          = os.getenv("VAULT_ADDR", "http://vault:8200")
VAULT_NAMESPACE     = os.getenv("VAULT_NAMESPACE", "kmrl")
VAULT_K8S_ROLE      = os.getenv("VAULT_K8S_ROLE", "kmrl-api")
VAULT_MOUNT_DB      = "database"
VAULT_MOUNT_KV      = "secret"
VAULT_MOUNT_TRANSIT = "transit"
VAULT_DB_ROLE       = "kmrl-api-role"
VAULT_TRANSIT_KEY   = "kmrl-pii"


# ── Secret Lease ─────────────────────────────────────────────────────────

@dataclass
class SecretLease:
    """Tracks a Vault lease for auto-renewal."""
    lease_id:      str
    secret:        dict[str, Any]
    lease_duration: int          # seconds
    renewable:     bool
    fetched_at:    float = field(default_factory=time.time)

    @property
    def expires_at(self) -> float:
        return self.fetched_at + self.lease_duration

    @property
    def should_renew(self) -> bool:
        """Renew when 80% of lease duration has elapsed."""
        elapsed = time.time() - self.fetched_at
        return self.renewable and elapsed > (self.lease_duration * 0.8)

    @property
    def is_expired(self) -> bool:
        return time.time() >= self.expires_at


# ── Vault Client ──────────────────────────────────────────────────────────

class VaultClient:
    """
    Async Vault client with Kubernetes auth.
    Falls back gracefully to environment variables if Vault unreachable.
    """

    def __init__(self):
        self._token: str | None = None
        self._token_expires: float = 0
        self._leases: dict[str, SecretLease] = {}
        self._available = False
        self._renewal_task: asyncio.Task | None = None

    async def authenticate(self) -> bool:
        """Authenticate using Kubernetes service account token."""
        try:
            import httpx

            k8s_token_path = "/var/run/secrets/kubernetes.io/serviceaccount/token"
            if not os.path.exists(k8s_token_path):
                # Dev environment — use VAULT_TOKEN env var
                self._token = os.getenv("VAULT_TOKEN", "dev-root-token")
                self._available = bool(self._token)
                return self._available

            with open(k8s_token_path) as f:
                jwt = f.read().strip()

            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(
                    f"{VAULT_ADDR}/v1/auth/kubernetes/login",
                    json={"role": VAULT_K8S_ROLE, "jwt": jwt},
                    headers={"X-Vault-Namespace": VAULT_NAMESPACE},
                )
                resp.raise_for_status()
                data = resp.json()

            auth = data["auth"]
            self._token = auth["client_token"]
            self._token_expires = time.time() + auth["lease_duration"]
            self._available = True
            logger.info("Vault: authenticated via Kubernetes (TTL=%ds)", auth["lease_duration"])
            return True

        except Exception as exc:
            logger.warning("Vault authentication failed, using env vars: %s", exc)
            self._available = False
            return False

    async def _request(self, method: str, path: str, **kwargs) -> dict:
        """Make an authenticated Vault API request."""
        import httpx

        if not self._token:
            raise RuntimeError("Not authenticated")

        headers = {
            "X-Vault-Token":     self._token,
            "X-Vault-Namespace": VAULT_NAMESPACE,
        }
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await getattr(client, method)(
                f"{VAULT_ADDR}/v1/{path}",
                headers=headers,
                **kwargs,
            )
            resp.raise_for_status()
            return resp.json()

    # ── Database Credentials ─────────────────────────────────────────────

    async def get_database_credentials(self) -> dict[str, str]:
        """
        Get dynamic PostgreSQL credentials from Vault.
        Vault auto-rotates these every 1 hour.
        Returns {'username': ..., 'password': ...}
        """
        cache_key = "db_creds"
        lease = self._leases.get(cache_key)
        if lease and not lease.is_expired:
            return lease.secret

        if not self._available:
            return self._fallback_db_creds()

        try:
            data = await self._request("get", f"{VAULT_MOUNT_DB}/creds/{VAULT_DB_ROLE}")
            creds = {"username": data["data"]["username"], "password": data["data"]["password"]}
            self._leases[cache_key] = SecretLease(
                lease_id=data["lease_id"],
                secret=creds,
                lease_duration=data["lease_duration"],
                renewable=data["renewable"],
            )
            logger.info("Vault: fetched dynamic DB credentials (TTL=%ds)", data["lease_duration"])
            return creds
        except Exception as exc:
            logger.warning("Vault DB creds failed, using env: %s", exc)
            return self._fallback_db_creds()

    def _fallback_db_creds(self) -> dict[str, str]:
        """Parse credentials from DATABASE_URL env var."""
        url = os.getenv("DATABASE_URL", "postgresql+asyncpg://kmrl:kmrl_secret@localhost:5432/kmrl_nexusai")
        try:
            from urllib.parse import urlparse
            parsed = urlparse(url.replace("+asyncpg", ""))
            return {"username": parsed.username or "kmrl", "password": parsed.password or ""}
        except Exception:
            return {"username": "kmrl", "password": ""}

    # ── Static Secrets ───────────────────────────────────────────────────

    async def get_secret(self, path: str, key: str) -> str:
        """Read a KV v2 secret."""
        if not self._available:
            return os.getenv(key.upper(), "")

        try:
            data = await self._request("get", f"{VAULT_MOUNT_KV}/data/{path}")
            return data["data"]["data"].get(key, "")
        except Exception as exc:
            logger.warning("Vault KV read failed (%s/%s): %s", path, key, exc)
            return os.getenv(key.upper(), "")

    async def get_jwt_secret(self) -> str:
        return await self.get_secret("kmrl/api", "SECRET_KEY") or os.getenv("SECRET_KEY", "")

    async def get_smtp_password(self) -> str:
        return await self.get_secret("kmrl/email", "SMTP_PASSWORD") or os.getenv("SMTP_PASSWORD", "")

    async def get_whatsapp_token(self) -> str:
        return await self.get_secret("kmrl/notifications", "WHATSAPP_API_TOKEN") or os.getenv("WHATSAPP_API_TOKEN", "")

    # ── Transit Encryption ───────────────────────────────────────────────

    async def encrypt(self, plaintext: str) -> str:
        """Encrypt PII data using Vault Transit engine."""
        if not self._available:
            import base64
            return base64.b64encode(plaintext.encode()).decode()  # dev fallback

        import base64
        b64 = base64.b64encode(plaintext.encode()).decode()
        try:
            data = await self._request(
                "post",
                f"{VAULT_MOUNT_TRANSIT}/encrypt/{VAULT_TRANSIT_KEY}",
                json={"plaintext": b64},
            )
            return data["data"]["ciphertext"]
        except Exception as exc:
            logger.error("Vault encrypt failed: %s", exc)
            return base64.b64encode(plaintext.encode()).decode()

    async def decrypt(self, ciphertext: str) -> str:
        """Decrypt ciphertext using Vault Transit engine."""
        if not self._available or not ciphertext.startswith("vault:"):
            import base64
            try:
                return base64.b64decode(ciphertext).decode()
            except Exception:
                return ciphertext

        import base64
        try:
            data = await self._request(
                "post",
                f"{VAULT_MOUNT_TRANSIT}/decrypt/{VAULT_TRANSIT_KEY}",
                json={"ciphertext": ciphertext},
            )
            return base64.b64decode(data["data"]["plaintext"]).decode()
        except Exception as exc:
            logger.error("Vault decrypt failed: %s", exc)
            return ciphertext

    # ── Lease Renewal ────────────────────────────────────────────────────

    async def start_renewal_loop(self) -> None:
        """Background task — renew leases before expiry."""
        logger.info("Vault: starting lease renewal loop")
        while True:
            try:
                for key, lease in list(self._leases.items()):
                    if lease.is_expired:
                        del self._leases[key]
                        logger.info("Vault: expired lease removed: %s", key)
                    elif lease.should_renew:
                        await self._renew_lease(key, lease)
            except Exception as exc:
                logger.error("Vault renewal loop error: %s", exc)
            await asyncio.sleep(60)

    async def _renew_lease(self, cache_key: str, lease: SecretLease) -> None:
        try:
            data = await self._request(
                "post",
                "sys/leases/renew",
                json={"lease_id": lease.lease_id, "increment": lease.lease_duration},
            )
            lease.lease_duration = data.get("lease_duration", lease.lease_duration)
            lease.fetched_at = time.time()
            logger.debug("Vault: renewed lease %s (TTL=%ds)", cache_key, lease.lease_duration)
        except Exception as exc:
            logger.warning("Vault: lease renewal failed for %s: %s", cache_key, exc)
            del self._leases[cache_key]


# ── Singleton ─────────────────────────────────────────────────────────────

_vault_client: VaultClient | None = None


async def get_vault_client() -> VaultClient:
    global _vault_client
    if _vault_client is None:
        _vault_client = VaultClient()
        await _vault_client.authenticate()
    return _vault_client


async def init_vault(app=None) -> VaultClient:
    """Initialize Vault client and start renewal loop. Called at app startup."""
    client = await get_vault_client()
    if client._available:
        import asyncio
        asyncio.create_task(client.start_renewal_loop())
        logger.info("Vault: secrets manager active")
    else:
        logger.warning("Vault: unavailable — using environment variable fallback")
    return client
