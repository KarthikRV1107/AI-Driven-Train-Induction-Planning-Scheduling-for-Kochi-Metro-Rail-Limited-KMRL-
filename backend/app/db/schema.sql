-- ============================================================
-- KMRL NexusAI — Complete Database Schema
-- PostgreSQL 16 · Partitioned · Indexed
-- ============================================================

-- Extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";
CREATE EXTENSION IF NOT EXISTS "timescaledb";  -- for time-series telemetry

-- ── Enums ────────────────────────────────────────────────────────────

CREATE TYPE trainset_status AS ENUM (
    'revenue_service', 'standby', 'ibl', 'maintenance',
    'cleaning', 'stabling', 'out_of_service'
);

CREATE TYPE fitness_cert_status AS ENUM (
    'valid', 'expiring_soon', 'expired', 'pending_renewal'
);

CREATE TYPE job_card_priority AS ENUM ('critical', 'high', 'medium', 'low');
CREATE TYPE job_card_status AS ENUM ('open', 'in_progress', 'completed', 'deferred');
CREATE TYPE alert_severity AS ENUM ('critical', 'warning', 'info');
CREATE TYPE alert_channel AS ENUM ('dashboard', 'email', 'sms', 'whatsapp');
CREATE TYPE user_role AS ENUM (
    'admin', 'depot_controller', 'maintenance_supervisor',
    'operations_manager', 'cleaning_team_lead', 'branding_manager'
);
CREATE TYPE optimization_status AS ENUM ('pending', 'running', 'completed', 'failed');

-- ── Core Tables ───────────────────────────────────────────────────────

CREATE TABLE depots (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    code            VARCHAR(10) UNIQUE NOT NULL,
    name            VARCHAR(100) NOT NULL,
    location        VARCHAR(200),
    total_bays      INTEGER NOT NULL DEFAULT 25,
    ibl_bays        INTEGER NOT NULL DEFAULT 4,
    cleaning_bays   INTEGER NOT NULL DEFAULT 3,
    layout_json     JSONB,                          -- depot geometry
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE trainsets (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    trainset_code       VARCHAR(10) UNIQUE NOT NULL,  -- e.g. TS-01
    rake_number         VARCHAR(20) UNIQUE NOT NULL,
    manufacturer        VARCHAR(100),
    year_of_manufacture INTEGER,
    car_count           INTEGER NOT NULL DEFAULT 4,
    depot_id            UUID REFERENCES depots(id),
    current_status      trainset_status NOT NULL DEFAULT 'stabling',
    current_bay         VARCHAR(10),
    total_mileage_km    NUMERIC(12, 2) DEFAULT 0,
    last_service_date   DATE,
    next_service_due    DATE,
    is_active           BOOLEAN NOT NULL DEFAULT TRUE,
    metadata            JSONB DEFAULT '{}',
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    updated_at          TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE users (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    employee_id     VARCHAR(20) UNIQUE NOT NULL,
    email           VARCHAR(255) UNIQUE NOT NULL,
    hashed_password VARCHAR(255) NOT NULL,
    full_name       VARCHAR(100) NOT NULL,
    role            user_role NOT NULL,
    depot_id        UUID REFERENCES depots(id),
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    last_login      TIMESTAMPTZ,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

-- ── Certificates & Clearances ─────────────────────────────────────────

CREATE TABLE fitness_certificates (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    trainset_id     UUID NOT NULL REFERENCES trainsets(id) ON DELETE CASCADE,
    cert_type       VARCHAR(50) NOT NULL,  -- rolling_stock, signalling, telecom, brake, hvac, door
    cert_number     VARCHAR(100),
    issuing_authority VARCHAR(100),
    issued_date     DATE NOT NULL,
    expiry_date     DATE NOT NULL,
    status          fitness_cert_status NOT NULL DEFAULT 'valid',
    document_url    VARCHAR(500),
    notes           TEXT,
    created_by      UUID REFERENCES users(id),
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW(),

    CONSTRAINT unique_active_cert UNIQUE (trainset_id, cert_type, expiry_date)
);

-- ── Maintenance ───────────────────────────────────────────────────────

CREATE TABLE maintenance_jobs (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    trainset_id     UUID NOT NULL REFERENCES trainsets(id),
    job_type        VARCHAR(50) NOT NULL,  -- scheduled, corrective, predictive, emergency
    system_affected VARCHAR(100) NOT NULL, -- brake, hvac, door, bogie, pantograph, etc.
    description     TEXT,
    priority        job_card_priority NOT NULL DEFAULT 'medium',
    status          job_card_status NOT NULL DEFAULT 'open',
    estimated_hours NUMERIC(5, 2),
    actual_hours    NUMERIC(5, 2),
    assigned_to     UUID REFERENCES users(id),
    depot_id        UUID REFERENCES depots(id),
    scheduled_start TIMESTAMPTZ,
    scheduled_end   TIMESTAMPTZ,
    actual_start    TIMESTAMPTZ,
    actual_end      TIMESTAMPTZ,
    ibm_maximo_ref  VARCHAR(50),            -- IBM Maximo WO reference
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE job_cards (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    job_id          UUID NOT NULL REFERENCES maintenance_jobs(id),
    card_number     VARCHAR(50) UNIQUE NOT NULL,
    description     TEXT NOT NULL,
    is_critical     BOOLEAN NOT NULL DEFAULT FALSE,
    status          job_card_status NOT NULL DEFAULT 'open',
    completed_by    UUID REFERENCES users(id),
    completed_at    TIMESTAMPTZ,
    sign_off_notes  TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- ── Mileage Tracking ──────────────────────────────────────────────────

CREATE TABLE mileage_logs (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    trainset_id     UUID NOT NULL REFERENCES trainsets(id),
    log_date        DATE NOT NULL,
    service_km      NUMERIC(8, 2) NOT NULL DEFAULT 0,
    test_km         NUMERIC(8, 2) NOT NULL DEFAULT 0,
    total_km        NUMERIC(8, 2) GENERATED ALWAYS AS (service_km + test_km) STORED,
    cumulative_km   NUMERIC(12, 2),
    route_code      VARCHAR(20),
    trips_count     INTEGER DEFAULT 0,
    created_at      TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE (trainset_id, log_date)
) PARTITION BY RANGE (log_date);

-- Monthly partitions for mileage
CREATE TABLE mileage_logs_2025_01 PARTITION OF mileage_logs
    FOR VALUES FROM ('2025-01-01') TO ('2025-02-01');
CREATE TABLE mileage_logs_2025_06 PARTITION OF mileage_logs
    FOR VALUES FROM ('2025-06-01') TO ('2026-01-01');
CREATE TABLE mileage_logs_2026 PARTITION OF mileage_logs
    FOR VALUES FROM ('2026-01-01') TO ('2027-01-01');

-- ── Cleaning ─────────────────────────────────────────────────────────

CREATE TABLE cleaning_slots (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    trainset_id     UUID NOT NULL REFERENCES trainsets(id),
    cleaning_type   VARCHAR(30) NOT NULL,  -- interior, exterior, deep, sanitization
    bay_id          VARCHAR(10),
    depot_id        UUID REFERENCES depots(id),
    scheduled_start TIMESTAMPTZ NOT NULL,
    scheduled_end   TIMESTAMPTZ NOT NULL,
    actual_start    TIMESTAMPTZ,
    actual_end      TIMESTAMPTZ,
    completed       BOOLEAN DEFAULT FALSE,
    assigned_team   UUID REFERENCES users(id),
    notes           TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- ── Branding ──────────────────────────────────────────────────────────

CREATE TABLE branding_contracts (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    trainset_id     UUID NOT NULL REFERENCES trainsets(id),
    advertiser_name VARCHAR(100) NOT NULL,
    contract_ref    VARCHAR(50) UNIQUE,
    branding_type   VARCHAR(50),           -- full_wrap, partial, interior
    start_date      DATE NOT NULL,
    end_date        DATE NOT NULL,
    min_exposure_hrs_per_week NUMERIC(5, 2) DEFAULT 0,
    actual_exposure_hrs NUMERIC(8, 2) DEFAULT 0,
    sla_compliant   BOOLEAN GENERATED ALWAYS AS (
                        actual_exposure_hrs >= min_exposure_hrs_per_week
                    ) STORED,
    priority_score  INTEGER DEFAULT 50,    -- 0–100, higher = prioritize for service
    is_active       BOOLEAN DEFAULT TRUE,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

-- ── Depot Layout ─────────────────────────────────────────────────────

CREATE TABLE depot_bays (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    depot_id        UUID NOT NULL REFERENCES depots(id),
    bay_code        VARCHAR(10) NOT NULL,
    bay_type        VARCHAR(20) NOT NULL,  -- stabling, ibl, cleaning, maintenance
    row_label       VARCHAR(5),
    position_x      NUMERIC(6, 2),
    position_y      NUMERIC(6, 2),
    is_occupied     BOOLEAN DEFAULT FALSE,
    occupied_by     UUID REFERENCES trainsets(id),
    is_operational  BOOLEAN DEFAULT TRUE,

    UNIQUE (depot_id, bay_code)
);

-- ── Shunting ──────────────────────────────────────────────────────────

CREATE TABLE shunting_operations (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    trainset_id     UUID NOT NULL REFERENCES trainsets(id),
    depot_id        UUID REFERENCES depots(id),
    from_bay        VARCHAR(10),
    to_bay          VARCHAR(10),
    operation_type  VARCHAR(30),           -- induction, withdrawal, repositioning
    planned_time    TIMESTAMPTZ,
    actual_time     TIMESTAMPTZ,
    duration_mins   INTEGER,
    operator_id     UUID REFERENCES users(id),
    ai_generated    BOOLEAN DEFAULT FALSE,
    notes           TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- ── Induction Plans ───────────────────────────────────────────────────

CREATE TABLE induction_plans (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    plan_date       DATE NOT NULL,
    depot_id        UUID REFERENCES depots(id),
    created_by      UUID REFERENCES users(id),
    optimization_status optimization_status DEFAULT 'pending',
    optimizer_version VARCHAR(20),
    score           NUMERIC(5, 2),         -- 0–100 optimization score
    revenue_count   INTEGER,
    standby_count   INTEGER,
    ibl_count       INTEGER,
    maintenance_count INTEGER,
    plan_json       JSONB NOT NULL,        -- full plan details
    override_notes  TEXT,
    approved_by     UUID REFERENCES users(id),
    approved_at     TIMESTAMPTZ,
    created_at      TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE (plan_date, depot_id)
);

CREATE TABLE induction_plan_items (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    plan_id         UUID NOT NULL REFERENCES induction_plans(id),
    trainset_id     UUID NOT NULL REFERENCES trainsets(id),
    assigned_status trainset_status NOT NULL,
    assigned_bay    VARCHAR(10),
    priority_rank   INTEGER,
    confidence_pct  NUMERIC(5, 2),
    ai_reasoning    JSONB,                 -- SHAP-based explanation
    constraint_violations JSONB DEFAULT '[]',
    is_override     BOOLEAN DEFAULT FALSE,
    override_by     UUID REFERENCES users(id),
    override_reason TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- ── Alerts ────────────────────────────────────────────────────────────

CREATE TABLE alerts (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    alert_code      VARCHAR(50) NOT NULL,
    severity        alert_severity NOT NULL,
    trainset_id     UUID REFERENCES trainsets(id),
    depot_id        UUID REFERENCES depots(id),
    title           VARCHAR(200) NOT NULL,
    description     TEXT,
    channel         alert_channel[] DEFAULT '{dashboard}',
    is_acknowledged BOOLEAN DEFAULT FALSE,
    acknowledged_by UUID REFERENCES users(id),
    acknowledged_at TIMESTAMPTZ,
    auto_resolved   BOOLEAN DEFAULT FALSE,
    metadata        JSONB DEFAULT '{}',
    created_at      TIMESTAMPTZ DEFAULT NOW()
) PARTITION BY RANGE (created_at);

CREATE TABLE alerts_2025 PARTITION OF alerts
    FOR VALUES FROM ('2025-01-01') TO ('2026-01-01');
CREATE TABLE alerts_2026 PARTITION OF alerts
    FOR VALUES FROM ('2026-01-01') TO ('2027-01-01');

-- ── ML & AI ──────────────────────────────────────────────────────────

CREATE TABLE ml_predictions (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    trainset_id     UUID NOT NULL REFERENCES trainsets(id),
    model_name      VARCHAR(100) NOT NULL,
    model_version   VARCHAR(20),
    prediction_type VARCHAR(50) NOT NULL,  -- failure_risk, readiness, mileage_forecast
    predicted_value NUMERIC(10, 4),
    confidence      NUMERIC(5, 4),
    feature_importance JSONB,              -- SHAP values
    input_features  JSONB,
    prediction_horizon_days INTEGER,
    is_actioned     BOOLEAN DEFAULT FALSE,
    prediction_at   TIMESTAMPTZ DEFAULT NOW()
) PARTITION BY RANGE (prediction_at);

CREATE TABLE ml_predictions_2025 PARTITION OF ml_predictions
    FOR VALUES FROM ('2025-01-01') TO ('2026-01-01');
CREATE TABLE ml_predictions_2026 PARTITION OF ml_predictions
    FOR VALUES FROM ('2026-01-01') TO ('2027-01-01');

CREATE TABLE historical_decisions (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    plan_id         UUID REFERENCES induction_plans(id),
    trainset_id     UUID NOT NULL REFERENCES trainsets(id),
    planned_status  trainset_status,
    actual_status   trainset_status,
    outcome         VARCHAR(50),           -- successful, withdrawal, delayed, failure
    delay_minutes   INTEGER,
    notes           TEXT,
    recorded_at     TIMESTAMPTZ DEFAULT NOW()
);

-- ── Telemetry (TimescaleDB hypertable) ────────────────────────────────

CREATE TABLE telemetry_readings (
    time            TIMESTAMPTZ NOT NULL,
    trainset_id     UUID NOT NULL,
    sensor_type     VARCHAR(50) NOT NULL,  -- brake, hvac, door, speed, vibration
    value           NUMERIC(10, 4),
    unit            VARCHAR(20),
    is_anomaly      BOOLEAN DEFAULT FALSE,
    anomaly_score   NUMERIC(5, 4)
);

SELECT create_hypertable('telemetry_readings', 'time');

-- ── Audit Log ────────────────────────────────────────────────────────

CREATE TABLE audit_logs (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id         UUID REFERENCES users(id),
    action          VARCHAR(100) NOT NULL,
    resource_type   VARCHAR(50),
    resource_id     UUID,
    old_value       JSONB,
    new_value       JSONB,
    ip_address      INET,
    user_agent      TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW()
) PARTITION BY RANGE (created_at);

CREATE TABLE audit_logs_2025 PARTITION OF audit_logs
    FOR VALUES FROM ('2025-01-01') TO ('2026-01-01');
CREATE TABLE audit_logs_2026 PARTITION OF audit_logs
    FOR VALUES FROM ('2026-01-01') TO ('2027-01-01');

-- ── Indexes ───────────────────────────────────────────────────────────

CREATE INDEX idx_trainsets_status ON trainsets(current_status);
CREATE INDEX idx_trainsets_depot ON trainsets(depot_id);
CREATE INDEX idx_fitness_certs_trainset ON fitness_certificates(trainset_id);
CREATE INDEX idx_fitness_certs_expiry ON fitness_certificates(expiry_date);
CREATE INDEX idx_fitness_certs_status ON fitness_certificates(status);
CREATE INDEX idx_maint_jobs_trainset ON maintenance_jobs(trainset_id);
CREATE INDEX idx_maint_jobs_status ON maintenance_jobs(status);
CREATE INDEX idx_maint_jobs_priority ON maintenance_jobs(priority);
CREATE INDEX idx_mileage_trainset_date ON mileage_logs(trainset_id, log_date DESC);
CREATE INDEX idx_induction_plans_date ON induction_plans(plan_date DESC);
CREATE INDEX idx_induction_items_plan ON induction_plan_items(plan_id);
CREATE INDEX idx_induction_items_trainset ON induction_plan_items(trainset_id);
CREATE INDEX idx_alerts_severity ON alerts(severity, created_at DESC);
CREATE INDEX idx_alerts_trainset ON alerts(trainset_id);
CREATE INDEX idx_ml_predictions_trainset ON ml_predictions(trainset_id, prediction_at DESC);
CREATE INDEX idx_audit_user ON audit_logs(user_id, created_at DESC);
CREATE INDEX idx_depot_bays_depot ON depot_bays(depot_id);
CREATE INDEX idx_telemetry_trainset ON telemetry_readings(trainset_id, time DESC);

-- ── Seed Data ─────────────────────────────────────────────────────────

INSERT INTO depots (code, name, location, total_bays, ibl_bays, cleaning_bays)
VALUES ('MTM', 'Muttom Depot', 'Aluva, Ernakulam, Kerala', 25, 4, 3);

-- Trigger: update updated_at
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN NEW.updated_at = NOW(); RETURN NEW; END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_trainsets_updated_at
    BEFORE UPDATE ON trainsets
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER trg_fitness_certs_updated_at
    BEFORE UPDATE ON fitness_certificates
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();
