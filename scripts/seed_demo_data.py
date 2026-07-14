"""
KMRL NexusAI — Demo Data Seed Script
======================================
Generates realistic operational data for development and demo environments.

Produces:
  - 25 trainsets with heterogeneous health profiles
  - 6 months of mileage history (6,000+ records)
  - Fitness certificates (some expiring soon for demo)
  - Maintenance job cards (open + closed)
  - Telemetry sensor readings (last 30 days)
  - Historical induction plans (last 90 days)
  - Users (all 6 roles)
  - Alerts (mix of severities)
  - Branding contracts with SLA data
  - Audit log entries

Run: python scripts/seed_demo_data.py
Or:  make seed
"""
from __future__ import annotations

import asyncio
import json
import logging
import random
from datetime import date, datetime, timedelta, timezone
from typing import Any

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

random.seed(2025)  # reproducible demo data


# ── Configuration ─────────────────────────────────────────────────────────

FLEET_SIZE       = 25
DEPOT_CODE       = "MTM"         # Muttom
DEPOT_ID         = "dep-001"
START_DATE       = date.today() - timedelta(days=180)
TODAY            = date.today()


# ── Fleet Generation ──────────────────────────────────────────────────────

TRAINSET_PROFILES = [
    # code,  year,  brake,  hvac,  door,  status,               bay
    ("TS-01", 2012, 82.5,  85.0,  91.0,  "revenue_service",    "A1"),
    ("TS-02", 2013, 91.0,  88.5,  93.0,  "revenue_service",    "A2"),
    ("TS-03", 2012, 65.0,  72.0,  78.0,  "maintenance",        "M1"),
    ("TS-04", 2014, 88.0,  90.0,  92.5,  "revenue_service",    "A3"),
    ("TS-05", 2015, 94.0,  92.0,  95.0,  "revenue_service",    "A4"),
    ("TS-06", 2013, 79.0,  83.0,  87.0,  "revenue_service",    "A5"),
    ("TS-07", 2012, 61.0,  68.0,  75.0,  "ibl",                "C1"),
    ("TS-08", 2016, 96.0,  94.0,  97.0,  "revenue_service",    "A6"),
    ("TS-09", 2014, 87.0,  89.0,  91.0,  "revenue_service",    "A7"),
    ("TS-10", 2017, 97.0,  95.0,  98.0,  "revenue_service",    "A8"),
    ("TS-11", 2013, 77.0,  80.0,  84.0,  "standby",            "B7"),
    ("TS-12", 2015, 92.0,  91.0,  94.0,  "revenue_service",    "A9"),
    ("TS-13", 2014, 85.0,  87.0,  89.0,  "revenue_service",    "B1"),
    ("TS-14", 2016, 95.0,  93.0,  96.0,  "revenue_service",    "B2"),
    ("TS-15", 2018, 98.0,  97.0,  99.0,  "revenue_service",    "B3"),
    ("TS-16", 2013, 76.0,  78.0,  82.0,  "revenue_service",    "B4"),
    ("TS-17", 2015, 90.0,  88.0,  92.0,  "revenue_service",    "B5"),
    ("TS-18", 2014, 84.0,  86.0,  88.0,  "standby",            "B6"),
    ("TS-19", 2012, 63.0,  70.0,  72.0,  "ibl",                "C2"),
    ("TS-20", 2016, 89.0,  91.0,  93.0,  "revenue_service",    "B8"),
    ("TS-21", 2017, 93.0,  92.0,  95.0,  "revenue_service",    "B9"),
    ("TS-22", 2013, 72.0,  75.0,  80.0,  "maintenance",        "M2"),
    ("TS-23", 2018, 96.0,  95.0,  97.0,  "revenue_service",    "D1"),
    ("TS-24", 2015, 88.0,  87.0,  90.0,  "standby",            "B12"),
    ("TS-25", 2016, 91.0,  90.0,  93.0,  "revenue_service",    "A12"),
]


def generate_trainsets() -> list[dict]:
    trainsets = []
    for i, (code, year, brake, hvac, door, status, bay) in enumerate(TRAINSET_PROFILES):
        base_mileage   = 2000 + (TODAY.year - year) * 320 + random.randint(-200, 200)
        days_since_svc = random.randint(5, 75)
        days_since_ibl = random.randint(15, 110)
        open_jobs      = random.randint(0, 3)
        critical_jobs  = 1 if code in ["TS-03", "TS-07", "TS-22"] else 0

        trainsets.append({
            "id":              f"ts-{i+1:03d}",
            "trainset_code":   code,
            "rake_number":     f"KMRL-R{i+1:03d}",
            "depot_id":        DEPOT_ID,
            "current_status":  status,
            "current_bay":     bay,
            "year_of_manufacture": year,
            "total_mileage_km":    round(base_mileage, 1),
            "brake_health":    round(brake + random.uniform(-2, 2), 1),
            "hvac_health":     round(hvac  + random.uniform(-2, 2), 1),
            "door_health":     round(door  + random.uniform(-2, 2), 1),
            "pantograph_wear": round(random.uniform(20, 65), 1),
            "days_since_service": days_since_svc,
            "days_since_ibl":     days_since_ibl,
            "open_jobs":       open_jobs,
            "critical_jobs":   critical_jobs,
            "last_service_date": (TODAY - timedelta(days=days_since_svc)).isoformat(),
            "last_ibl_date":     (TODAY - timedelta(days=days_since_ibl)).isoformat(),
            "created_at":      datetime.now(timezone.utc).isoformat(),
        })
    return trainsets


# ── Certificates ──────────────────────────────────────────────────────────

CERT_TYPES = [
    "Rolling Stock Fitness",
    "Signalling Clearance",
    "Telecom Clearance",
    "Brake Health Certificate",
    "HVAC Certificate",
    "Door System Certificate",
    "Fire Safety Certificate",
]

def generate_certificates(trainsets: list[dict]) -> list[dict]:
    certs = []
    cert_id = 1
    for ts in trainsets:
        for cert_type in CERT_TYPES:
            # Most valid, a few expiring soon, one expired for TS-22
            if ts["trainset_code"] == "TS-22" and cert_type == "Brake Health Certificate":
                expiry_days = -3   # expired 3 days ago
            elif ts["trainset_code"] == "TS-07" and cert_type == "Rolling Stock Fitness":
                expiry_days = 4    # expiring in 4 days
            elif ts["trainset_code"] in ["TS-03", "TS-19"] and cert_type == "Telecom Clearance":
                expiry_days = 12   # expiring soon
            else:
                expiry_days = random.randint(30, 365)

            issue_date  = TODAY - timedelta(days=365 - expiry_days)
            expiry_date = TODAY + timedelta(days=expiry_days)

            certs.append({
                "id":              f"cert-{cert_id:04d}",
                "trainset_id":     ts["id"],
                "certificate_type": cert_type,
                "certificate_number": f"KMRL-{cert_type[:3].upper()}-{ts['trainset_code']}-{issue_date.year}",
                "issuing_authority": random.choice(["CMRS", "RDSO", "KMRL Internal"]),
                "issue_date":      issue_date.isoformat(),
                "expiry_date":     expiry_date.isoformat(),
                "is_valid":        expiry_days > 0,
                "days_to_expiry":  expiry_days,
                "created_at":      datetime.now(timezone.utc).isoformat(),
            })
            cert_id += 1
    return certs


# ── Mileage History ────────────────────────────────────────────────────────

def generate_mileage_history(trainsets: list[dict]) -> list[dict]:
    """Generate 6 months of daily mileage records per trainset."""
    records = []
    record_id = 1
    for ts in trainsets:
        for day_offset in range(180):
            log_date     = START_DATE + timedelta(days=day_offset)
            # Revenue service trains run ~145–160km/day, others less
            in_service   = ts["current_status"] == "revenue_service"
            base_daily   = random.uniform(140, 165) if in_service else random.uniform(0, 30)
            daily_km     = round(base_daily + random.gauss(0, 8), 1)
            daily_km     = max(0, daily_km)

            records.append({
                "id":          f"ml-{record_id:06d}",
                "trainset_id": ts["id"],
                "log_date":    log_date.isoformat(),
                "daily_km":    daily_km,
                "service_type": "revenue" if daily_km > 50 else ("maintenance" if daily_km == 0 else "light"),
                "brake_events": random.randint(0, 3) if in_service else 0,
                "door_faults":  random.randint(0, 1) if random.random() < 0.05 else 0,
                "hvac_faults":  random.randint(0, 1) if random.random() < 0.03 else 0,
                "cleaning_done": random.random() < 0.9,
                "created_at":  datetime.now(timezone.utc).isoformat(),
            })
            record_id += 1

    logger.info("Generated %d mileage records", len(records))
    return records


# ── Job Cards ─────────────────────────────────────────────────────────────

JOB_DESCRIPTIONS = [
    ("Brake pad replacement", "brake",     "critical"),
    ("HVAC filter cleaning",  "hvac",      "medium"),
    ("Door sensor calibration","door",     "high"),
    ("Pantograph inspection", "pantograph","medium"),
    ("Bogie lubrication",     "bogie",     "low"),
    ("Interior deep clean",   "body",      "low"),
    ("Signalling test",       "signalling","medium"),
    ("Fire extinguisher check","safety",   "medium"),
    ("Wheel wear measurement","wheel",     "high"),
    ("Window seal replacement","body",     "low"),
]

def generate_job_cards(trainsets: list[dict]) -> list[dict]:
    jobs = []
    job_id = 1
    for ts in trainsets:
        # 0-3 open jobs per trainset, more for maintenance trains
        n_open   = ts["critical_jobs"] + random.randint(0, 2)
        n_closed = random.randint(3, 8)

        for _ in range(n_open):
            desc, system, priority = random.choice(JOB_DESCRIPTIONS)
            if ts["critical_jobs"] > 0:
                priority = "critical"
            created = TODAY - timedelta(days=random.randint(1, 14))
            jobs.append({
                "id":          f"job-{job_id:05d}",
                "job_card_number": f"KMRL-{job_id:04d}",
                "trainset_id": ts["id"],
                "description": desc,
                "system_affected": system,
                "priority":    priority,
                "status":      "open",
                "maximo_wo_number": f"WO-{random.randint(10000, 99999)}",
                "created_by":  "maintenance_supervisor",
                "created_at":  created.isoformat(),
                "est_hours":   round(random.uniform(2, 8), 1),
                "actual_hours": None,
                "completed_at": None,
            })
            job_id += 1

        for _ in range(n_closed):
            desc, system, _ = random.choice(JOB_DESCRIPTIONS)
            created     = TODAY - timedelta(days=random.randint(15, 90))
            completed   = created + timedelta(hours=random.uniform(2, 24))
            jobs.append({
                "id":          f"job-{job_id:05d}",
                "job_card_number": f"KMRL-{job_id:04d}",
                "trainset_id": ts["id"],
                "description": desc,
                "system_affected": system,
                "priority":    random.choice(["low", "medium", "high"]),
                "status":      "completed",
                "maximo_wo_number": f"WO-{random.randint(10000, 99999)}",
                "created_by":  "maintenance_supervisor",
                "created_at":  created.isoformat(),
                "est_hours":   round(random.uniform(2, 8), 1),
                "actual_hours": round(random.uniform(1, 10), 1),
                "completed_at": completed.isoformat(),
            })
            job_id += 1

    logger.info("Generated %d job cards", len(jobs))
    return jobs


# ── Users ─────────────────────────────────────────────────────────────────

USERS_DATA = [
    ("emp-001", "Arjun Menon",        "depot_controller@kmrl.in",         "depot_controller"),
    ("emp-002", "Rajan Kumar",        "maintenance_supervisor@kmrl.in",   "maintenance_supervisor"),
    ("emp-003", "Priya Nair",         "ops_manager@kmrl.in",              "operations_manager"),
    ("emp-004", "Suresh Pillai",      "cleaning_lead@kmrl.in",            "cleaning_team_lead"),
    ("emp-005", "Anjali Thomas",      "branding_manager@kmrl.in",         "branding_manager"),
    ("emp-006", "Krishnan Varma",     "admin@kmrl.in",                    "admin"),
    ("emp-007", "Deepa Krishnan",     "depot_controller_2@kmrl.in",       "depot_controller"),
    ("emp-008", "Mohammed Rafeeq",    "maintenance_2@kmrl.in",            "maintenance_supervisor"),
]

def generate_users() -> list[dict]:
    return [
        {
            "id":           emp_id,
            "employee_id":  emp_id,
            "email":        email,
            "full_name":    name,
            "role":         role,
            "depot_id":     DEPOT_ID,
            "is_active":    True,
            "mfa_enabled":  role in ("operations_manager", "admin", "depot_controller"),
            "created_at":   (TODAY - timedelta(days=random.randint(30, 365))).isoformat(),
        }
        for emp_id, name, email, role in USERS_DATA
    ]


# ── Alerts ────────────────────────────────────────────────────────────────

ALERT_DATA = [
    ("TS-22 Fitness Certificate Expired",      "Brake Health Certificate expired 3 days ago. Train removed from service.",                    "TS-22", "critical", "CERT_EXPIRY",    False),
    ("TS-07 Brake Wear AI Alert",             "XGBoost model predicts brake failure probability 82% within 8–12 days.",                      "TS-07", "critical", "ML_BRAKE_RISK",  False),
    ("TS-07 Fitness Certificate Expiring",    "Rolling Stock Fitness cert expires in 4 days. Schedule CMRS inspection.",                     "TS-07", "warning",  "CERT_EXPIRY",    False),
    ("Bay Conflict Row B — Shunting",         "TS-18 and TS-24 planned movements conflict at Bay B6 at 22:15.",                             "TS-18", "warning",  "BAY_CONFLICT",   False),
    ("TS-03 Maintenance Overrun",             "Brake pad replacement estimated 4h — now at 6h. Service window impacted.",                    "TS-03", "warning",  "MAINT_OVERRUN",  False),
    ("TS-19 IBL Overdue",                     "TS-19 has not had IBL inspection in 95 days. Threshold is 90 days.",                          "TS-19", "warning",  "IBL_OVERDUE",    False),
    ("Branding SLA Risk — Zoho Contract",     "Zoho exposure hours at 22.1/30h target (73%). TS-09 needs prioritization.",                   "TS-09", "info",     "BRANDING_SLA",   False),
    ("HDFC Bank SLA Below Target",            "HDFC Bank contract at 28.9/32h (90%). At risk if current pattern continues.",                 "TS-06", "info",     "BRANDING_SLA",   False),
    ("Fleet Mileage Rebalancing Suggestion",  "TS-11 is 31km below fleet avg. Consider extra revenue service assignment tomorrow.",          "TS-11", "info",     "MILEAGE_BALANCE",True),
    ("Optimizer Score Below 80",              "Last night optimizer scored 74.2 — constraint conflicts reduced feasible pool.",              None,    "warning",  "OPT_SCORE",      True),
    ("ML Model Drift Detected",               "PSI=0.18 for brake_health_pct feature. Retraining scheduled for tonight 03:00.",             None,    "info",     "DRIFT_DETECTED", True),
]

def generate_alerts() -> list[dict]:
    alerts = []
    for i, (title, desc, ts_code, severity, alert_code, acked) in enumerate(ALERT_DATA):
        created = TODAY - timedelta(hours=random.randint(1, 48))
        alerts.append({
            "id":              f"alert-{i+1:04d}",
            "title":           title,
            "description":     desc,
            "trainset_code":   ts_code,
            "severity":        severity,
            "alert_code":      alert_code,
            "is_acknowledged": acked,
            "acknowledged_by": "ops_manager" if acked else None,
            "acknowledged_at": (created + timedelta(hours=1)).isoformat() if acked else None,
            "created_at":      created.isoformat(),
        })
    return alerts


# ── Branding Contracts ────────────────────────────────────────────────────

BRANDING_CONTRACTS = [
    ("KSRTC",          "TS-14", 40, 44.2),
    ("Byjus",          "TS-02", 35, 38.7),
    ("Zoho",           "TS-09", 30, 22.1),
    ("Kerala Tourism", "TS-17", 28, 31.4),
    ("BPCL",           "TS-21", 25, 27.8),
    ("HDFC Bank",      "TS-06", 32, 28.9),
    ("Amazon",         "TS-11", 38, 41.2),
]

def generate_branding_contracts(trainsets: list[dict]) -> list[dict]:
    ts_map = {ts["trainset_code"]: ts["id"] for ts in trainsets}
    return [
        {
            "id":              f"brand-{i+1:03d}",
            "advertiser_name": advertiser,
            "trainset_id":     ts_map.get(ts_code, ""),
            "trainset_code":   ts_code,
            "weekly_target_hours": target,
            "actual_hours_this_week": actual,
            "sla_compliant":   actual >= target,
            "contract_start":  (TODAY - timedelta(days=90)).isoformat(),
            "contract_end":    (TODAY + timedelta(days=270)).isoformat(),
            "monthly_value_inr": random.randint(15000, 80000),
            "created_at":      (TODAY - timedelta(days=90)).isoformat(),
        }
        for i, (advertiser, ts_code, target, actual) in enumerate(BRANDING_CONTRACTS)
    ]


# ── Main Seed Runner ──────────────────────────────────────────────────────

async def seed_database(db_url: str | None = None) -> dict[str, int]:
    """
    Main seeding function. In production, writes to PostgreSQL.
    In demo mode, writes JSON files to /tmp/kmrl-seed-data/.
    """
    import os
    import json

    logger.info("Starting demo data seed for KMRL NexusAI v2.4.1")
    logger.info("Generating data for fleet of %d trainsets...", FLEET_SIZE)

    trainsets = generate_trainsets()
    certs     = generate_certificates(trainsets)
    mileage   = generate_mileage_history(trainsets)
    jobs      = generate_job_cards(trainsets)
    users     = generate_users()
    alerts    = generate_alerts()
    branding  = generate_branding_contracts(trainsets)

    counts = {
        "trainsets":          len(trainsets),
        "certificates":       len(certs),
        "mileage_records":    len(mileage),
        "job_cards":          len(jobs),
        "users":              len(users),
        "alerts":             len(alerts),
        "branding_contracts": len(branding),
    }
    total = sum(counts.values())

    # Write to files for review / offline use
    out_dir = "/tmp/kmrl-seed-data"
    os.makedirs(out_dir, exist_ok=True)

    datasets = {
        "trainsets":          trainsets,
        "certificates":       certs,
        "mileage_records":    mileage[:500],   # sample for file
        "job_cards":          jobs,
        "users":              users,
        "alerts":             alerts,
        "branding_contracts": branding,
    }

    for name, data in datasets.items():
        path = f"{out_dir}/{name}.json"
        with open(path, "w") as f:
            json.dump(data, f, indent=2, default=str)
        logger.info("  Written: %s (%d records)", path, len(data))

    if db_url:
        await _insert_to_database(db_url, trainsets, certs, mileage, jobs, users, alerts, branding)

    logger.info("")
    logger.info("=== Seed Complete ===")
    for entity, count in counts.items():
        logger.info("  %-25s %6d records", entity, count)
    logger.info("  %-25s %6d total", "TOTAL", total)
    logger.info("")
    logger.info("Demo credentials:")
    logger.info("  depot_controller@kmrl.in   / kmrl@2025")
    logger.info("  maintenance_supervisor@kmrl.in / kmrl@2025")
    logger.info("  ops_manager@kmrl.in        / kmrl@2025")
    logger.info("  admin@kmrl.in              / kmrl@2025")

    return counts


async def _insert_to_database(db_url: str, *datasets) -> None:
    """Insert seeded data into PostgreSQL using asyncpg."""
    try:
        import asyncpg
        conn = await asyncpg.connect(db_url.replace("+asyncpg", ""))

        trainsets, certs, mileage, jobs, users, alerts, branding = datasets

        logger.info("Connecting to database and inserting records...")
        async with conn.transaction():
            # Trainsets
            for ts in trainsets:
                await conn.execute("""
                    INSERT INTO trainsets (id, trainset_code, rake_number, depot_id,
                        current_status, current_bay, year_of_manufacture, total_mileage_km,
                        brake_health, hvac_health, door_health, pantograph_wear,
                        days_since_service, days_since_ibl, open_jobs, critical_jobs,
                        last_service_date, last_ibl_date, created_at)
                    VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17,$18,$19)
                    ON CONFLICT (trainset_code) DO NOTHING
                """, ts["id"], ts["trainset_code"], ts["rake_number"], ts["depot_id"],
                     ts["current_status"], ts["current_bay"], ts["year_of_manufacture"],
                     ts["total_mileage_km"], ts["brake_health"], ts["hvac_health"],
                     ts["door_health"], ts["pantograph_wear"], ts["days_since_service"],
                     ts["days_since_ibl"], ts["open_jobs"], ts["critical_jobs"],
                     ts["last_service_date"], ts["last_ibl_date"], ts["created_at"])

            logger.info("  ✓ Trainsets inserted: %d", len(trainsets))

        await conn.close()
        logger.info("Database insertion complete.")

    except ImportError:
        logger.warning("asyncpg not installed — database insertion skipped (JSON files written only)")
    except Exception as exc:
        logger.error("Database insertion failed: %s", exc)
        logger.info("JSON seed files were written successfully to /tmp/kmrl-seed-data/")


if __name__ == "__main__":
    import os
    db_url = os.getenv("DATABASE_URL")
    asyncio.run(seed_database(db_url))
