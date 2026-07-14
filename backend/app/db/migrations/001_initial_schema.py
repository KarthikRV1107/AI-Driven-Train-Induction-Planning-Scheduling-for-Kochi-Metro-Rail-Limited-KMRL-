"""Initial schema — KMRL NexusAI v2.4.1

Revision ID: 001_initial_schema
Revises:
Create Date: 2025-06-01 21:00:00.000000
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── Extensions ──────────────────────────────────────────────────
    op.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"')
    op.execute('CREATE EXTENSION IF NOT EXISTS "pg_trgm"')

    # ── Enums ────────────────────────────────────────────────────────
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE trainset_status AS ENUM (
                'revenue_service','standby','ibl','maintenance',
                'cleaning','stabling','out_of_service'
            );
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE fitness_cert_status AS ENUM (
                'valid','expiring_soon','expired','pending_renewal'
            );
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE job_card_priority AS ENUM ('critical','high','medium','low');
            CREATE TYPE job_card_status AS ENUM ('open','in_progress','completed','deferred');
            CREATE TYPE alert_severity AS ENUM ('critical','warning','info');
            CREATE TYPE user_role AS ENUM (
                'admin','depot_controller','maintenance_supervisor',
                'operations_manager','cleaning_team_lead','branding_manager'
            );
            CREATE TYPE optimization_status AS ENUM ('pending','running','completed','failed');
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$;
    """)

    # ── depots ────────────────────────────────────────────────────────
    op.create_table(
        "depots",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("code", sa.String(10), unique=True, nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("location", sa.String(200)),
        sa.Column("total_bays", sa.Integer(), nullable=False, server_default="25"),
        sa.Column("ibl_bays", sa.Integer(), nullable=False, server_default="4"),
        sa.Column("cleaning_bays", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("layout_json", postgresql.JSONB()),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
    )

    # ── trainsets ─────────────────────────────────────────────────────
    op.create_table(
        "trainsets",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("trainset_code", sa.String(10), unique=True, nullable=False),
        sa.Column("rake_number", sa.String(20), unique=True, nullable=False),
        sa.Column("manufacturer", sa.String(100)),
        sa.Column("year_of_manufacture", sa.Integer()),
        sa.Column("car_count", sa.Integer(), nullable=False, server_default="4"),
        sa.Column("depot_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("depots.id")),
        sa.Column("current_status", sa.Text(), nullable=False, server_default="'stabling'"),
        sa.Column("current_bay", sa.String(10)),
        sa.Column("total_mileage_km", sa.Numeric(12, 2), server_default="0"),
        sa.Column("last_service_date", sa.Date()),
        sa.Column("next_service_due", sa.Date()),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("metadata", postgresql.JSONB(), server_default="'{}'"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
    )
    op.create_index("idx_trainsets_status", "trainsets", ["current_status"])
    op.create_index("idx_trainsets_depot", "trainsets", ["depot_id"])

    # ── users ─────────────────────────────────────────────────────────
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("employee_id", sa.String(20), unique=True, nullable=False),
        sa.Column("email", sa.String(255), unique=True, nullable=False),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("full_name", sa.String(100), nullable=False),
        sa.Column("role", sa.Text(), nullable=False),
        sa.Column("depot_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("depots.id")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("last_login", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
    )

    # ── fitness_certificates ──────────────────────────────────────────
    op.create_table(
        "fitness_certificates",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("trainset_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("trainsets.id", ondelete="CASCADE"), nullable=False),
        sa.Column("cert_type", sa.String(50), nullable=False),
        sa.Column("cert_number", sa.String(100)),
        sa.Column("issuing_authority", sa.String(100)),
        sa.Column("issued_date", sa.Date(), nullable=False),
        sa.Column("expiry_date", sa.Date(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default="'valid'"),
        sa.Column("document_url", sa.String(500)),
        sa.Column("notes", sa.Text()),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
        sa.UniqueConstraint("trainset_id", "cert_type", "expiry_date", name="uq_cert"),
    )
    op.create_index("idx_fitness_certs_trainset", "fitness_certificates", ["trainset_id"])
    op.create_index("idx_fitness_certs_expiry", "fitness_certificates", ["expiry_date"])
    op.create_index("idx_fitness_certs_status", "fitness_certificates", ["status"])

    # ── maintenance_jobs ──────────────────────────────────────────────
    op.create_table(
        "maintenance_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("trainset_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("trainsets.id"), nullable=False),
        sa.Column("job_type", sa.String(50), nullable=False),
        sa.Column("system_affected", sa.String(100), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("priority", sa.Text(), nullable=False, server_default="'medium'"),
        sa.Column("status", sa.Text(), nullable=False, server_default="'open'"),
        sa.Column("estimated_hours", sa.Numeric(5, 2)),
        sa.Column("actual_hours", sa.Numeric(5, 2)),
        sa.Column("assigned_to", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id")),
        sa.Column("depot_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("depots.id")),
        sa.Column("scheduled_start", sa.DateTime(timezone=True)),
        sa.Column("scheduled_end", sa.DateTime(timezone=True)),
        sa.Column("actual_start", sa.DateTime(timezone=True)),
        sa.Column("actual_end", sa.DateTime(timezone=True)),
        sa.Column("ibm_maximo_ref", sa.String(50)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
    )
    op.create_index("idx_maint_jobs_trainset", "maintenance_jobs", ["trainset_id"])
    op.create_index("idx_maint_jobs_status", "maintenance_jobs", ["status"])
    op.create_index("idx_maint_jobs_priority", "maintenance_jobs", ["priority"])

    # ── job_cards ─────────────────────────────────────────────────────
    op.create_table(
        "job_cards",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("job_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("maintenance_jobs.id"), nullable=False),
        sa.Column("card_number", sa.String(50), unique=True, nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("is_critical", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("status", sa.Text(), nullable=False, server_default="'open'"),
        sa.Column("completed_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id")),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("sign_off_notes", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
    )

    # ── mileage_logs ──────────────────────────────────────────────────
    op.create_table(
        "mileage_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("trainset_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("trainsets.id"), nullable=False),
        sa.Column("log_date", sa.Date(), nullable=False),
        sa.Column("service_km", sa.Numeric(8, 2), nullable=False, server_default="0"),
        sa.Column("test_km", sa.Numeric(8, 2), nullable=False, server_default="0"),
        sa.Column("cumulative_km", sa.Numeric(12, 2)),
        sa.Column("route_code", sa.String(20)),
        sa.Column("trips_count", sa.Integer(), server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
        sa.UniqueConstraint("trainset_id", "log_date", name="uq_mileage_daily"),
    )
    op.create_index("idx_mileage_trainset_date", "mileage_logs", ["trainset_id", sa.text("log_date DESC")])

    # ── cleaning_slots ────────────────────────────────────────────────
    op.create_table(
        "cleaning_slots",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("trainset_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("trainsets.id"), nullable=False),
        sa.Column("cleaning_type", sa.String(30), nullable=False),
        sa.Column("bay_id", sa.String(10)),
        sa.Column("depot_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("depots.id")),
        sa.Column("scheduled_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("scheduled_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("actual_start", sa.DateTime(timezone=True)),
        sa.Column("actual_end", sa.DateTime(timezone=True)),
        sa.Column("completed", sa.Boolean(), server_default="false"),
        sa.Column("assigned_team", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id")),
        sa.Column("notes", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
    )

    # ── branding_contracts ────────────────────────────────────────────
    op.create_table(
        "branding_contracts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("trainset_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("trainsets.id"), nullable=False),
        sa.Column("advertiser_name", sa.String(100), nullable=False),
        sa.Column("contract_ref", sa.String(50), unique=True),
        sa.Column("branding_type", sa.String(50)),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("min_exposure_hrs_per_week", sa.Numeric(5, 2), server_default="0"),
        sa.Column("actual_exposure_hrs", sa.Numeric(8, 2), server_default="0"),
        sa.Column("priority_score", sa.Integer(), server_default="50"),
        sa.Column("is_active", sa.Boolean(), server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
    )

    # ── depot_bays ────────────────────────────────────────────────────
    op.create_table(
        "depot_bays",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("depot_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("depots.id"), nullable=False),
        sa.Column("bay_code", sa.String(10), nullable=False),
        sa.Column("bay_type", sa.String(20), nullable=False),
        sa.Column("row_label", sa.String(5)),
        sa.Column("position_x", sa.Numeric(6, 2)),
        sa.Column("position_y", sa.Numeric(6, 2)),
        sa.Column("is_occupied", sa.Boolean(), server_default="false"),
        sa.Column("occupied_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("trainsets.id")),
        sa.Column("is_operational", sa.Boolean(), server_default="true"),
        sa.UniqueConstraint("depot_id", "bay_code", name="uq_depot_bay"),
    )
    op.create_index("idx_depot_bays_depot", "depot_bays", ["depot_id"])

    # ── shunting_operations ───────────────────────────────────────────
    op.create_table(
        "shunting_operations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("trainset_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("trainsets.id"), nullable=False),
        sa.Column("depot_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("depots.id")),
        sa.Column("from_bay", sa.String(10)),
        sa.Column("to_bay", sa.String(10)),
        sa.Column("operation_type", sa.String(30)),
        sa.Column("planned_time", sa.DateTime(timezone=True)),
        sa.Column("actual_time", sa.DateTime(timezone=True)),
        sa.Column("duration_mins", sa.Integer()),
        sa.Column("operator_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id")),
        sa.Column("ai_generated", sa.Boolean(), server_default="false"),
        sa.Column("notes", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
    )

    # ── induction_plans ───────────────────────────────────────────────
    op.create_table(
        "induction_plans",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("plan_date", sa.Date(), nullable=False),
        sa.Column("depot_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("depots.id")),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id")),
        sa.Column("optimization_status", sa.Text(), server_default="'pending'"),
        sa.Column("optimizer_version", sa.String(20)),
        sa.Column("score", sa.Numeric(5, 2)),
        sa.Column("revenue_count", sa.Integer()),
        sa.Column("standby_count", sa.Integer()),
        sa.Column("ibl_count", sa.Integer()),
        sa.Column("maintenance_count", sa.Integer()),
        sa.Column("plan_json", postgresql.JSONB(), nullable=False),
        sa.Column("override_notes", sa.Text()),
        sa.Column("approved_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id")),
        sa.Column("approved_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
        sa.UniqueConstraint("plan_date", "depot_id", name="uq_plan_date_depot"),
    )
    op.create_index("idx_induction_plans_date", "induction_plans", [sa.text("plan_date DESC")])

    # ── induction_plan_items ──────────────────────────────────────────
    op.create_table(
        "induction_plan_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("plan_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("induction_plans.id"), nullable=False),
        sa.Column("trainset_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("trainsets.id"), nullable=False),
        sa.Column("assigned_status", sa.Text(), nullable=False),
        sa.Column("assigned_bay", sa.String(10)),
        sa.Column("priority_rank", sa.Integer()),
        sa.Column("confidence_pct", sa.Numeric(5, 2)),
        sa.Column("ai_reasoning", postgresql.JSONB()),
        sa.Column("constraint_violations", postgresql.JSONB(), server_default="'[]'"),
        sa.Column("is_override", sa.Boolean(), server_default="false"),
        sa.Column("override_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id")),
        sa.Column("override_reason", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
    )
    op.create_index("idx_induction_items_plan", "induction_plan_items", ["plan_id"])
    op.create_index("idx_induction_items_trainset", "induction_plan_items", ["trainset_id"])

    # ── alerts ────────────────────────────────────────────────────────
    op.create_table(
        "alerts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("alert_code", sa.String(50), nullable=False),
        sa.Column("severity", sa.Text(), nullable=False),
        sa.Column("trainset_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("trainsets.id")),
        sa.Column("depot_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("depots.id")),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("is_acknowledged", sa.Boolean(), server_default="false"),
        sa.Column("acknowledged_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id")),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True)),
        sa.Column("auto_resolved", sa.Boolean(), server_default="false"),
        sa.Column("metadata", postgresql.JSONB(), server_default="'{}'"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
    )
    op.create_index("idx_alerts_severity", "alerts", ["severity", sa.text("created_at DESC")])
    op.create_index("idx_alerts_trainset", "alerts", ["trainset_id"])

    # ── ml_predictions ────────────────────────────────────────────────
    op.create_table(
        "ml_predictions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("trainset_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("trainsets.id"), nullable=False),
        sa.Column("model_name", sa.String(100), nullable=False),
        sa.Column("model_version", sa.String(20)),
        sa.Column("prediction_type", sa.String(50), nullable=False),
        sa.Column("predicted_value", sa.Numeric(10, 4)),
        sa.Column("confidence", sa.Numeric(5, 4)),
        sa.Column("feature_importance", postgresql.JSONB()),
        sa.Column("input_features", postgresql.JSONB()),
        sa.Column("prediction_horizon_days", sa.Integer()),
        sa.Column("is_actioned", sa.Boolean(), server_default="false"),
        sa.Column("prediction_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
    )
    op.create_index("idx_ml_predictions_trainset", "ml_predictions", ["trainset_id", sa.text("prediction_at DESC")])

    # ── historical_decisions ──────────────────────────────────────────
    op.create_table(
        "historical_decisions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("plan_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("induction_plans.id")),
        sa.Column("trainset_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("trainsets.id"), nullable=False),
        sa.Column("planned_status", sa.Text()),
        sa.Column("actual_status", sa.Text()),
        sa.Column("outcome", sa.String(50)),
        sa.Column("delay_minutes", sa.Integer()),
        sa.Column("notes", sa.Text()),
        sa.Column("recorded_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
    )

    # ── audit_logs ────────────────────────────────────────────────────
    op.create_table(
        "audit_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id")),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("resource_type", sa.String(50)),
        sa.Column("resource_id", postgresql.UUID(as_uuid=True)),
        sa.Column("old_value", postgresql.JSONB()),
        sa.Column("new_value", postgresql.JSONB()),
        sa.Column("ip_address", postgresql.INET()),
        sa.Column("user_agent", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
    )
    op.create_index("idx_audit_user", "audit_logs", ["user_id", sa.text("created_at DESC")])

    # ── Seed: Muttom Depot ────────────────────────────────────────────
    op.execute("""
        INSERT INTO depots (code, name, location, total_bays, ibl_bays, cleaning_bays)
        VALUES ('MTM', 'Muttom Depot', 'Aluva, Ernakulam, Kerala', 25, 4, 3)
        ON CONFLICT (code) DO NOTHING;
    """)

    # ── Updated_at trigger ────────────────────────────────────────────
    op.execute("""
        CREATE OR REPLACE FUNCTION update_updated_at()
        RETURNS TRIGGER AS $$
        BEGIN NEW.updated_at = NOW(); RETURN NEW; END;
        $$ LANGUAGE plpgsql;
    """)
    for table in ["trainsets", "fitness_certificates", "branding_contracts", "maintenance_jobs"]:
        op.execute(f"""
            CREATE TRIGGER trg_{table}_updated_at
            BEFORE UPDATE ON {table}
            FOR EACH ROW EXECUTE FUNCTION update_updated_at();
        """)


def downgrade() -> None:
    for table in ["audit_logs", "historical_decisions", "ml_predictions", "alerts",
                  "induction_plan_items", "induction_plans", "shunting_operations",
                  "depot_bays", "branding_contracts", "cleaning_slots", "mileage_logs",
                  "job_cards", "maintenance_jobs", "fitness_certificates", "users",
                  "trainsets", "depots"]:
        op.drop_table(table, if_exists=True)
    for enum in ["trainset_status", "fitness_cert_status", "job_card_priority",
                 "job_card_status", "alert_severity", "user_role", "optimization_status"]:
        op.execute(f"DROP TYPE IF EXISTS {enum} CASCADE")
