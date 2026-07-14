# KMRL NexusAI — Train Induction Planning & Scheduling Platform

> AI-Driven nightly train induction optimization for Kochi Metro Rail Limited

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                         KMRL NexusAI Platform                       │
├──────────────┬──────────────┬──────────────────┬────────────────────┤
│  Next.js 15  │  FastAPI     │  OR-Tools Engine  │  ML Services       │
│  Frontend    │  REST/WS API │  Optimization     │  XGBoost/PyTorch   │
├──────────────┴──────────────┴──────────────────┴────────────────────┤
│                    Apache Kafka (Event Bus)                          │
├──────────────┬──────────────┬──────────────────┬────────────────────┤
│  PostgreSQL  │  Redis       │  Celery Workers   │  MinIO (Storage)   │
│  Primary DB  │  Cache/Queue │  Async Tasks      │  File Storage      │
└──────────────┴──────────────┴──────────────────┴────────────────────┘
```

## Quick Start

```bash
# Clone and start all services
git clone https://github.com/kmrl/nexusai
cd kmrl-nexusai
cp .env.example .env
docker-compose up -d
```

Platform available at: http://localhost:3000
API docs: http://localhost:8000/docs
Kafka UI: http://localhost:8080

## Vercel Deployment

Deploy the repository root to Vercel and the build will target `frontend/` automatically, or set the Vercel root directory to `frontend/` if you prefer. Host `backend/` separately. The Vercel-specific setup guide is in [docs/VERCEL.md](/C:/Users/WELCOME/Downloads/kmrl-nexusai/kmrl/docs/VERCEL.md).

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | Next.js 15, TypeScript, Tailwind CSS, Framer Motion |
| Backend | Python 3.12, FastAPI, SQLAlchemy 2.0, Alembic |
| AI/ML | OR-Tools, XGBoost, PyTorch, scikit-learn, SHAP |
| Database | PostgreSQL 16, Redis 7 |
| Messaging | Apache Kafka 3.6 |
| Workers | Celery 5, Flower |
| Infra | Docker, Kubernetes 1.29, Helm 3 |
| Monitoring | Prometheus, Grafana, Jaeger |

## Project Structure

```
kmrl/
├── backend/               # FastAPI application
│   ├── app/
│   │   ├── api/v1/       # REST endpoints
│   │   ├── core/         # Config, security, logging
│   │   ├── db/           # Database engine, migrations
│   │   ├── models/       # SQLAlchemy ORM models
│   │   ├── schemas/      # Pydantic request/response schemas
│   │   ├── services/     # Business logic layer
│   │   ├── ml/           # ML inference services
│   │   └── optimization/ # OR-Tools engine
│   └── tests/
├── frontend/             # Next.js 15 app
├── ml/                   # Training pipelines
├── infra/
│   ├── docker/           # Dockerfiles
│   ├── k8s/              # Kubernetes manifests
│   └── helm/             # Helm charts
└── docs/                 # Documentation
```

## Fleet Configuration

- **Current fleet**: 25 trainsets (4-car rake)
- **Target fleet**: 40 trainsets
- **Depots**: Muttom (primary), planned expansion 2027
- **Planning window**: 21:00–23:00 IST nightly

## License

Proprietary — Kochi Metro Rail Limited © 2025
