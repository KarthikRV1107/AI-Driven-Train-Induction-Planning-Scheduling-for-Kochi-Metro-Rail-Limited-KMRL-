# KMRL NexusAI — CI/CD Setup Guide
## GitHub Actions Secrets & Environment Configuration

---

## Required GitHub Secrets

Configure these in: **Repository → Settings → Secrets and variables → Actions**

### Container Registry

| Secret | Value | Used In |
|--------|-------|---------|
| `GITHUB_TOKEN` | Auto-provided by GitHub | Image push to GHCR |

### Kubernetes Access

| Secret | Value | Used In |
|--------|-------|---------|
| `KUBE_CONFIG_STAGING` | `base64 ~/.kube/config-staging` | Staging deploy |
| `KUBE_CONFIG_PRODUCTION` | `base64 ~/.kube/config-prod` | Production deploy |

### Database (Production)

| Secret | Value | Used In |
|--------|-------|---------|
| `PROD_DATABASE_URL` | Full asyncpg connection string | DB migrations job |

### Notifications

| Secret | Value | Used In |
|--------|-------|---------|
| `SLACK_WEBHOOK_URL` | Slack incoming webhook URL | Deploy notifications |

### Smoke Tests

| Secret | Value | Used In |
|--------|-------|---------|
| `SMOKE_TEST_TOKEN` | Valid JWT for smoke test user | Production smoke tests |

### Code Quality

| Secret | Value | Used In |
|--------|-------|---------|
| `CODECOV_TOKEN` | Codecov.io token | Coverage upload |
| `SNYK_TOKEN` | Snyk security token | Dependency scanning |

---

## Setting Secrets via GitHub CLI

```bash
# Install gh CLI
brew install gh   # macOS
gh auth login

# Set all secrets at once
gh secret set KUBE_CONFIG_STAGING     < ~/.kube/config-staging-b64
gh secret set KUBE_CONFIG_PRODUCTION  < ~/.kube/config-prod-b64
gh secret set SLACK_WEBHOOK_URL       --body "https://hooks.slack.com/services/..."
gh secret set SMOKE_TEST_TOKEN        --body "eyJhbGci..."
gh secret set PROD_DATABASE_URL       --body "postgresql+asyncpg://..."
gh secret set CODECOV_TOKEN           --body "your-codecov-token"
```

---

## GitHub Environments

Configure in: **Repository → Settings → Environments**

### Staging Environment
```
Name: staging
Protection rules:
  - Required reviewers: none
  - Wait timer: 0 minutes
  - Deployment branches: develop
Environment secrets:
  - Same as above (staging-specific values)
Environment URL: https://staging.nexusai.kmrl.in
```

### Production Environment
```
Name: production
Protection rules:
  - Required reviewers: 1 (Operations Manager or Tech Lead)
  - Wait timer: 0 minutes
  - Deployment branches: main
Environment secrets:
  - KUBE_CONFIG_PRODUCTION
  - PROD_DATABASE_URL
  - SMOKE_TEST_TOKEN
Environment URL: https://nexusai.kmrl.in
```

---

## Branch Protection Rules

Configure in: **Repository → Settings → Branches → Add rule**

### `main` branch
```yaml
Branch name pattern: main
☑ Require a pull request before merging
  ☑ Require approvals: 1
  ☑ Dismiss stale pull request approvals when new commits are pushed
  ☑ Require review from code owners
☑ Require status checks to pass before merging
  Required status checks:
    - lint-backend
    - lint-frontend
    - test-backend (3.11)
    - test-backend (3.12)
    - test-optimizer
    - test-frontend
    - security-scan
☑ Require branches to be up to date before merging
☑ Require conversation resolution before merging
☑ Require signed commits
☑ Restrict pushes that create matching branches
☑ Do not allow bypassing the above settings
```

### `develop` branch
```yaml
Branch name pattern: develop
☑ Require a pull request before merging
  ☑ Require approvals: 1
☑ Require status checks to pass before merging
  Required: lint-backend, lint-frontend, test-backend, test-optimizer
☑ Allow force pushes: Admin only
```

---

## CODEOWNERS File

```
# .github/CODEOWNERS

# Global owners
* @kmrl-platform-team

# AI/ML changes require ML team review
backend/app/optimization/   @kmrl-ai-team
backend/app/ml/             @kmrl-ai-team
backend/app/rl/             @kmrl-ai-team

# Infrastructure changes require DevOps review
infra/                      @kmrl-devops-team
.github/workflows/          @kmrl-devops-team

# Security changes require Security team review
backend/app/security/       @kmrl-security-team
infra/vault/                @kmrl-security-team

# Frontend design changes
frontend/                   @kmrl-frontend-team

# Database migrations require DBA review
backend/app/db/migrations/  @kmrl-dba-team
backend/app/db/schema.sql   @kmrl-dba-team
```

---

## Workflow Triggers Summary

```
┌─────────────────────────────────────────────────────────────────────┐
│  Git Event             │  Triggered Jobs                            │
├─────────────────────────────────────────────────────────────────────┤
│  PR → develop/main     │  lint → test (all) → security-scan        │
│  push → develop        │  + build → deploy-staging                 │
│  push → main           │  + build → deploy-production (w/ approval)│
│  Schedule (02:00 UTC)  │  security-scan (Trivy + Bandit + audit)   │
│  workflow_dispatch     │  full pipeline with target env selection   │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Local CI Simulation

Run the CI pipeline locally before pushing using `act`:

```bash
# Install act
brew install act

# Run all jobs
act push

# Run specific job
act push -j test-backend

# Run with secrets
act push --secret-file .env.ci

# Dry run (show what would run)
act push --dryrun
```

---

## Pipeline Performance Benchmarks

| Stage | Typical Duration | Parallelism |
|-------|-----------------|-------------|
| lint-backend | 45s | — |
| lint-frontend | 30s | — |
| test-backend (3.12) | 3m 20s | — |
| test-optimizer | 2m 45s | — |
| test-frontend | 2m 10s | — |
| security-scan | 4m 30s | — |
| build-images (API) | 5m 15s | With BuildKit cache |
| build-images (Frontend) | 4m 45s | With BuildKit cache |
| deploy-staging | 3m 00s | — |
| deploy-production | 6m 30s | Includes migration |
| **Total (main push)** | **~18 minutes** | Tests run in parallel |

---

## Notification Configuration

Slack channel routing:
```yaml
# .github/slack-config.yaml
channels:
  deploy-success:   "#kmrl-deployments"
  deploy-failure:   "#kmrl-alerts-p1"
  security-finding: "#kmrl-security"
  test-failure:     "#kmrl-platform"
```

---

## Dependabot Configuration

```yaml
# .github/dependabot.yml
version: 2
updates:
  - package-ecosystem: pip
    directory: /backend
    schedule:
      interval: weekly
      day: monday
      time: "09:00"
      timezone: Asia/Kolkata
    labels: [dependencies, python]
    open-pull-requests-limit: 5
    ignore:
      - dependency-name: torch
        update-types: [version-update:semver-major]

  - package-ecosystem: npm
    directory: /frontend
    schedule:
      interval: weekly
      day: monday
    labels: [dependencies, javascript]
    open-pull-requests-limit: 5

  - package-ecosystem: docker
    directory: /infra/docker
    schedule:
      interval: monthly
    labels: [dependencies, docker]

  - package-ecosystem: github-actions
    directory: /
    schedule:
      interval: monthly
    labels: [dependencies, github-actions]
```
