import os
import json
import uuid
import httpx
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from pydantic import BaseModel

from backend.database import get_db
from backend.models import ATSJobRun, ATSJobSnapshot, DailyJobRelease, DeletedATSJob
from backend.config import settings
from backend.pipeline.mistral_service import generate_job_batch_summary
from backend.utils.logger import logger

router = APIRouter(prefix="/api/ats-jobs", tags=["ATS Jobs"])

# Default query payload for jobo.world/ats-jobs-api
DEFAULT_SEARCH_PAYLOAD = {
    "experience_levels": [
        "mid",
        "senior"
    ],
    "include_company_details": False,
    "locations": [
        "United States",
        "San Francisco",
        "New York, NY",
        "Austin, TX",
        "Seattle, WA",
        "Chicago, IL",
        "Boston, MA",
        "Los Angeles, CA",
        "Denver, CO"
    ],
    "page_size": 20,
    "posted_before": "30 days",
    "queries": [
        "Staff Software Engineer",
        "Senior Frontend Engineer",
        "Cloud Security Engineer",
        "Data Platform Architect",
        "DevSecOps Engineer"
    ],
    "search_description": True
}


class FetchJobsRequest(BaseModel):
    queries: Optional[List[str]] = None
    companies_include: Optional[List[str]] = None
    experience_levels: Optional[List[str]] = None
    page_size: Optional[int] = 20


def get_canonical_company_key(name: str) -> str:
    """Normalizes company name by stripping punctuation and corporate/tech suffixes."""
    if not name:
        return ""
    import re
    clean = re.sub(r'[^a-zA-Z0-9\s]', '', str(name).lower()).strip()
    suffixes = {"ai", "inc", "corp", "corporation", "llc", "ltd", "limited", "tech", "technologies", "technology", "software", "systems", "solutions", "labs", "group", "co", "company"}
    tokens = [t for t in clean.split() if t]
    while len(tokens) > 1 and tokens[-1] in suffixes:
        tokens.pop()
    return " ".join(tokens)


def parse_job_item(item: dict, run_id: str) -> ATSJobSnapshot:
    """Helper to convert Apify raw dataset item into ATSJobSnapshot model."""
    job_id = item.get("id") or str(uuid.uuid4())
    title = item.get("title") or item.get("normalized_title") or "Software Engineer"
    normalized_title = item.get("normalized_title") or title
    
    company_info = item.get("company")
    if isinstance(company_info, dict):
        company_name = company_info.get("name") or "Unknown Company"
        company_website = company_info.get("website")
        company_logo = company_info.get("logo_url")
    else:
        company_name = str(company_info or "Unknown Company")
        company_website = None
        company_logo = None

    # Location formatting
    locations_list = item.get("locations", [])
    if isinstance(locations_list, list) and locations_list:
        loc_strs = [
            f"{l.get('city', '')}, {l.get('region', '')} ({l.get('country', '')})"
            if isinstance(l, dict) else str(l) for l in locations_list
        ]
        location = "; ".join(filter(None, loc_strs))
    else:
        location = item.get("location") or "Remote / Unspecified"

    # Compensation parsing
    comp = item.get("compensation") or {}
    comp_min = comp.get("min") if isinstance(comp, dict) else None
    comp_max = comp.get("max") if isinstance(comp, dict) else None
    comp_currency = comp.get("currency", "USD") if isinstance(comp, dict) else "USD"
    comp_period = comp.get("period", "yearly") if isinstance(comp, dict) else "yearly"

    snapshot = ATSJobSnapshot(
        id=job_id,
        run_id=run_id,
        title=title,
        normalized_title=normalized_title,
        company_name=company_name,
        company_website=company_website,
        company_logo=company_logo,
        location=location,
        workplace_type=item.get("workplace_type") or "Remote",
        employment_type=item.get("employment_type") or "Full-time",
        experience_level=item.get("experience_level") or "Mid Level",
        compensation_min=float(comp_min) if comp_min is not None else None,
        compensation_max=float(comp_max) if comp_max is not None else None,
        compensation_currency=comp_currency,
        compensation_period=comp_period,
        ats_source=item.get("source") or "ats",
        apply_url=item.get("apply_url") or item.get("listing_url"),
        listing_url=item.get("listing_url") or item.get("apply_url"),
        description=item.get("description"),
        summary=item.get("summary") or (item.get("description") or "")[:250],
        qualifications=item.get("qualifications"),
        responsibilities=item.get("responsibilities"),
        benefits=item.get("benefits"),
        date_posted=str(item.get("date_posted") or item.get("created_at") or ""),
        created_at=datetime.now(timezone.utc)
    )
    return snapshot


def is_strict_us_location(item: dict) -> bool:
    """Verifies job location is strictly US or US Remote (filters out non-US locations like Mumbai/London)."""
    locations = item.get("locations") or []
    workplace_type = (item.get("workplace_type") or "").lower()

    if not locations:
        return True

    for loc in locations:
        if isinstance(loc, dict):
            country = (loc.get("country") or "").lower()
            location_str = (loc.get("location") or "").lower()
            city = (loc.get("city") or "").lower()
            region = (loc.get("region") or "").lower()

            if country and not any(c in country for c in ["united states", "us", "usa"]):
                return False

            if any(c in country for c in ["united states", "us", "usa"]):
                return True

            us_hubs = ["san francisco", "new york", "austin", "seattle", "chicago", "boston", "los angeles", "san jose", "denver", "atlanta", "texas", "california", "washington", "new york", "massachusetts", "illinois", "colorado", "georgia"]
            if any(hub in location_str or hub in city or hub in region for hub in us_hubs):
                return True
        elif isinstance(loc, str):
            if any(c in loc.lower() for c in ["united states", "us", "usa", "san francisco", "new york", "austin", "seattle", "chicago"]):
                return True

    return workplace_type == "remote"


def is_posted_before_30_days(item: dict) -> bool:
    """Verifies job posting date was posted BEFORE 30 days ago (>= 30 days old)."""
    date_str = item.get("date_posted") or item.get("created_at")
    if not date_str:
        return True
    try:
        clean_date = str(date_str).replace("Z", "+00:00")
        if "T" in clean_date:
            dt = datetime.fromisoformat(clean_date)
        else:
            dt = datetime.strptime(clean_date[:10], "%Y-%m-%d").replace(tzinfo=timezone.utc)

        days_old = (datetime.now(timezone.utc) - dt).days
        return days_old >= 30
    except Exception:
        return True


def has_valid_date_posted(item: dict) -> bool:
    """Verifies that job item has an explicit date_posted attribute specified in raw JSON data."""
    dp = item.get("date_posted")
    if not dp or str(dp).strip().lower() in ["", "none", "null", "undefined"]:
        return False
    return True


def serialize_job(j: ATSJobSnapshot) -> dict:
    return {
        "id": j.id,
        "run_id": j.run_id,
        "title": j.title,
        "normalized_title": j.normalized_title,
        "company_name": j.company_name,
        "company_website": j.company_website,
        "company_logo": j.company_logo,
        "location": j.location,
        "workplace_type": j.workplace_type,
        "employment_type": j.employment_type,
        "experience_level": j.experience_level,
        "compensation_min": j.compensation_min,
        "compensation_max": j.compensation_max,
        "compensation_currency": j.compensation_currency,
        "compensation_period": j.compensation_period,
        "ats_source": j.ats_source,
        "apply_url": j.apply_url,
        "listing_url": j.listing_url,
        "description": j.description,
        "summary": j.summary,
        "qualifications": j.qualifications,
        "responsibilities": j.responsibilities,
        "benefits": j.benefits,
        "date_posted": j.date_posted,
        "verified_contacts": j.verified_contacts or [],
        "contacts_enriched_at": j.contacts_enriched_at.isoformat() if j.contacts_enriched_at else None,
        "created_at": j.created_at.isoformat() if j.created_at else None,
        "status": j.status,
        "original_post_date": j.original_post_date,
        "monitor_until": j.monitor_until.isoformat() if j.monitor_until else None,
        "last_rescraped_at": j.last_rescraped_at.isoformat() if j.last_rescraped_at else None,
        "jd_changed": bool(j.jd_changed),
        "reposted": bool(j.reposted),
        "repost_of_job_id": j.repost_of_job_id
    }


@router.post("/fetch")
async def fetch_ats_jobs(req: Optional[FetchJobsRequest] = None, db: Session = Depends(get_db)):
    """
    Triggers Apify actor jobo.world/ats-jobs-api with $0.04 cost guardrails.
    Passes raw job items to Mistral AI for batch summary synthesis.
    Stores the run metadata and job snapshots in NeonDB database.
    """
    apify_key = os.getenv("APIFY_API_KEY") or getattr(settings, "APIFY_API_KEY", "")
    if not apify_key:
        logger.error("❌ APIFY_API_KEY is missing in environment.")
        raise HTTPException(status_code=500, detail="APIFY_API_KEY is not configured in backend environment.")

    actor_id = "jobo.world~ats-jobs-api"
    apify_url = f"https://api.apify.com/v2/acts/{actor_id}/run-sync-get-dataset-items"

    # Construct payload from DEFAULT_SEARCH_PAYLOAD
    payload = dict(DEFAULT_SEARCH_PAYLOAD)

    if req:
        if req.queries:
            payload["queries"] = req.queries
        if req.companies_include is not None:
            payload["companies_include"] = req.companies_include
        if req.experience_levels:
            payload["experience_levels"] = req.experience_levels
        if req.page_size:
            payload["page_size"] = min(req.page_size, 20)

    # 🛡️ Mandatory Cost & Execution Guardrails
    params = {
        "token": apify_key,
        "maxTotalChargeUsd": 0.04,  # Cap maximum charge in USD to $0.04
        "maxItems": 20,             # Cap total dataset items returned
        "timeout": 60               # Hard timeout in seconds
    }

    logger.info(f"📡 Calling Apify actor {actor_id} with maxTotalChargeUsd=0.04...")

    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            res = await client.post(apify_url, params=params, json=payload)

        if res.status_code not in [200, 201]:
            logger.error(f"❌ Apify API Error {res.status_code}: {res.text}")
            raise HTTPException(
                status_code=res.status_code,
                detail=f"Apify Actor error ({res.status_code}): {res.text[:300]}"
            )

        items = res.json()
        if isinstance(items, dict):
            items = items.get("items", []) or items.get("data", [])

        if not isinstance(items, list):
            items = []

        logger.info(f"✅ Apify returned {len(items)} job items from actor execution.")

        # Retrieve all blacklisted deleted companies/URLs to prevent resurfacing
        deleted_records = db.query(DeletedATSJob).all()
        blacklisted_companies = set()
        blacklisted_urls = set()
        for d in deleted_records:
            if d.canonical_company:
                blacklisted_companies.add(d.canonical_company.strip().lower())
            if d.company_name:
                blacklisted_companies.add(d.company_name.strip().lower())
            if d.job_url:
                blacklisted_urls.add(d.job_url.strip())

        # Filter items for strict US location
        raw_filtered = [item for item in items if is_strict_us_location(item)]
        if not raw_filtered and items:
            raw_filtered = items

        # Deduplicate items by (company, title, url) & exclude blacklisted deleted companies
        items = []
        seen_job_keys = set()
        for item in raw_filtered:
            comp_info = item.get("company")
            comp_name = comp_info.get("name") if isinstance(comp_info, dict) else str(comp_info or "")
            norm_name = comp_name.strip().lower()
            canon_key = get_canonical_company_key(comp_name) or norm_name
            item_url = item.get("url") or item.get("apply_url") or ""
            item_title = (item.get("title") or item.get("normalized_title") or "").strip().lower()

            if norm_name in blacklisted_companies or canon_key in blacklisted_companies or (item_url and item_url in blacklisted_urls):
                continue

            job_key = (canon_key, item_title, item_url)
            if job_key not in seen_job_keys:
                seen_job_keys.add(job_key)
                items.append(item)

        # Macro hiring summary LLM generation via Mistral AI
        general_summary = await generate_job_batch_summary(items)

        # Save ATSJobRun metadata
        run_id = f"run_{uuid.uuid4().hex[:12]}"
        job_run = ATSJobRun(
            id=run_id,
            run_time=datetime.now(timezone.utc),
            job_count=len(items),
            general_summary=general_summary,
            query_payload=payload
        )
        db.add(job_run)

        # Save individual ATSJobSnapshots
        snapshots = []
        for raw_item in items:
            snap = parse_job_item(raw_item, run_id)
            db.merge(snap)
            snapshots.append(snap)

        db.commit()
        db.refresh(job_run)

        # Query all cumulative job snapshots stored across all runs, filtering out any deleted companies
        all_snapshots = db.query(ATSJobSnapshot).order_by(ATSJobSnapshot.created_at.desc()).all()
        cumulative_jobs = []
        seen_job_keys = set()
        for j in all_snapshots:
            norm_company = (j.company_name or "").strip().lower()
            canon_company = get_canonical_company_key(j.company_name) or norm_company
            url_match = (j.listing_url and j.listing_url.strip() in blacklisted_urls) or (j.apply_url and j.apply_url.strip() in blacklisted_urls)

            if norm_company in blacklisted_companies or canon_company in blacklisted_companies or url_match:
                continue

            job_key = (canon_company, (j.title or "").strip().lower(), (j.listing_url or j.apply_url or j.id or "").strip().lower())
            if job_key not in seen_job_keys:
                seen_job_keys.add(job_key)
                cumulative_jobs.append(j)

        return {
            "status": "success",
            "run_id": run_id,
            "run_time": job_run.run_time.isoformat(),
            "job_count": len(cumulative_jobs),
            "general_summary": general_summary,
            "jobs": [serialize_job(j) for j in cumulative_jobs]
        }

    except HTTPException as http_err:
        logger.error(f"❌ HTTPException in fetch_ats_jobs: {http_err.detail}")
        raise
    except Exception as e:
        logger.error(f"❌ Exception in fetch_ats_jobs: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to fetch ATS jobs: {str(e)}")


@router.get("")
@router.get("/")
@router.get("/latest")
def get_latest_ats_jobs(db: Session = Depends(get_db)):
    """Retrieves the latest fetch run and all stored cumulative job cards, excluding blacklisted deleted jobs."""
    latest_run = db.query(ATSJobRun).order_by(ATSJobRun.run_time.desc()).first()

    # Retrieve all deleted blacklisted companies
    deleted_records = db.query(DeletedATSJob).all()
    blacklisted_companies = set()
    blacklisted_urls = set()
    for d in deleted_records:
        if d.canonical_company:
            blacklisted_companies.add(d.canonical_company.strip().lower())
        if d.company_name:
            blacklisted_companies.add(d.company_name.strip().lower())
        if d.job_url:
            blacklisted_urls.add(d.job_url.strip())

    # Retrieve all stored job snapshots across all sweeps
    raw_jobs = db.query(ATSJobSnapshot).order_by(ATSJobSnapshot.created_at.desc()).all()

    # Deduplicate cumulative jobs by (company, title, url), excluding blacklisted deleted companies
    jobs = []
    seen_job_keys = set()
    for j in raw_jobs:
        norm_company = (j.company_name or "").strip().lower()
        canon_company = get_canonical_company_key(j.company_name) or norm_company
        url_match = (j.listing_url and j.listing_url.strip() in blacklisted_urls) or (j.apply_url and j.apply_url.strip() in blacklisted_urls)

        if norm_company in blacklisted_companies or canon_company in blacklisted_companies or url_match:
            continue

        job_key = (canon_company, (j.title or "").strip().lower(), (j.listing_url or j.apply_url or j.id or "").strip().lower())
        if job_key not in seen_job_keys:
            seen_job_keys.add(job_key)
            jobs.append(j)

    return {
        "status": "success",
        "run_id": latest_run.id if latest_run else None,
        "run_time": latest_run.run_time.isoformat() if latest_run and latest_run.run_time else None,
        "job_count": len(jobs),
        "general_summary": latest_run.general_summary if latest_run else "",
        "jobs": [serialize_job(j) for j in jobs]
    }


@router.get("/track")
def get_track_jobs(db: Session = Depends(get_db)):
    """
    Returns today's surfaced Track Jobs postings.

    Read-only. Does not release/surface jobs itself — that is handled
    exclusively by fetch_day1_jobs/fetch_day2_jobs in job_pipeline.py,
    which run on the scheduler.
    """
    now = datetime.now(timezone.utc)
    release_date = now.date().isoformat()

    todays_job_ids = {
        row.job_id
        for row in db.query(DailyJobRelease.job_id)
        .filter(DailyJobRelease.release_date == release_date)
        .all()
        if row.job_id
    }

    if not todays_job_ids:
        return {
            "status": "success",
            "release_date": release_date,
            "job_count": 0,
            "jobs": []
        }

    jobs = (
        db.query(ATSJobSnapshot)
        .filter(ATSJobSnapshot.id.in_(todays_job_ids))
        .all()
    )

    return {
        "status": "success",
        "release_date": release_date,
        "job_count": len(jobs),
        "jobs": [serialize_job(job) for job in jobs]
    }
@router.post("/track/rescrape")
def rescrape_track_jobs():
    """Manually triggers the weekly Track Jobs monitoring sweep (JD changes, taken-down, reposts, 75-day expiry)."""
    from backend.pipeline.job_monitor import run_weekly_monitoring
    result = run_weekly_monitoring()
    return {"status": "success", **result}


@router.get("/runs")

@router.get("/runs")
def get_ats_job_runs(db: Session = Depends(get_db)):
    """Returns past fetch runs metadata."""
    runs = db.query(ATSJobRun).order_by(ATSJobRun.run_time.desc()).limit(20).all()
    return [
        {
            "id": r.id,
            "run_time": r.run_time.isoformat() if r.run_time else None,
            "job_count": r.job_count,
            "general_summary": r.general_summary
        }
        for r in runs
    ]


@router.delete("/{job_id}")
def delete_ats_job(job_id: str, db: Session = Depends(get_db)):
    """
    Permanently deletes a job snapshot and blacklists the company/posting
    so that neither duplicates from past runs nor new fetch sweeps will resurface it.
    """
    job = db.query(ATSJobSnapshot).filter(ATSJobSnapshot.id == job_id).first()
    comp_name = job.company_name if job else None
    canon_comp = get_canonical_company_key(comp_name) if comp_name else None
    title = job.title if job else None
    job_url = (job.listing_url or job.apply_url) if job else None

    # 1. Delete all matching snapshots in the database (handles duplicates across runs)
    if job and comp_name:
        all_matches = db.query(ATSJobSnapshot).all()
        for snap in all_matches:
            s_name = (snap.company_name or "").strip().lower()
            s_canon = get_canonical_company_key(snap.company_name) or s_name
            if snap.id == job_id or s_name == comp_name.lower() or (canon_comp and s_canon == canon_comp):
                db.delete(snap)
    else:
        db.query(ATSJobSnapshot).filter(ATSJobSnapshot.id == job_id).delete()

    # 2. Record in DeletedATSJob persistent blacklist table so it never resurfaces
    if comp_name or canon_comp or job_url:
        del_entry = DeletedATSJob(
            id=f"del_{uuid.uuid4().hex[:12]}",
            canonical_company=canon_comp or comp_name,
            company_name=comp_name,
            job_title=title,
            job_url=job_url,
            deleted_at=datetime.now(timezone.utc)
        )
        db.merge(del_entry)

    db.commit()
    logger.info(f"🗑️ Permanently deleted and blacklisted ATS job: {title} at {comp_name} ({job_id})")
    return {"status": "success", "id": job_id, "deleted_company": comp_name}
