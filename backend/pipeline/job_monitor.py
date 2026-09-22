"""Track Jobs weekly monitoring.

Handles Step 3 (JD changes, taken-down detection, repost detection)
and Step 4 (75-day expiry) from the Track Jobs spec.

Only postings with status == "surfaced" are rescraped. Held postings
are left alone until they've actually been shown to the user.
"""

import hashlib
from datetime import datetime, timezone

import httpx

from backend.database import SessionLocal
from backend.models import ATSJobSnapshot
from backend.pipeline.filter_funnel import trim_html_for_llm
from backend.utils.logger import logger


def _description_hash(text: str | None) -> str | None:
    if not text:
        return None
    return hashlib.sha256(str(text).strip().encode("utf-8")).hexdigest()


def _fetch_posting_page(url: str) -> tuple[int | None, str]:
    """Fetch the ATS posting page. Returns (status_code, page_text)."""
    try:
        res = httpx.get(url, timeout=15.0, follow_redirects=True)
        return res.status_code, trim_html_for_llm(res.text)
    except Exception as exc:
        logger.warning(f"Job Monitor: fetch failed for {url}: {exc}")
        return None, ""


def _is_taken_down(status_code: int | None, page_text: str, job_title: str | None) -> bool:
    """A posting counts as taken down on 404/410, a fetch failure, or
    when the page no longer contains the job title."""
    if status_code in (404, 410) or status_code is None:
        return True

    if job_title and job_title.strip().lower() not in page_text.lower():
        return True

    return False


def rescrape_job_posting(job: ATSJobSnapshot) -> dict:
    """
    Re-scrape a single surfaced posting's ATS page.

    Returns a dict describing what changed:
    {"taken_down": bool, "jd_changed": bool, "new_hash": str | None}
    """
    url = job.listing_url or job.apply_url

    if not url:
        logger.warning(f"Job Monitor: job {job.id} has no listing_url/apply_url, skipping")
        return {"taken_down": False, "jd_changed": False, "new_hash": None}

    status_code, page_text = _fetch_posting_page(url)

    taken_down = _is_taken_down(status_code, page_text, job.title)

    if taken_down:
        return {"taken_down": True, "jd_changed": False, "new_hash": None}

    new_hash = _description_hash(page_text)
    jd_changed = bool(job.description_hash) and new_hash != job.description_hash

    return {"taken_down": False, "jd_changed": jd_changed, "new_hash": new_hash}


def run_weekly_monitoring() -> dict:
    """
    Step 3: re-scrape every surfaced posting, detect JD changes,
    taken-down postings, and reposts.

    Step 4: expire any posting (surfaced or held) past its
    monitor_until date, regardless of monitoring outcome.
    """
    db = SessionLocal()

    rescraped_count = 0
    jd_changed_count = 0
    taken_down_count = 0
    reposted_count = 0
    expired_count = 0

    try:
        now = datetime.now(timezone.utc)

        # --- Step 3: rescrape surfaced postings only ---
        surfaced_jobs = (
            db.query(ATSJobSnapshot)
            .filter(ATSJobSnapshot.status == "surfaced")
            .all()
        )

        for job in surfaced_jobs:
            result = rescrape_job_posting(job)
            rescraped_count += 1

            job.last_rescraped_at = now

            if result["taken_down"]:
                job.status = "taken_down"
                taken_down_count += 1
                continue

            if result["jd_changed"]:
                job.previous_description_hash = job.description_hash
                job.description_hash = result["new_hash"]
                job.jd_changed = True
                jd_changed_count += 1

        db.commit()

        # --- Repost detection ---
        # A repost is a taken-down posting whose company_domain +
        # normalized_title identity has reappeared as a *different*
        # job row (job_pipeline._store_qualified_jobs flips a
        # matching taken_down row back to held/reposted on re-fetch;
        # this pass catches any that were stored as new rows instead).
        taken_down_jobs = (
            db.query(ATSJobSnapshot)
            .filter(ATSJobSnapshot.status == "taken_down")
            .all()
        )

        for old_job in taken_down_jobs:
            match = (
                db.query(ATSJobSnapshot)
                .filter(
                    ATSJobSnapshot.job_identity_key == old_job.job_identity_key,
                    ATSJobSnapshot.id != old_job.id,
                    ATSJobSnapshot.status.in_(["held", "surfaced"]),
                )
                .first()
            )

            if match:
                match.reposted = True
                match.repost_of_job_id = old_job.id
                reposted_count += 1

        db.commit()

        # --- Step 4: 75-day expiry ---
        expiring_jobs = (
            db.query(ATSJobSnapshot)
            .filter(
                ATSJobSnapshot.monitor_until.isnot(None),
                ATSJobSnapshot.monitor_until < now,
                ATSJobSnapshot.status != "expired",
            )
            .all()
        )

        for job in expiring_jobs:
            job.status = "expired"
            expired_count += 1

        db.commit()

        logger.info(
            f"Job Monitor weekly run: rescraped={rescraped_count} "
            f"jd_changed={jd_changed_count} taken_down={taken_down_count} "
            f"reposted={reposted_count} expired={expired_count}"
        )

        return {
            "rescraped": rescraped_count,
            "jd_changed": jd_changed_count,
            "taken_down": taken_down_count,
            "reposted": reposted_count,
            "expired": expired_count,
        }

    except Exception:
        db.rollback()
        raise
    finally:
        db.close()