"""Track Jobs pipeline.

This module keeps the new Track Jobs workflow separate from the existing
lead-intelligence pipeline.

Current scope:
- Fetch Day 1 jobs from the Career Site Job Listing API.
- Fetch Day 1 jobs from JobsPipe.
- Combine and deduplicate the two source results.
- Filter the combined jobs through the active client ICP.
- Store all qualified jobs in the database.

Daily release logic and monitoring will be added in later steps.
"""

import hashlib
import re
from datetime import datetime, timedelta, timezone
import uuid
from backend.config import settings
from backend.database import SessionLocal
from backend.models import ATSJobSnapshot, TrackJobsRun, DailyJobRelease
from backend.config_manager import load_intent_config
from backend.pipeline.enrichment import resolve_domain_via_serper
from backend.pipeline.icp_filter import apply_icp_filters
from backend.pipeline.job_sources.career_site_feed import fetch_career_site_jobs
from backend.pipeline.job_sources.jobspipe import (
    fetch_jobspipe_day1_jobs,
    fetch_jobspipe_day2_jobs,
)


def _normalize_title(title: str | None) -> str:
    """Normalize a job title for deduplication."""
    if not title:
        return ""

    return re.sub(r"\s+", " ", title.strip().lower())


def _deduplicate_jobs(jobs: list[dict]) -> list[dict]:
    """Deduplicate jobs using company domain + normalized job title."""
    seen = set()
    deduplicated_jobs = []

    for job in jobs:
        company_domain = (
            job.get("company_domain") or ""
        ).strip().lower()

        normalized_title = _normalize_title(
            job.get("title")
        )

        # If either part is missing, keep the job rather than
        # incorrectly grouping unrelated jobs together.
        if not company_domain or not normalized_title:
            deduplicated_jobs.append(job)
            continue

        job_key = (
            company_domain,
            normalized_title,
        )

        if job_key in seen:
            continue

        seen.add(job_key)

        job["normalized_title"] = normalized_title
        deduplicated_jobs.append(job)

    return deduplicated_jobs


def _parse_employee_count(employee_count) -> int | None:
    """Convert an employee count or range string into a usable integer."""
    if employee_count is None:
        return None

    if isinstance(employee_count, int):
        return employee_count

    if isinstance(employee_count, float):
        return int(employee_count)

    if isinstance(employee_count, str):
        matches = re.findall(
            r"\d[\d,]*",
            employee_count.replace(",", ""),
        )
        if matches:
            return max(int(match) for match in matches)

    return None


def _matches_target_industry(
    industry: str,
    target_industries: list[str],
) -> bool:
    """Return True when the enriched industry matches the active ICP."""
    if not industry or industry.strip().lower() == "unknown":
        return False

    normalized_industry = industry.strip().lower()

    return any(
        target.lower() in normalized_industry
        for target in target_industries
    )


def _matches_exclusion(
    company_name: str,
    firmographics: dict,
    exclude_terms: list[str],
) -> bool:
    """Return True when company information matches an ICP exclusion term."""
    searchable_text = " ".join(
        str(value)
        for value in [
            company_name,
            firmographics.get("industry", ""),
            firmographics.get("description", ""),
            firmographics.get("specialities", ""),
            firmographics.get("company_type", ""),
        ]
        if value
    ).lower()

    return any(
        term.lower() in searchable_text
        for term in exclude_terms
    )


async def _filter_jobs_by_icp(
    jobs: list[dict],
) -> list[dict]:
    """
    Enrich companies and strictly qualify jobs against the active client ICP.

    The existing apply_icp_filters() still calculates the standard score and
    fit label. Track Jobs additionally requires the configured employee range,
    target industry, and exclusion rules to pass.
    """
    qualified_jobs = []

    config = load_intent_config()
    active_niche = config.get("active_niche", "recruitment")
    niche_info = config.get("niches", {}).get(active_niche, {})

    min_employees = niche_info.get(
        "min_employees",
        config.get("min_employees", 0),
    )
    max_employees = niche_info.get(
        "max_employees",
        config.get("max_employees", 2000),
    )
    target_industries = niche_info.get(
        "target_industries"
    ) or config.get(
        "target_industries",
        settings.ICP.TARGET_INDUSTRIES,
    )
    exclude_terms = niche_info.get("exclude_terms", [])

    for job in jobs:
        company_name = job.get("company_name")
        company_domain = job.get("company_domain") or ""

        if not company_name:
            print(
                "Track Jobs ICP: rejected job with no company name"
            )
            continue

        try:
            resolved_domain, firmographics = (
                await resolve_domain_via_serper(
                    company_name=company_name,
                    serper_api_key=settings.SERPER_API_KEY,
                    phase1_estimated_domain=company_domain,
                )
            )
        except Exception as exc:
            print(
                f"Track Jobs ICP enrichment failed for "
                f"{company_name}: {exc}"
            )
            continue

        if resolved_domain:
            job["company_domain"] = resolved_domain

        hq_country = firmographics.get("hq_country") or firmographics.get("locations", [{}])
        is_us = False
        if isinstance(firmographics.get("hq_country"), str):
            is_us = firmographics["hq_country"].strip().upper() == "US"
        elif isinstance(firmographics.get("locations"), list):
            is_us = any(
                isinstance(loc, dict) and (loc.get("country") or "").strip().upper() == "US"
                for loc in firmographics["locations"]
                if isinstance(loc, dict) and loc.get("is_headquarter")
            )

        if not is_us:
            print(
                f"Track Jobs ICP: rejected {company_name} "
                f"(not US-based)"
            )
            continue

        employee_count = firmographics.get("employee_count")
        parsed_employee_count = _parse_employee_count(employee_count)

        funding_stage = firmographics.get("funding_stage")
        industry = firmographics.get("industry", "Unknown")

        score, fit_label = apply_icp_filters(
            base_score=100,
            employee_count=employee_count,
            funding_stage=funding_stage,
            industry=industry,
        )

        job["icp_score"] = score
        job["icp_fit_label"] = fit_label
        job["company_employee_count"] = employee_count
        job["company_industry"] = industry
        job["company_firmographics"] = firmographics

        if parsed_employee_count is None:
            print(
                f"Track Jobs ICP: rejected {company_name} "
                f"(employee count unavailable)"
            )
            continue

        if not (
            min_employees
            <= parsed_employee_count
            <= max_employees
        ):
            print(
                f"Track Jobs ICP: rejected {company_name} "
                f"(employees={parsed_employee_count}, "
                f"allowed={min_employees}-{max_employees})"
            )
            continue

        if not _matches_target_industry(
            industry,
            target_industries,
        ):
            print(
                f"Track Jobs ICP: rejected {company_name} "
                f"(industry={industry})"
            )
            continue

        if _matches_exclusion(
            company_name,
            firmographics,
            exclude_terms,
        ):
            print(
                f"Track Jobs ICP: rejected {company_name} "
                f"(excluded company type)"
            )
            continue

        qualified_jobs.append(job)

    print(
        f"Track Jobs ICP: input={len(jobs)} "
        f"qualified={len(qualified_jobs)} "
        f"rejected={len(jobs) - len(qualified_jobs)}"
    )

    return qualified_jobs


def _normalize_domain(domain: str | None) -> str:
    """Normalize a company domain for stable job identity."""
    if not domain:
        return ""

    domain = domain.strip().lower()
    domain = re.sub(r"^https?://", "", domain)
    domain = domain.split("/")[0]
    domain = domain.removeprefix("www.")

    return domain


def _build_job_identity_key(job: dict) -> str:
    """Build the stable company-domain + normalized-title job identity."""
    company_domain = _normalize_domain(
        job.get("company_domain")
    )
    normalized_title = _normalize_title(
        job.get("title")
    )

    raw_key = f"{company_domain}|{normalized_title}"

    return hashlib.sha256(
        raw_key.encode("utf-8")
    ).hexdigest()


def _parse_post_date(date_posted: str | None) -> datetime | None:
    """Parse a job posting date into a timezone-aware datetime."""
    if not date_posted:
        return None

    try:
        parsed = datetime.fromisoformat(
            str(date_posted).replace("Z", "+00:00")
        )
    except ValueError:
        return None

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)

    return parsed


def _description_hash(description: str | None) -> str | None:
    """Create a stable hash of a job description."""
    if not description:
        return None

    return hashlib.sha256(
        str(description).strip().encode("utf-8")
    ).hexdigest()


def _store_qualified_jobs(jobs: list[dict]) -> list[ATSJobSnapshot]:
    """
    Store qualified Track Jobs postings as held jobs.

    Existing jobs are not duplicated. New jobs are persisted to the qualified
    pool but are not surfaced; daily release logic is handled separately.
    """
    if not jobs:
        print("Track Jobs DB: no qualified jobs to store")
        return []

    db = SessionLocal()
    stored_jobs: list[ATSJobSnapshot] = []

    try:
        now = datetime.now(timezone.utc)

        for job in jobs:
            company_domain = _normalize_domain(
                job.get("company_domain")
            )
            normalized_title = _normalize_title(
                job.get("title")
            )

            if not company_domain or not normalized_title:
                print(
                    "Track Jobs DB: skipping job with incomplete identity"
                )
                continue

            job_identity_key = _build_job_identity_key(job)

            existing_job = (
                db.query(ATSJobSnapshot)
                .filter(
                    ATSJobSnapshot.job_identity_key
                    == job_identity_key
                )
                .first()
            )

            if existing_job:
                existing_job.last_seen_at = now
                continue

            original_post_date = job.get("date_posted")
            parsed_post_date = _parse_post_date(
                original_post_date
            )

            monitor_until = None
            if parsed_post_date:
                monitor_until = parsed_post_date + timedelta(days=75)
            location_value = job.get("location")

            if isinstance(location_value, list):
                location_value = "; ".join(str(loc) for loc in location_value if loc)

            

            new_job = ATSJobSnapshot(
                id=job.get("id") or job_identity_key,
                title=job.get("title") or normalized_title,
                normalized_title=normalized_title,
                company_name=job.get("company_name"),
                company_website=job.get("company_website"),
                company_logo=job.get("company_logo"),
                location=location_value,
                workplace_type=job.get("workplace_type"),
                employment_type=job.get("employment_type"),
                experience_level=job.get("experience_level"),
                compensation_min=job.get("compensation_min"),
                compensation_max=job.get("compensation_max"),
                compensation_currency=job.get(
                    "compensation_currency"
                ),
                compensation_period=job.get(
                    "compensation_period"
                ),
                ats_source=job.get("ats_source"),
                apply_url=job.get("apply_url"),
                listing_url=job.get("listing_url"),
                description=job.get("description"),
                summary=job.get("summary"),
                qualifications=job.get("qualifications"),
                responsibilities=job.get("responsibilities"),
                benefits=job.get("benefits"),
                date_posted=original_post_date,
                verified_contacts=job.get(
                    "verified_contacts"
                ),
                original_post_date=original_post_date,
                first_discovered_at=now,
                company_domain=company_domain,
                source=job.get("source"),
                status="held",
                last_seen_at=now,
                monitor_until=monitor_until,
                description_hash=_description_hash(
                    job.get("description")
                ),
                jd_changed=False,
                reposted=False,
                job_identity_key=job_identity_key,
            
            )

            db.add(new_job)
            stored_jobs.append(new_job)

        db.commit()

        print(
            f"Track Jobs DB: qualified={len(jobs)} "
            f"newly_stored={len(stored_jobs)}"
        )

        return stored_jobs

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()


async def fetch_day1_jobs() -> list[dict]:
    """Fetch, combine, deduplicate, ICP-filter, and store Day 1 jobs."""
    apify_jobs = fetch_career_site_jobs()
    jobspipe_jobs = fetch_jobspipe_day1_jobs()

    combined_jobs = apify_jobs + jobspipe_jobs

    deduplicated_jobs = _deduplicate_jobs(
        combined_jobs
    )

    qualified_jobs = await _filter_jobs_by_icp(
        deduplicated_jobs
    )

    _store_qualified_jobs(qualified_jobs)

    db = SessionLocal()
    try:
        now = datetime.now(timezone.utc)
        db.add(
            TrackJobsRun(
                id=f"track_run_{now.strftime('%Y%m%d%H%M%S%f')}",
                run_time=now,
                status="success",
            )
        )
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

    return qualified_jobs


async def fetch_day2_jobs(limit: int = 100, daily_quota: int = 60) -> list[dict]:
    """
    Day 2+ Track Jobs flow.

    Fresh JobsPipe jobs discovered since the last successful Track Jobs run
    are qualified and surfaced first. Any remaining daily quota is filled
    from previously held qualified jobs.
    """
    db = SessionLocal()

    try:
        previous_run = (
            db.query(TrackJobsRun)
            .filter(TrackJobsRun.status == "success")
            .order_by(TrackJobsRun.run_time.desc())
            .first()
        )

        if not previous_run:
            raise RuntimeError(
                "No successful Track Jobs run found. Run Day 1 before Day 2+."
            )

        discovered_at_gte = previous_run.run_time
    finally:
        db.close()

    # Day 2+ acquisition is JobsPipe only.
    jobs = fetch_jobspipe_day2_jobs(
        discovered_at_gte=discovered_at_gte,
        limit=limit,
    )

    deduplicated_jobs = _deduplicate_jobs(jobs)
    qualified_jobs = await _filter_jobs_by_icp(deduplicated_jobs)

    # Persist qualified fresh jobs. Newly inserted rows are the fresh set.
    stored_fresh_jobs = _store_qualified_jobs(qualified_jobs)

    db = SessionLocal()

    try:
        now = datetime.now(timezone.utc)
        release_date = now.date().isoformat()

        # Do not release the same job twice on the same day.
        released_today_ids = {
            release.job_id
            for release in (
                db.query(DailyJobRelease)
                .filter(DailyJobRelease.release_date == release_date)
                .all()
            )
        }

        released_count = 0

        # 1. Fresh jobs get priority and count toward the daily quota.
        for job in stored_fresh_jobs:
            if released_count >= daily_quota:
                break

            if job.id in released_today_ids:
                continue

            job.status = "surfaced"
            job.surfaced_at = now

            db.add(
                DailyJobRelease(
                    id=f"release_{uuid.uuid4().hex[:12]}",
                    job_id=job.id,
                    release_date=release_date,
                )
            )
            released_today_ids.add(job.id)
            released_count += 1

        # 2. Fill the remaining quota from the existing held pool.
        remaining_quota = max(daily_quota - released_count, 0)

        if remaining_quota:
            held_jobs = (
                db.query(ATSJobSnapshot)
                .filter(ATSJobSnapshot.status == "held")
                .order_by(
                    ATSJobSnapshot.first_discovered_at.asc(),
                    ATSJobSnapshot.id.asc(),
                )
                .all()
            )

            for job in held_jobs:
                if remaining_quota <= 0:
                    break

                if job.id in released_today_ids:
                    continue

                job.status = "surfaced"
                job.surfaced_at = now

                db.add(
                DailyJobRelease(
                    id=f"release_{uuid.uuid4().hex[:12]}",
                    job_id=job.id,
                    release_date=release_date,
                )
            )
                released_today_ids.add(job.id)
                released_count += 1
                remaining_quota -= 1

        # Only advance the run timestamp after acquisition, qualification,
        # persistence, and release all succeed.
        db.add(
            TrackJobsRun(
                id=f"track_run_{now.strftime('%Y%m%d%H%M%S%f')}",
                run_time=now,
                status="success",
            )
        )

        db.commit()

        print(
            f"Track Jobs Day 2+: fresh_qualified={len(qualified_jobs)} "
            f"fresh_released={min(len(stored_fresh_jobs), daily_quota)} "
            f"total_released={released_count} quota={daily_quota}"
        )

    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

    return qualified_jobs

