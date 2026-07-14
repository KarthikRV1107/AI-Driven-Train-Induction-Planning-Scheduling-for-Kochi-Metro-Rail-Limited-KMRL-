"""
KMRL NexusAI — Core Configuration
"""
from functools import lru_cache
from typing import Literal
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # ── Application ──────────────────────────────────────────────────
    APP_NAME: str = "KMRL NexusAI"
    APP_VERSION: str = "2.4.1"
    ENVIRONMENT: Literal["development", "staging", "production"] = "development"
    DEBUG: bool = False
    SECRET_KEY: str = "change-me-in-production-use-openssl-rand-hex-32"
    ALLOWED_HOSTS: list[str] = ["*"]

    # ── Database ─────────────────────────────────────────────────────
    DATABASE_URL: str = "postgresql+asyncpg://kmrl:kmrl_secret@localhost:5432/kmrl_nexusai"
    DATABASE_POOL_SIZE: int = 20
    DATABASE_MAX_OVERFLOW: int = 10
    DATABASE_ECHO: bool = False

    # ── Redis ─────────────────────────────────────────────────────────
    REDIS_URL: str = "redis://localhost:6379/0"
    REDIS_CACHE_TTL: int = 300  # 5 minutes default

    # ── Auth ─────────────────────────────────────────────────────────
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # ── Kafka ─────────────────────────────────────────────────────────
    KAFKA_BOOTSTRAP_SERVERS: str = "localhost:9092"
    KAFKA_TOPIC_TELEMETRY: str = "kmrl.trainset.telemetry"
    KAFKA_TOPIC_ALERTS: str = "kmrl.alerts"
    KAFKA_TOPIC_INDUCTION: str = "kmrl.induction.plans"
    KAFKA_CONSUMER_GROUP: str = "kmrl-nexusai"

    # ── Celery ─────────────────────────────────────────────────────────
    CELERY_BROKER_URL: str = "redis://localhost:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/2"

    # ── ML ─────────────────────────────────────────────────────────────
    ML_MODEL_PATH: str = "/app/models"
    ML_RETRAIN_SCHEDULE: str = "0 3 * * *"  # 3 AM daily
    ML_MIN_TRAINING_SAMPLES: int = 500
    FEATURE_STORE_PATH: str = "/app/feature_store"

    # ── Optimization ──────────────────────────────────────────────────
    OPTIMIZER_TIMEOUT_SECONDS: int = 30
    OPTIMIZER_MAX_ITERATIONS: int = 10_000
    FLEET_SIZE: int = 25
    FLEET_SIZE_TARGET: int = 40
    PLANNING_WINDOW_START_HOUR: int = 21  # 21:00 IST
    PLANNING_WINDOW_END_HOUR: int = 23    # 23:00 IST

    # ── Alerts ────────────────────────────────────────────────────────
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    ALERT_EMAIL_FROM: str = "nexusai@kmrl.in"
    WHATSAPP_API_URL: str = ""
    WHATSAPP_API_TOKEN: str = ""

    # ── Monitoring ────────────────────────────────────────────────────
    SENTRY_DSN: str = ""
    PROMETHEUS_ENABLED: bool = True
    LOG_LEVEL: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
