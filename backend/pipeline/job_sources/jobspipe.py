from datetime import datetime, timedelta, timezone
from typing import Any

import requests

from backend.config import settings


JOBSPIPE_URL = "https://api.jobspipe.dev/v1/jobs/search"


def _normalize_job(item: dict[str, Any], discovered_at: datetime) -> dict[str, Any]:
    company_object = item.get("company_object") or {}

    return {
        "title": item.get("job_title"),
        "normalized_title": item.get("normalized_title"),
        "company_name": item.get("company"),
        "company_website": company_object.get("url"),
        "company_logo": company_object.get("logo"),
        "company_domain": item.get("company_domain"),
        "location": item.get("location"),
        "workplace_type": item.get("work_arrangement"),
        "employment_type": (
            item.get("employment_statuses")[0]
            if item.get("employment_statuses")
            else None
        ),
        "experience_level": item.get("seniority"),
        "salary_min": item.get("min_annual_salary"),
        "salary_max": item.get("max_annual_salary"),
        "salary_currency": item.get("salary_currency"),
        "salary_unit": "YEAR" if item.get("min_annual_salary") or item.get("max_annual_salary") else None,
        "ats_source": (
            item.get("sources")[0].get("provider")
            if item.get("sources") and isinstance(item["sources"][0], dict)
            else None
        ),
        "source": "jobspipe",
        "apply_url": item.get("url"),
        "listing_url": item.get("source_url") or item.get("url"),
        "description": item.get("description"),
        "summary": None,
        "qualifications": None,
        "responsibilities": None,
        "benefits": item.get("benefits"),
        "date_posted": item.get("date_posted"),
        "original_post_date": item.get("date_posted"),
        "first_discovered_at": item.get("discovered_at") or discovered_at,
        "last_seen_at": item.get("last_seen_at") or discovered_at,
        "job_identity_key": None,
    }


def _date_window(now: datetime) -> tuple[str, str]:
    return (
        (now - timedelta(days=60)).date().isoformat(),
        (now - timedelta(days=15)).date().isoformat(),
    )


def fetch_jobspipe_day1_jobs(limit: int = 10) -> list[dict[str, Any]]:
    """
    Fetch JobsPipe jobs posted 15-60 days ago.

    Day 1 acquisition function, filtered by posting date window.
    """
    if not settings.JOBSPIPE_API_KEY:
        raise RuntimeError("JOBSPIPE_API_KEY is not configured")

    now = datetime.now(timezone.utc)
    posted_at_gte, posted_at_lte = _date_window(now)

    payload = {
        "posted_at_gte": posted_at_gte,
        "posted_at_lte": posted_at_lte,
        "limit": limit,
        "job_country_code_or": ["US"],
        "isic_division_or": ["62"],
    }

    response = requests.post(
        JOBSPIPE_URL,
        headers={
            "Authorization": f"Bearer {settings.JOBSPIPE_API_KEY}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=120,
    )
    response.raise_for_status()

    result = response.json()
    items = result.get("data", [])

    if not isinstance(items, list):
        raise RuntimeError("Unexpected JobsPipe response: data must be a list")

    discovered_at = now

    return [
        _normalize_job(item, discovered_at)
        for item in items
        if isinstance(item, dict)
    ]


def fetch_jobspipe_day2_jobs(
    discovered_at_gte: datetime,
    limit: int = 100,
) -> list[dict[str, Any]]:
    """
    Fetch JobsPipe jobs discovered since the last successful Track Jobs run.

    Day 2+ acquisition function, filtered by discovered_at_gte instead of
    the Day 1 posting-date window.
    """
    if not settings.JOBSPIPE_API_KEY:
        raise RuntimeError("JOBSPIPE_API_KEY is not configured")

    now = datetime.now(timezone.utc)

    payload = {
        "discovered_at_gte": discovered_at_gte.isoformat(),
        "limit": limit,
        "job_country_code_or": ["US"],
        "isic_division_or": ["62"],
    }

    response = requests.post(
        JOBSPIPE_URL,
        headers={
            "Authorization": f"Bearer {settings.JOBSPIPE_API_KEY}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=120,
    )
    response.raise_for_status()

    result = response.json()
    items = result.get("data", [])

    if not isinstance(items, list):
        raise RuntimeError("Unexpected JobsPipe response: data must be a list")

    discovered_at = now

    return [
        _normalize_job(item, discovered_at)
        for item in items
        if isinstance(item, dict)
    ]