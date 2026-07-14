# ============================================================
# KMRL NexusAI — Makefile
# Usage: make <target>
# ============================================================

.PHONY: help dev prod test test-unit test-integration test-e2e test-load \
        build push migrate seed lint format type-check clean logs \
        optimizer-run ml-train drift-check vault-init keycloak-import \
        chaos-run k8s-deploy helm-upgrade docs backup

SHELL       := /bin/bash
APP_VERSION := 2.4.1
REGISTRY    := ghcr.io/kmrl
NAMESPACE   := kmrl-production
COMPOSE     := docker-compose -f infra/docker/docker-compose.yml
KUBECTL     := kubectl -n $(NAMESPACE)
HELM        := helm -n $(NAMESPACE)

# ── Help ──────────────────────────────────────────────────────────────────
help:
	@echo ""
	@echo "  KMRL NexusAI v$(APP_VERSION) — Available Commands"
	@echo "  ─────────────────────────────────────────────────"
	@echo "  Development:"
	@echo "    make dev          Start all services (Docker Compose)"
	@echo "    make logs         Stream API logs"
	@echo "    make seed         Load demo dataset"
	@echo "    make migrate      Run DB migrations"
	@echo ""
	@echo "  Testing:"
	@echo "    make test         Run all tests"
	@echo "    make test-unit    Unit + optimizer tests"
	@echo "    make test-int     Integration pipeline tests"
	@echo "    make test-e2e     Cypress E2E tests"
	@echo "    make test-load    k6 load tests"
	@echo "    make chaos-run    Chaos Toolkit experiments"
	@echo ""
	@echo "  AI/ML:"
	@echo "    make ml-train     Train all ML models"
	@echo "    make optimizer-run  Trigger nightly optimizer"
	@echo "    make drift-check  Run model drift detection"
	@echo ""
	@echo "  Security:"
	@echo "    make vault-init   Initialize HashiCorp Vault"
	@echo "    make keycloak-import  Import KMRL realm to Keycloak"
	@echo ""
	@echo "  Production:"
	@echo "    make build        Build Docker images"
	@echo "    make push         Push images to registry"
	@echo "    make k8s-deploy   Deploy to Kubernetes"
	@echo "    make helm-upgrade Upgrade Helm release"
	@echo "    make backup       Trigger manual DB backup"
	@echo ""

# ── Development ───────────────────────────────────────────────────────────
dev:
	@echo "Starting KMRL NexusAI development stack..."
	$(COMPOSE) up -d
	@echo ""
	@echo "  Platform:    http://localhost:3000"
	@echo "  API docs:    http://localhost:8000/docs"
	@echo "  Kafka UI:    http://localhost:8080"
	@echo "  Flower:      http://localhost:5555"
	@echo "  Grafana:     http://localhost:3001"
	@echo "  Prometheus:  http://localhost:9090"
	@echo ""

stop:
	$(COMPOSE) down

clean:
	$(COMPOSE) down -v --remove-orphans
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .next -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name node_modules -exec rm -rf {} + 2>/dev/null || true
	@echo "Clean complete"

logs:
	$(COMPOSE) logs -f api worker-optimization

logs-all:
	$(COMPOSE) logs -f

# ── Database ─────────────────────────────────────────────────────────────
migrate:
	@echo "Running Alembic migrations..."
	$(COMPOSE) exec api alembic upgrade head
	@echo "Migrations complete"

migrate-down:
	$(COMPOSE) exec api alembic downgrade -1

migrate-new:
	@read -p "Migration name: " name; \
	$(COMPOSE) exec api alembic revision --autogenerate -m "$$name"

seed:
	@echo "Loading demo dataset..."
	$(COMPOSE) exec api python scripts/seed_demo_data.py
	@echo "Seed complete"

# ── Testing ───────────────────────────────────────────────────────────────
test: test-unit test-int

test-unit:
	@echo "Running unit + optimizer tests..."
	$(COMPOSE) exec api pytest tests/test_suite.py \
		-v \
		--cov=app \
		--cov-report=term-missing \
		--cov-report=html:coverage-report \
		--cov-fail-under=75 \
		-x \
		--tb=short \
		-q
	@echo "Unit tests complete. Coverage report: coverage-report/index.html"

test-int:
	@echo "Running integration pipeline tests..."
	$(COMPOSE) exec api pytest tests/test_integration.py \
		-v \
		-m "integration" \
		--tb=short \
		-q
	@echo "Integration tests complete"

test-e2e:
	@echo "Running Cypress E2E tests..."
	cd frontend && npx cypress run --spec "tests/e2e/**/*.cy.ts"

test-e2e-open:
	cd frontend && npx cypress open

test-load:
	@echo "Running k6 load tests..."
	@read -p "API token: " token; \
	k6 run \
		--env BASE_URL=http://localhost:8000 \
		--env API_TOKEN=$$token \
		tests/load/load_test.js
	@echo "Load test complete"

test-soak:
	@echo "Running 4-hour soak test..."
	@read -p "API token: " token; \
	k6 run \
		--duration 4h \
		--env BASE_URL=http://localhost:8000 \
		--env API_TOKEN=$$token \
		--env SOAK=true \
		tests/load/load_test.js

chaos-run:
	@echo "Running chaos experiments..."
	pip install chaostoolkit --quiet
	chaos run infra/chaos/experiments.json
	@echo "Chaos experiments complete"

# ── Lint & Format ─────────────────────────────────────────────────────────
lint:
	@echo "Linting Python..."
	cd backend && ruff check app/ tests/
	@echo "Linting TypeScript..."
	cd frontend && npm run lint

format:
	cd backend && black app/ tests/ && isort app/ tests/
	cd frontend && npx prettier --write "src/**/*.{ts,tsx,css}"

type-check:
	cd backend && mypy app/ --ignore-missing-imports
	cd frontend && npm run type-check

# ── AI/ML Operations ──────────────────────────────────────────────────────
ml-train:
	@echo "Training ML models..."
	$(COMPOSE) exec worker-ml celery -A app.workers.celery_app call \
		workers.retrain_ml_models \
		--timeout=3600
	@echo "Training complete. Models saved to /app/models"

optimizer-run:
	@echo "Triggering nightly optimization..."
	$(COMPOSE) exec api python -c "
from app.workers import run_nightly_optimization
result = run_nightly_optimization.delay()
print('Task ID:', result.id)
print('Waiting for result...')
output = result.get(timeout=60)
print('Result:', output)
"

drift-check:
	@echo "Running drift detection..."
	$(COMPOSE) exec worker-ml celery -A app.workers.celery_app call \
		workers.run_drift_detection
	@echo "Drift check complete"

rl-warmup:
	@echo "Running RL warm-start simulation (100 episodes)..."
	$(COMPOSE) exec api python -c "
from app.rl.agent import HistoricalLearningService
svc = HistoricalLearningService()
result = svc.simulate_learning(n_episodes=100)
print('Episodes:', result['episodes'])
print('Avg reward:', result['avg_reward'])
print('Final epsilon:', result['final_epsilon'])
print('Weights:', result['final_weights'])
"

# ── Security ─────────────────────────────────────────────────────────────
vault-init:
	@echo "Initializing HashiCorp Vault..."
	kubectl apply -f infra/vault/vault-keycloak.yaml
	kubectl wait --for=condition=ready pod -l app=vault -n vault-system --timeout=120s
	kubectl exec -n vault-system vault-0 -- vault operator init \
		-key-shares=1 \
		-key-threshold=1 \
		-format=json | tee /tmp/vault-keys.json
	@echo ""
	@echo "⚠️  IMPORTANT: Save /tmp/vault-keys.json to a secure location and DELETE it!"

keycloak-import:
	@echo "Importing KMRL realm to Keycloak..."
	kubectl wait --for=condition=ready pod -l app=keycloak -n keycloak-system --timeout=300s
	kubectl exec -n keycloak-system deploy/keycloak -- \
		/opt/keycloak/bin/kc.sh import \
		--file /opt/keycloak/data/import/kmrl-realm.json
	@echo "Realm imported successfully"

ssl-check:
	@echo "Checking TLS certificates..."
	echo | openssl s_client -connect nexusai.kmrl.in:443 2>/dev/null | \
		openssl x509 -noout -dates

# ── Docker ────────────────────────────────────────────────────────────────
build:
	@echo "Building Docker images..."
	docker build -f infra/docker/Dockerfile.api \
		--target production \
		-t $(REGISTRY)/nexusai-api:$(APP_VERSION) \
		-t $(REGISTRY)/nexusai-api:latest \
		./backend
	docker build -f infra/docker/Dockerfile.frontend \
		--target production \
		-t $(REGISTRY)/nexusai-frontend:$(APP_VERSION) \
		-t $(REGISTRY)/nexusai-frontend:latest \
		./frontend
	@echo "Build complete: $(APP_VERSION)"

push:
	docker push $(REGISTRY)/nexusai-api:$(APP_VERSION)
	docker push $(REGISTRY)/nexusai-api:latest
	docker push $(REGISTRY)/nexusai-frontend:$(APP_VERSION)
	docker push $(REGISTRY)/nexusai-frontend:latest
	@echo "Images pushed to $(REGISTRY)"

scan:
	@echo "Scanning images for vulnerabilities..."
	trivy image $(REGISTRY)/nexusai-api:$(APP_VERSION)
	trivy image $(REGISTRY)/nexusai-frontend:$(APP_VERSION)

# ── Kubernetes ────────────────────────────────────────────────────────────
k8s-deploy:
	@echo "Deploying to Kubernetes ($(NAMESPACE))..."
	kubectl apply -f infra/k8s/base/deployment.yaml
	$(KUBECTL) rollout status deployment/kmrl-api --timeout=300s
	$(KUBECTL) rollout status deployment/kmrl-frontend --timeout=300s
	@echo "Deployment complete"

helm-upgrade:
	@read -p "Image tag [$(APP_VERSION)]: " tag; \
	tag=$${tag:-$(APP_VERSION)}; \
	$(HELM) upgrade --install kmrl-prod ./infra/helm/kmrl \
		--namespace $(NAMESPACE) \
		--set image.api.tag=$$tag \
		--set image.frontend.tag=$$tag \
		--values infra/helm/kmrl/values.yaml \
		--atomic \
		--timeout 15m
	@echo "Helm upgrade complete: $$tag"

k8s-status:
	$(KUBECTL) get pods,svc,ingress,hpa

k8s-rollback:
	$(HELM) rollback kmrl-prod --namespace $(NAMESPACE)

# ── Monitoring ────────────────────────────────────────────────────────────
prometheus-reload:
	curl -s -X POST http://localhost:9090/-/reload

grafana-import:
	$(COMPOSE) exec api python -c "
import json, requests
from app.observability.telemetry import GRAFANA_DASHBOARD
resp = requests.post(
    'http://localhost:3001/api/dashboards/import',
    headers={'Authorization': 'Bearer admin', 'Content-Type': 'application/json'},
    json={'dashboard': GRAFANA_DASHBOARD, 'overwrite': True, 'folderId': 0}
)
print(resp.status_code, resp.json())
"

# ── Backup ────────────────────────────────────────────────────────────────
backup:
	@echo "Creating database backup..."
	$(COMPOSE) exec postgres pg_dump -U kmrl kmrl_nexusai | \
		gzip > backups/kmrl_db_$$(date +%Y%m%d_%H%M%S).sql.gz
	@echo "Backup saved to backups/"

backup-k8s:
	@echo "Triggering Velero backup..."
	velero backup create kmrl-manual-$$(date +%Y%m%d-%H%M%S) \
		--include-namespaces $(NAMESPACE) \
		--wait

restore-k8s:
	@read -p "Backup name: " name; \
	velero restore create --from-backup $$name --wait

# ── Documentation ─────────────────────────────────────────────────────────
docs:
	@echo "Generating API docs from OpenAPI spec..."
	npx @redocly/cli build-docs docs/openapi.yaml \
		--output docs/api-reference.html \
		--title "KMRL NexusAI API Reference"
	@echo "API docs generated: docs/api-reference.html"
