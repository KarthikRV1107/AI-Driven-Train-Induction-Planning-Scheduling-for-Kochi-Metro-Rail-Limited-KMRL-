"""
KMRL NexusAI — SQLAlchemy ORM Models
"""
from __future__ import annotations
import enum
from datetime import date, datetime
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean, Column, Date, DateTime, Enum, Float, ForeignKey,
    Integer, String, Text, UniqueConstraint, func
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


# ── Enums ─────────────────────────────────────────────────────────────────

class TrainsetStatus(str, enum.Enum):
    REVENUE_SERVICE = "revenue_service"
    STANDBY = "standby"
    IBL = "ibl"
    MAINTENANCE = "maintenance"
    CLEANING = "cleaning"
    STABLING = "stabling"
    OUT_OF_SERVICE = "out_of_service"


class FitnessCertStatus(str, enum.Enum):
    VALID = "valid"
    EXPIRING_SOON = "expiring_soon"
    EXPIRED = "expired"
    PENDING_RENEWAL = "pending_renewal"


class JobPriority(str, enum.Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class JobStatus(str, enum.Enum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    DEFERRED = "deferred"


class AlertSeverity(str, enum.Enum):
    CRITICAL = "critical"
    WARNING = "warning"
    INFO = "info"


class UserRole(str, enum.Enum):
    ADMIN = "admin"
    DEPOT_CONTROLLER = "depot_controller"
    MAINTENANCE_SUPERVISOR = "maintenance_supervisor"
    OPERATIONS_MANAGER = "operations_manager"
    CLEANING_TEAM_LEAD = "cleaning_team_lead"
    BRANDING_MANAGER = "branding_manager"


class OptimizationStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


# ── Models ────────────────────────────────────────────────────────────────

class Depot(Base):
    __tablename__ = "depots"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    code: Mapped[str] = mapped_column(String(10), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    location: Mapped[Optional[str]] = mapped_column(String(200))
    total_bays: Mapped[int] = mapped_column(Integer, default=25)
    ibl_bays: Mapped[int] = mapped_column(Integer, default=4)
    cleaning_bays: Mapped[int] = mapped_column(Integer, default=3)
    layout_json: Mapped[Optional[dict]] = mapped_column(JSONB)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    trainsets: Mapped[list["Trainset"]] = relationship(back_populates="depot")
    bays: Mapped[list["DepotBay"]] = relationship(back_populates="depot")


class Trainset(Base):
    __tablename__ = "trainsets"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    trainset_code: Mapped[str] = mapped_column(String(10), unique=True, nullable=False)
    rake_number: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    manufacturer: Mapped[Optional[str]] = mapped_column(String(100))
    year_of_manufacture: Mapped[Optional[int]] = mapped_column(Integer)
    car_count: Mapped[int] = mapped_column(Integer, default=4)
    depot_id: Mapped[Optional[UUID]] = mapped_column(PGUUID(as_uuid=True), ForeignKey("depots.id"))
    current_status: Mapped[TrainsetStatus] = mapped_column(
        Enum(TrainsetStatus), default=TrainsetStatus.STABLING
    )
    current_bay: Mapped[Optional[str]] = mapped_column(String(10))
    total_mileage_km: Mapped[float] = mapped_column(Float, default=0.0)
    last_service_date: Mapped[Optional[date]] = mapped_column(Date)
    next_service_due: Mapped[Optional[date]] = mapped_column(Date)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    metadata_: Mapped[dict] = mapped_column("metadata", JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    depot: Mapped[Optional[Depot]] = relationship(back_populates="trainsets")
    fitness_certificates: Mapped[list["FitnessCertificate"]] = relationship(back_populates="trainset", cascade="all, delete-orphan")
    maintenance_jobs: Mapped[list["MaintenanceJob"]] = relationship(back_populates="trainset")
    mileage_logs: Mapped[list["MileageLog"]] = relationship(back_populates="trainset")
    cleaning_slots: Mapped[list["CleaningSlot"]] = relationship(back_populates="trainset")
    branding_contracts: Mapped[list["BrandingContract"]] = relationship(back_populates="trainset")
    ml_predictions: Mapped[list["MLPrediction"]] = relationship(back_populates="trainset")


class User(Base):
    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    employee_id: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(100), nullable=False)
    role: Mapped[UserRole] = mapped_column(Enum(UserRole), nullable=False)
    depot_id: Mapped[Optional[UUID]] = mapped_column(PGUUID(as_uuid=True), ForeignKey("depots.id"))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_login: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class FitnessCertificate(Base):
    __tablename__ = "fitness_certificates"
    __table_args__ = (UniqueConstraint("trainset_id", "cert_type", "expiry_date"),)

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    trainset_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("trainsets.id", ondelete="CASCADE"))
    cert_type: Mapped[str] = mapped_column(String(50), nullable=False)
    cert_number: Mapped[Optional[str]] = mapped_column(String(100))
    issuing_authority: Mapped[Optional[str]] = mapped_column(String(100))
    issued_date: Mapped[date] = mapped_column(Date, nullable=False)
    expiry_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[FitnessCertStatus] = mapped_column(Enum(FitnessCertStatus), default=FitnessCertStatus.VALID)
    document_url: Mapped[Optional[str]] = mapped_column(String(500))
    notes: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    trainset: Mapped[Trainset] = relationship(back_populates="fitness_certificates")


class MaintenanceJob(Base):
    __tablename__ = "maintenance_jobs"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    trainset_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("trainsets.id"))
    job_type: Mapped[str] = mapped_column(String(50), nullable=False)
    system_affected: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    priority: Mapped[JobPriority] = mapped_column(Enum(JobPriority), default=JobPriority.MEDIUM)
    status: Mapped[JobStatus] = mapped_column(Enum(JobStatus), default=JobStatus.OPEN)
    estimated_hours: Mapped[Optional[float]] = mapped_column(Float)
    actual_hours: Mapped[Optional[float]] = mapped_column(Float)
    assigned_to: Mapped[Optional[UUID]] = mapped_column(PGUUID(as_uuid=True), ForeignKey("users.id"))
    depot_id: Mapped[Optional[UUID]] = mapped_column(PGUUID(as_uuid=True), ForeignKey("depots.id"))
    scheduled_start: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    scheduled_end: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    actual_start: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    actual_end: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    ibm_maximo_ref: Mapped[Optional[str]] = mapped_column(String(50))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    trainset: Mapped[Trainset] = relationship(back_populates="maintenance_jobs")
    job_cards: Mapped[list["JobCard"]] = relationship(back_populates="job", cascade="all, delete-orphan")


class JobCard(Base):
    __tablename__ = "job_cards"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    job_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("maintenance_jobs.id"))
    card_number: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    is_critical: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[JobStatus] = mapped_column(Enum(JobStatus), default=JobStatus.OPEN)
    completed_by: Mapped[Optional[UUID]] = mapped_column(PGUUID(as_uuid=True), ForeignKey("users.id"))
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    sign_off_notes: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    job: Mapped[MaintenanceJob] = relationship(back_populates="job_cards")


class MileageLog(Base):
    __tablename__ = "mileage_logs"
    __table_args__ = (UniqueConstraint("trainset_id", "log_date"),)

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    trainset_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("trainsets.id"))
    log_date: Mapped[date] = mapped_column(Date, nullable=False)
    service_km: Mapped[float] = mapped_column(Float, default=0.0)
    test_km: Mapped[float] = mapped_column(Float, default=0.0)
    cumulative_km: Mapped[Optional[float]] = mapped_column(Float)
    route_code: Mapped[Optional[str]] = mapped_column(String(20))
    trips_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    trainset: Mapped[Trainset] = relationship(back_populates="mileage_logs")


class CleaningSlot(Base):
    __tablename__ = "cleaning_slots"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    trainset_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("trainsets.id"))
    cleaning_type: Mapped[str] = mapped_column(String(30), nullable=False)
    bay_id: Mapped[Optional[str]] = mapped_column(String(10))
    depot_id: Mapped[Optional[UUID]] = mapped_column(PGUUID(as_uuid=True), ForeignKey("depots.id"))
    scheduled_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    scheduled_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    actual_start: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    actual_end: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    completed: Mapped[bool] = mapped_column(Boolean, default=False)
    assigned_team: Mapped[Optional[UUID]] = mapped_column(PGUUID(as_uuid=True), ForeignKey("users.id"))
    notes: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    trainset: Mapped[Trainset] = relationship(back_populates="cleaning_slots")


class BrandingContract(Base):
    __tablename__ = "branding_contracts"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    trainset_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("trainsets.id"))
    advertiser_name: Mapped[str] = mapped_column(String(100), nullable=False)
    contract_ref: Mapped[Optional[str]] = mapped_column(String(50), unique=True)
    branding_type: Mapped[Optional[str]] = mapped_column(String(50))
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    min_exposure_hrs_per_week: Mapped[float] = mapped_column(Float, default=0.0)
    actual_exposure_hrs: Mapped[float] = mapped_column(Float, default=0.0)
    priority_score: Mapped[int] = mapped_column(Integer, default=50)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    trainset: Mapped[Trainset] = relationship(back_populates="branding_contracts")


class DepotBay(Base):
    __tablename__ = "depot_bays"
    __table_args__ = (UniqueConstraint("depot_id", "bay_code"),)

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    depot_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("depots.id"))
    bay_code: Mapped[str] = mapped_column(String(10), nullable=False)
    bay_type: Mapped[str] = mapped_column(String(20), nullable=False)
    row_label: Mapped[Optional[str]] = mapped_column(String(5))
    position_x: Mapped[Optional[float]] = mapped_column(Float)
    position_y: Mapped[Optional[float]] = mapped_column(Float)
    is_occupied: Mapped[bool] = mapped_column(Boolean, default=False)
    occupied_by: Mapped[Optional[UUID]] = mapped_column(PGUUID(as_uuid=True), ForeignKey("trainsets.id"))
    is_operational: Mapped[bool] = mapped_column(Boolean, default=True)

    depot: Mapped[Depot] = relationship(back_populates="bays")


class InductionPlan(Base):
    __tablename__ = "induction_plans"
    __table_args__ = (UniqueConstraint("plan_date", "depot_id"),)

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    plan_date: Mapped[date] = mapped_column(Date, nullable=False)
    depot_id: Mapped[Optional[UUID]] = mapped_column(PGUUID(as_uuid=True), ForeignKey("depots.id"))
    created_by: Mapped[Optional[UUID]] = mapped_column(PGUUID(as_uuid=True), ForeignKey("users.id"))
    optimization_status: Mapped[OptimizationStatus] = mapped_column(Enum(OptimizationStatus), default=OptimizationStatus.PENDING)
    optimizer_version: Mapped[Optional[str]] = mapped_column(String(20))
    score: Mapped[Optional[float]] = mapped_column(Float)
    revenue_count: Mapped[Optional[int]] = mapped_column(Integer)
    standby_count: Mapped[Optional[int]] = mapped_column(Integer)
    ibl_count: Mapped[Optional[int]] = mapped_column(Integer)
    maintenance_count: Mapped[Optional[int]] = mapped_column(Integer)
    plan_json: Mapped[dict] = mapped_column(JSONB, nullable=False)
    override_notes: Mapped[Optional[str]] = mapped_column(Text)
    approved_by: Mapped[Optional[UUID]] = mapped_column(PGUUID(as_uuid=True), ForeignKey("users.id"))
    approved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    items: Mapped[list["InductionPlanItem"]] = relationship(back_populates="plan", cascade="all, delete-orphan")


class InductionPlanItem(Base):
    __tablename__ = "induction_plan_items"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    plan_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("induction_plans.id"))
    trainset_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("trainsets.id"))
    assigned_status: Mapped[TrainsetStatus] = mapped_column(Enum(TrainsetStatus), nullable=False)
    assigned_bay: Mapped[Optional[str]] = mapped_column(String(10))
    priority_rank: Mapped[Optional[int]] = mapped_column(Integer)
    confidence_pct: Mapped[Optional[float]] = mapped_column(Float)
    ai_reasoning: Mapped[Optional[dict]] = mapped_column(JSONB)
    constraint_violations: Mapped[dict] = mapped_column(JSONB, default=list)
    is_override: Mapped[bool] = mapped_column(Boolean, default=False)
    override_by: Mapped[Optional[UUID]] = mapped_column(PGUUID(as_uuid=True), ForeignKey("users.id"))
    override_reason: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    plan: Mapped[InductionPlan] = relationship(back_populates="items")


class Alert(Base):
    __tablename__ = "alerts"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    alert_code: Mapped[str] = mapped_column(String(50), nullable=False)
    severity: Mapped[AlertSeverity] = mapped_column(Enum(AlertSeverity), nullable=False)
    trainset_id: Mapped[Optional[UUID]] = mapped_column(PGUUID(as_uuid=True), ForeignKey("trainsets.id"))
    depot_id: Mapped[Optional[UUID]] = mapped_column(PGUUID(as_uuid=True), ForeignKey("depots.id"))
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    is_acknowledged: Mapped[bool] = mapped_column(Boolean, default=False)
    acknowledged_by: Mapped[Optional[UUID]] = mapped_column(PGUUID(as_uuid=True), ForeignKey("users.id"))
    acknowledged_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    auto_resolved: Mapped[bool] = mapped_column(Boolean, default=False)
    metadata_: Mapped[dict] = mapped_column("metadata", JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class MLPrediction(Base):
    __tablename__ = "ml_predictions"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    trainset_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("trainsets.id"))
    model_name: Mapped[str] = mapped_column(String(100), nullable=False)
    model_version: Mapped[Optional[str]] = mapped_column(String(20))
    prediction_type: Mapped[str] = mapped_column(String(50), nullable=False)
    predicted_value: Mapped[Optional[float]] = mapped_column(Float)
    confidence: Mapped[Optional[float]] = mapped_column(Float)
    feature_importance: Mapped[Optional[dict]] = mapped_column(JSONB)
    input_features: Mapped[Optional[dict]] = mapped_column(JSONB)
    prediction_horizon_days: Mapped[Optional[int]] = mapped_column(Integer)
    is_actioned: Mapped[bool] = mapped_column(Boolean, default=False)
    prediction_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    trainset: Mapped[Trainset] = relationship(back_populates="ml_predictions")
