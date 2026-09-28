from datetime import datetime, timedelta, timezone
from typing import Any

from apify_client import ApifyClient

from backend.config import settings


APIFY_ACTOR_ID = "fantastic-jobs/career-site-job-listing-api"


def _first_value(value: Any) -> Any:
    if isinstance(value, list):
        return value[0] if value else None
    return value


def _parse_datetime(value: Any) -> datetime | None:
    if not value:
        return None

    try:
        parsed = datetime.fromisoformat(
            str(value).replace("Z", "+00:00")
        )

        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        else:
            parsed = parsed.astimezone(timezone.utc)

        return parsed

    except (TypeError, ValueError):
        return None


def _location_text(item: dict[str, Any]) -> str | None:
    if item.get("locations_alt"):
        return item["locations_alt"]

    locations = item.get("locations_derived") or []

    if isinstance(locations, list):
        parts = []

        for location in locations:
            if isinstance(location, dict):
                parts.append(
                    ", ".join(
                        str(value)
                        for value in (
                            location.get("city"),
                            location.get("admin"),
                            location.get("country"),
                        )
                        if value
                    )
                )
            elif location:
                parts.append(str(location))

        return "; ".join(
            part for part in parts if part
        ) or None

    return None


def _normalize_job(
    item: dict[str, Any],
    discovered_at: datetime,
) -> dict[str, Any]:

    description = (
        item.get("description_text")
        or item.get("description_html")
    )

    workplace_type = item.get("ai_work_arrangement")

    employment_type = (
        item.get("ai_employment_type")
        or item.get("employment_type")
    )

    return {
        "title": item.get("title"),
        "normalized_title": None,

        "company_name": item.get("organization"),

        "company_website": (
            item.get("org_linkedin_website")
            or item.get("organization_url")
        ),

        "company_logo": (
            item.get("org_logo_permalink")
            or item.get("organization_logo")
        ),

        "company_domain": (
            item.get("domain_derived")
            or item.get("source_domain")
        ),

        "location": _location_text(item),

        "workplace_type": workplace_type,

        "employment_type": _first_value(employment_type),

        "experience_level": item.get(
            "ai_experience_level"
        ),

        "salary_min": item.get(
            "ai_salary_min_value"
        ),

        "salary_max": item.get(
            "ai_salary_max_value"
        ),

        "salary_currency": item.get(
            "ai_salary_currency"
        ),

        "salary_unit": item.get(
            "ai_salary_unit_text"
        ),

        "ats_source": item.get("source"),

        "source": "apify_career_site_feed",

        "apply_url": item.get("url"),

        "listing_url": item.get("url"),

        "description": description,

        "summary": item.get(
            "ai_core_responsibilities"
        ),

        "qualifications": item.get(
            "ai_requirements_summary"
        ),

        "responsibilities": item.get(
            "ai_core_responsibilities"
        ),

        "benefits": item.get(
            "ai_benefits"
        ),

        "date_posted": item.get(
            "date_posted"
        ),

        "original_post_date": item.get(
            "date_posted"
        ),

        "first_discovered_at": discovered_at,

        "last_seen_at": discovered_at,

        "job_identity_key": None,
    }


def _filter_by_post_date(
    jobs: list[dict[str, Any]],
    now: datetime,
) -> list[dict[str, Any]]:

    cutoff_60_days = now - timedelta(days=60)
    cutoff_15_days = now - timedelta(days=15)

    filtered_jobs = []

    no_date = 0
    invalid_date = 0
    too_recent = 0
    too_old = 0

    for job in jobs:

        posted_at = _parse_datetime(
            job.get("date_posted")
        )

        if not job.get("date_posted"):
            no_date += 1
            continue

        if posted_at is None:
            invalid_date += 1
            continue

        if cutoff_60_days <= posted_at <= cutoff_15_days:
            filtered_jobs.append(job)

        elif posted_at > cutoff_15_days:
            too_recent += 1

        else:
            too_old += 1

    print(
        "Career Site API date filter: "
        f"no_date={no_date} "
        f"invalid_date={invalid_date} "
        f"too_recent={too_recent} "
        f"too_old={too_old} "
        f"kept={len(filtered_jobs)}"
    )

    return filtered_jobs


def fetch_career_site_jobs(
    run_input: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:

    """
    Fetch Day 1 jobs from the Apify Career Site Job Listing API.

    The actor provides the backfill using timeRange=6m.
    The pipeline then keeps only jobs posted 15-60 days ago.

    Deduplication, ICP filtering, persistence, daily release
    selection, and monitoring are handled by later pipeline stages.
    """

    if not settings.APIFY_API_KEY:
        raise RuntimeError(
            "APIFY_API_KEY is not configured"
        )

    discovered_at = datetime.now(timezone.utc)

    cutoff_60_days = (
        discovered_at - timedelta(days=60)
    )

    payload = {
        "timeRange": "6m",
        "limit": 100,
        "datePostedAfter": cutoff_60_days.strftime("%Y-%m-%d"),
        "includeCompanyDetails": True,
        "descriptionType": "text",
        "locationSearch": ["United States"],
        "liIndustryFilter": [
            "Software Development",
            "IT Services and IT Consulting",
            "Information Services",
            "Computer and Network Security",
        ],
        "liOrganizationEmployeesGte": 50,
        "liOrganizationEmployeesLte": 2000,
        "removeAgency": True,
    }

    if run_input:
        payload.update(run_input)

    client = ApifyClient(
        settings.APIFY_API_KEY
    )

    run = client.actor(
        APIFY_ACTOR_ID
    ).call(
        run_input=payload
    )

    if not run:
        raise RuntimeError(
            "Apify Career Site Job Listing API run did not return a result"
        )

    dataset_id = run["defaultDatasetId"]

    items = list(
        client.dataset(
            dataset_id
        ).iterate_items()
    )

    normalized_jobs = [
        _normalize_job(
            item,
            discovered_at,
        )
        for item in items
        if isinstance(item, dict)
    ]

    print(
        f"Career Site API fetched={len(normalized_jobs)} "
        f"returning_all={len(normalized_jobs)}"
    )

    return normalized_jobs