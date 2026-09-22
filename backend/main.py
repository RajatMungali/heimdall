from dotenv import load_dotenv
load_dotenv("backend/.env", override=True)
# Reload trigger: 2026-07-25 14:13

from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware

from pydantic import BaseModel
from sqlalchemy.orm import Session
import logging
logging.getLogger("uvicorn.access").disabled = True

from datetime import datetime, timezone
from contextlib import asynccontextmanager
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from backend.utils.logger import logger

from backend.config import settings
from backend.database import engine, Base, get_db
from backend import models
from backend.pipeline.dns_audit import audit_domain_email_infrastructure
from backend.pipeline.filter_funnel import trim_html_for_llm, passes_keyword_gate
from backend.validation.quote_validator import validate_quote
from backend.pipeline.scorer import process_hybrid_lead_scoring
from backend.routers import pipeline, leads
from backend.kafka_service import consume_enrichment_events


# ======================================================================
# Database initialization — creates all ORM tables & auto-migrates columns
# ======================================================================
# ======================================================================
# Database initialization — creates all ORM tables & auto-migrates columns
# ======================================================================
try:
    from sqlalchemy import text

    # Create any tables that do not already exist.
    Base.metadata.create_all(bind=engine)

    with engine.connect() as conn:
        if not settings.DATABASE_URL.startswith("sqlite"):
            conn.execute(text("CREATE SCHEMA IF NOT EXISTS heimdall;"))

            # Existing migrations
            conn.execute(text(
                "ALTER TABLE lead_snapshots "
                "ADD COLUMN IF NOT EXISTS company_segment VARCHAR(255) "
                "DEFAULT 'Growth Scale-up';"
            ))
            conn.execute(text(
                "ALTER TABLE lead_snapshots "
                "ADD COLUMN IF NOT EXISTS why_now TEXT "
                "DEFAULT 'Verified public buying intent triggers detected.';"
            ))
            conn.execute(text(
                "ALTER TABLE lead_snapshots "
                "ADD COLUMN IF NOT EXISTS signal_tags JSONB "
                "DEFAULT '[]'::jsonb;"
            ))
            conn.execute(text(
                "ALTER TABLE lead_snapshots "
                "ADD COLUMN IF NOT EXISTS annual_revenue TEXT;"
            ))
            conn.execute(text(
                "ALTER TABLE social_posts "
                "ADD COLUMN IF NOT EXISTS summary TEXT;"
            ))
            conn.execute(text(
                "ALTER TABLE ats_job_snapshots "
                "ADD COLUMN IF NOT EXISTS date_posted VARCHAR(255);"
            ))

            # Track Jobs migrations
            conn.execute(text(
                "ALTER TABLE ats_job_snapshots "
                "ADD COLUMN IF NOT EXISTS original_post_date VARCHAR(255);"
            ))
            conn.execute(text(
                "ALTER TABLE ats_job_snapshots "
                "ADD COLUMN IF NOT EXISTS first_discovered_at TIMESTAMP;"
            ))
            conn.execute(text(
                "ALTER TABLE ats_job_snapshots "
                "ADD COLUMN IF NOT EXISTS company_domain VARCHAR(255);"
            ))
            conn.execute(text(
                "ALTER TABLE ats_job_snapshots "
                "ADD COLUMN IF NOT EXISTS source VARCHAR(255);"
            ))
            conn.execute(text(
                "ALTER TABLE ats_job_snapshots "
                "ADD COLUMN IF NOT EXISTS status VARCHAR(50) DEFAULT 'held';"
            ))
            conn.execute(text(
                "ALTER TABLE ats_job_snapshots "
                "ADD COLUMN IF NOT EXISTS surfaced_at TIMESTAMP;"
            ))
            conn.execute(text(
                "ALTER TABLE ats_job_snapshots "
                "ADD COLUMN IF NOT EXISTS last_seen_at TIMESTAMP;"
            ))
            conn.execute(text(
                "ALTER TABLE ats_job_snapshots "
                "ADD COLUMN IF NOT EXISTS last_rescraped_at TIMESTAMP;"
            ))
            conn.execute(text(
                "ALTER TABLE ats_job_snapshots "
                "ADD COLUMN IF NOT EXISTS monitor_until TIMESTAMP;"
            ))
            conn.execute(text(
                "ALTER TABLE ats_job_snapshots "
                "ADD COLUMN IF NOT EXISTS description_hash VARCHAR(255);"
            ))
            conn.execute(text(
                "ALTER TABLE ats_job_snapshots "
                "ADD COLUMN IF NOT EXISTS previous_description_hash VARCHAR(255);"
            ))
            conn.execute(text(
                "ALTER TABLE ats_job_snapshots "
                "ADD COLUMN IF NOT EXISTS jd_changed BOOLEAN DEFAULT FALSE;"
            ))
            conn.execute(text(
                "ALTER TABLE ats_job_snapshots "
                "ADD COLUMN IF NOT EXISTS reposted BOOLEAN DEFAULT FALSE;"
            ))
            conn.execute(text(
                "ALTER TABLE ats_job_snapshots "
                "ADD COLUMN IF NOT EXISTS repost_of_job_id VARCHAR(255);"
            ))
            conn.execute(text(
                "ALTER TABLE ats_job_snapshots "
                "ADD COLUMN IF NOT EXISTS job_identity_key VARCHAR(512);"
            ))

        else:
            # Existing SQLite migrations
            try:
                conn.execute(text(
                    "ALTER TABLE lead_snapshots "
                    "ADD COLUMN company_segment TEXT DEFAULT 'Growth Scale-up';"
                ))
            except Exception:
                pass

            try:
                conn.execute(text(
                    "ALTER TABLE lead_snapshots "
                    "ADD COLUMN why_now TEXT "
                    "DEFAULT 'Verified public buying intent triggers detected.';"
                ))
            except Exception:
                pass

            try:
                conn.execute(text(
                    "ALTER TABLE lead_snapshots "
                    "ADD COLUMN signal_tags JSON DEFAULT '[]';"
                ))
            except Exception:
                pass

            try:
                conn.execute(text(
                    "ALTER TABLE social_posts ADD COLUMN summary TEXT;"
                ))
            except Exception:
                pass

            try:
                conn.execute(text(
                    "ALTER TABLE ats_job_snapshots ADD COLUMN date_posted TEXT;"
                ))
            except Exception:
                pass

            try:
                conn.execute(text(
                    "ALTER TABLE lead_snapshots ADD COLUMN annual_revenue TEXT;"
                ))
            except Exception:
                pass

            # Track Jobs migrations
            track_jobs_columns = [
                ("original_post_date", "TEXT"),
                ("first_discovered_at", "DATETIME"),
                ("company_domain", "TEXT"),
                ("source", "TEXT"),
                ("status", "TEXT DEFAULT 'held'"),
                ("surfaced_at", "DATETIME"),
                ("last_seen_at", "DATETIME"),
                ("last_rescraped_at", "DATETIME"),
                ("monitor_until", "DATETIME"),
                ("description_hash", "TEXT"),
                ("previous_description_hash", "TEXT"),
                ("jd_changed", "BOOLEAN DEFAULT 0"),
                ("reposted", "BOOLEAN DEFAULT 0"),
                ("repost_of_job_id", "TEXT"),
                ("job_identity_key", "TEXT"),
            ]

            for column_name, column_definition in track_jobs_columns:
                try:
                    conn.execute(text(
                        f"ALTER TABLE ats_job_snapshots "
                        f"ADD COLUMN {column_name} {column_definition};"
                    ))
                except Exception:
                    # Column already exists.
                    pass

        conn.commit()

except Exception as e:
    logger.error(f"Database initialization warning: {e}")


# ======================================================================
# Background scheduler — managed via FastAPI lifespan (audit fix)
# Prevents duplicate threads on uvicorn --reload
# ======================================================================
scheduler = BackgroundScheduler(timezone='UTC')

def backfill_missing_timestamps():
    """Backfills missing last_updated timestamps in existing DB snapshots."""
    from backend.database import SessionLocal
    from backend.models import LeadSnapshot
    db = SessionLocal()
    try:
        leads = db.query(LeadSnapshot).all()
        now_dt = datetime.now(timezone.utc)
        updated_count = 0
        for lead in leads:
            if not lead.last_updated:
                lead.last_updated = now_dt
                updated_count += 1
            if lead.full_payload and isinstance(lead.full_payload, dict):
                if not lead.full_payload.get("last_updated"):
                    payload = dict(lead.full_payload)
                    payload["last_updated"] = (lead.last_updated or now_dt).isoformat()
                    lead.full_payload = payload
                    updated_count += 1
        if updated_count > 0:
            db.commit()
    except Exception as err:
        logger.error(f"Backfill timestamp warning: {err}")
    finally:
        db.close()

from apscheduler.triggers.cron import CronTrigger
import asyncio

def run_async_midnight_cron():
    asyncio.run(trigger_midnight_cron_run(daily_quota=20))

from backend.pipeline.streaming_orchestrator import trigger_midnight_cron_run


def run_weekly_track_jobs_monitoring():
    from backend.pipeline.job_monitor import run_weekly_monitoring
    run_weekly_monitoring()


def run_daily_track_jobs():
    from backend.database import SessionLocal
    from backend.models import TrackJobsRun
    from backend.pipeline.job_pipeline import fetch_day1_jobs, fetch_day2_jobs

    db = SessionLocal()
    try:
        has_run_before = db.query(TrackJobsRun).filter(TrackJobsRun.status == "success").first() is not None
    finally:
        db.close()

    if has_run_before:
        asyncio.run(fetch_day2_jobs())
    else:
        asyncio.run(fetch_day1_jobs())

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Backfill timestamps for existing DB snapshots
    backfill_missing_timestamps()
    # Start Kafka consumer for enrichment events
    asyncio.create_task(consume_enrichment_events())
    # Daily 2:00 AM Cron Execution
    scheduler.add_job(
        func=run_async_midnight_cron,
        trigger=CronTrigger(hour=2, minute=0, timezone='UTC')
    )
    scheduler.add_job(
        func=run_weekly_track_jobs_monitoring,
        trigger=CronTrigger(day_of_week='mon', hour=3, minute=0, timezone='UTC')
    )
    scheduler.add_job(
        func=run_daily_track_jobs,
        trigger=CronTrigger(hour=6, minute=0, timezone='UTC')
    )
    scheduler.start()
    yield
    scheduler.shutdown(wait=False)



# ======================================================================
# Application instance
# ======================================================================
app = FastAPI(
    title="Heimdall Intel Platform API",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_origin_regex=r"https://.*\.vercel\.app",
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ======================================================================
# Mount routers from Stage 4 & 5
# ======================================================================
app.include_router(pipeline.router)
app.include_router(leads.router)

from backend.routers import settings, social_posts, ats_jobs, webhooks, fullenrich
app.include_router(settings.router)
app.include_router(social_posts.router)
app.include_router(ats_jobs.router)
app.include_router(webhooks.router)
app.include_router(fullenrich.router)


# ======================================================================
# Direct routes (cumulative from Stages 1-3)
# ======================================================================

@app.get("/")
@app.head("/")
@app.get("/api/health")
@app.head("/api/health")
def health_check():
    return {
        "status": "healthy",
        "stage": 5,
        "scheduler_status": "active_running"
    }


@app.get("/api/audit/dns")
def execute_dns_audit(domain: str):
    """Direct programmatic debugging route for infrastructure audits. (Stage 1)"""
    return audit_domain_email_infrastructure(domain)


class FilterRequest(BaseModel):
    raw_html: str


class ValidationPayload(BaseModel):
    quote: str
    source_text: str


@app.post("/api/filter/simulate")
def simulate_filter_funnel(payload: FilterRequest):
    """Programmatic staging endpoint evaluating structural data reduction. (Stage 2)"""
    cleaned_text = trim_html_for_llm(payload.raw_html)
    matches_gate = passes_keyword_gate(cleaned_text)

    return {
        "character_count_before": len(payload.raw_html),
        "character_count_after": len(cleaned_text),
        "passes_keyword_gate": matches_gate,
        "sample_preview": cleaned_text[:300]
    }


@app.post("/api/validation/verify-quote")
def verify_extracted_quote(payload: ValidationPayload):
    """Validates the alignment of an extracted quote against the source material. (Stage 2)"""
    success, score = validate_quote(payload.quote, payload.source_text)
    return {
        "is_valid": success,
        "similarity_score": score,
        "action_taken": "Proceed" if success else "Discard Signal"
    }


@app.get("/api/score/simulate")
def simulate_scoring_pipeline():
    """Simulates scoring and returns a full strict LeadDetailResponse payload."""
    mock_llm_json = {
        "company_name": "Crework Labs",
        "intent_score": 85,
        "signals": [
            {
                "signal_type": "sdr_hiring",
                "verbatim_quote": "Looking for high-velocity SDR leadership",
                "event_date": "2026-06-15T12:00:00Z"
            },
            {
                "signal_type": "growth_news",
                "verbatim_quote": "expanding its global B2B footprint",
                "event_date": "2026-02-10T12:00:00Z"
            }
        ],
        "ai_verdict": "High conversion potential for outbound agency services."
    }

    mock_firmographics = {
        "employee_count": 45,
        "funding_stage": "Seed",
        "industry": "Software Development"
    }

    scored_payload = process_hybrid_lead_scoring(
        mock_llm_json, mock_firmographics
    )
    verified_count = sum(
        1 for signal in scored_payload["signals"]
        if signal["quote_validated"]
    )

    return {
        "id": "score-sim-1",
        "company_name": scored_payload["company_name"],
        "domain": "creworklabs.com",
        "industry": mock_firmographics["industry"],
        "employee_count": mock_firmographics["employee_count"],
        "funding_stage": mock_firmographics["funding_stage"],
        "intent_score": scored_payload["intent_score"],
        "signal_freshness": scored_payload["signal_freshness"],
        "tier": scored_payload["tier"],
        "icp_fit": scored_payload["icp_fit"],
        "confidence": {
            "label": "High Trust" if verified_count else "Low Trust",
            "color": "emerald" if verified_count else "rose",
            "verified": verified_count,
            "total": len(scored_payload["signals"])
        },
        "why_now": "Validated SDR hiring and growth signals detected in the scoring simulation.",
        "badge": "signal_added",
        "signals": scored_payload["signals"],
        "ai_verdict": scored_payload["ai_verdict"],
        "dns_audit": audit_domain_email_infrastructure("creworklabs.com"),
        "last_updated": datetime.now(timezone.utc).isoformat()
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True, access_log=False)

