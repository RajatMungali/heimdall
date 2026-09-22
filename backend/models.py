from sqlalchemy import Column, String, Integer, Float, DateTime, Text, Boolean, JSON, ForeignKey

from backend.database import Base

from datetime import datetime, timezone


class LeadSnapshot(Base):
    """Stores scored lead data for historical comparison and freshness badge computation."""
    __tablename__ = "lead_snapshots"

    id = Column(String, primary_key=True, index=True)

    domain = Column(String, index=True, nullable=False)
    company_name = Column(String, nullable=True)
    company_segment = Column(String, nullable=True, default="Growth Scale-up")
    industry = Column(String, nullable=True)
    employee_count = Column(Integer, nullable=True)
    funding_stage = Column(String, nullable=True)
    intent_score = Column(Integer, nullable=False, default=0)
    signal_freshness = Column(Integer, nullable=True, default=100)
    tier = Column(String, nullable=True)
    icp_fit = Column(String, nullable=True)
    badge = Column(String, nullable=True)
    social_segment = Column(String, nullable=True)  # Segment A, Segment B, Segment C
    meta_ads_active = Column(Boolean, default=False)
    meta_ads_count = Column(Integer, default=0)
    bio_url = Column(String, nullable=True)
    why_now = Column(
        Text,
        nullable=True,
        default="Verified public buying intent triggers detected."
    )
    signal_tags = Column(JSON, nullable=True, default=list)
    ai_verdict = Column(Text, nullable=True)
    company_linkedin_id = Column(String, nullable=True)
    annual_revenue = Column(String, nullable=True)
    company_insights = Column(JSON, nullable=True)
    job_openings = Column(JSON, nullable=True)
    full_payload = Column(JSON, nullable=True)

    last_updated = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc)
    )


class PipelineStatus(Base):
    """Tracks background pipeline execution state for telemetry reporting."""
    __tablename__ = "pipeline_status"

    id = Column(String, primary_key=True, index=True)

    last_run_time = Column(String, nullable=True)
    lead_count_processed = Column(Integer, default=0)
    status = Column(String, nullable=True, default="Idle")
    errors_encountered = Column(Boolean, default=False)


class ScrapeLedger(Base):
    """Tracks previously scraped founders/companies to enforce cooldowns and protect credit budgets."""
    __tablename__ = "scrape_ledger"

    id = Column(String, primary_key=True, index=True)

    company_name = Column(String, index=True, nullable=False)
    founder_handle = Column(String, nullable=True)
    platform = Column(String, nullable=False)

    last_scraped_date = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc)
    )


class SocialPostSnapshot(Base):
    """Stores curated social media posts fetched via Scrape Creators API."""
    __tablename__ = "social_posts"

    id = Column(String, primary_key=True, index=True)

    platform = Column(String, nullable=False, index=True)
    author_name = Column(String, nullable=True)
    author_handle = Column(String, nullable=True)
    content = Column(Text, nullable=False)
    post_url = Column(String, nullable=False)
    keyword_matched = Column(String, nullable=True)
    company_name = Column(String, nullable=True)
    summary = Column(Text, nullable=True)
    published_at = Column(String, nullable=True)

    created_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc)
    )


class ScrapeCache(Base):
    """Tracks seen post URLs to prevent duplicate LLM classification in future runs."""
    __tablename__ = "scrape_cache"

    id = Column(String, primary_key=True, index=True)

    post_url = Column(String, unique=True, index=True, nullable=False)

    processed_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc)
    )


class ATSJobRun(Base):
    """Stores batch metadata for an Apify ATS jobs fetch run."""
    __tablename__ = "ats_job_runs"

    id = Column(String, primary_key=True, index=True)

    run_time = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc)
    )

    job_count = Column(Integer, default=0)
    general_summary = Column(Text, nullable=True)
    query_payload = Column(JSON, nullable=True)


class ATSJobSnapshot(Base):
    """Stores individual job posting snapshots fetched via jobo.world/ats-jobs-api."""
    __tablename__ = "ats_job_snapshots"

    id = Column(String, primary_key=True, index=True)

    run_id = Column(
        String,
        ForeignKey("ats_job_runs.id"),
        nullable=True,
        index=True
    )

    title = Column(String, nullable=False)
    normalized_title = Column(String, nullable=True)
    company_name = Column(String, nullable=True, index=True)
    company_website = Column(String, nullable=True)
    company_logo = Column(String, nullable=True)
    location = Column(String, nullable=True)
    workplace_type = Column(String, nullable=True)  # Remote, Hybrid, On-site
    employment_type = Column(String, nullable=True)  # Full-time, Part-time, Contract
    experience_level = Column(String, nullable=True)

    compensation_min = Column(Float, nullable=True)
    compensation_max = Column(Float, nullable=True)
    compensation_currency = Column(String, nullable=True)
    compensation_period = Column(String, nullable=True)

    ats_source = Column(
        String,
        nullable=True
    )  # greenhouse, ashby, oraclecloud, etc.

    apply_url = Column(String, nullable=True)
    listing_url = Column(String, nullable=True)

    description = Column(Text, nullable=True)
    summary = Column(Text, nullable=True)
    qualifications = Column(JSON, nullable=True)
    responsibilities = Column(JSON, nullable=True)
    benefits = Column(JSON, nullable=True)
    date_posted = Column(String, nullable=True)

    verified_contacts = Column(JSON, nullable=True)
    contacts_enriched_at = Column(DateTime, nullable=True)

    created_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc)
    )

    # ------------------------------------------------------------------
    # Track Jobs fields
    # ------------------------------------------------------------------

    # Original posting date used for the 75-day monitoring/expiry window.
    original_post_date = Column(
        String,
        nullable=True,
        index=True
    )

    # When Heimdall first discovered this job.
    first_discovered_at = Column(
        DateTime,
        nullable=True,
        index=True
    )

    # Normalized company domain used with normalized title for deduplication.
    company_domain = Column(
        String,
        nullable=True,
        index=True
    )

    # Which Track Jobs source produced this posting.
    source = Column(
        String,
        nullable=True,
        index=True
    )

    # Job lifecycle: held, surfaced, taken_down, expired.
    status = Column(
        String,
        nullable=True,
        default="held",
        index=True
    )

    # When the job was first surfaced to the user.
    surfaced_at = Column(
        DateTime,
        nullable=True
    )

    # Most recent time the posting was observed at its ATS.
    last_seen_at = Column(
        DateTime,
        nullable=True
    )

    # Most recent weekly rescrape time.
    last_rescraped_at = Column(
        DateTime,
        nullable=True
    )

    # 75-day expiry date calculated from the original post date.
    monitor_until = Column(
        DateTime,
        nullable=True,
        index=True
    )

    # Hash of the currently stored job description.
    description_hash = Column(
        String,
        nullable=True
    )

    # Previous description hash used to detect JD changes.
    previous_description_hash = Column(
        String,
        nullable=True
    )

    # True when the current JD differs from the previous version.
    jd_changed = Column(
        Boolean,
        nullable=True,
        default=False
    )

    # True when this posting is identified as a repost.
    reposted = Column(
        Boolean,
        nullable=True,
        default=False
    )

    # Original job this posting was reposted from.
    repost_of_job_id = Column(
        String,
        ForeignKey("ats_job_snapshots.id"),
        nullable=True,
        index=True
    )

    # Company domain + normalized title identity used for deduplication.
    job_identity_key = Column(
        String,
        nullable=True,
        index=True
    )


class DailyJobRelease(Base):
    """Records which Track Jobs postings were surfaced on each release day."""
    __tablename__ = "daily_job_releases"

    id = Column(String, primary_key=True, index=True)

    job_id = Column(
        String,
        ForeignKey("ats_job_snapshots.id"),
        nullable=False,
        index=True
    )

    release_date = Column(
        String,
        nullable=False,
        index=True
    )

    released_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc)
    )


class DeletedATSJob(Base):
    """Tracks deleted ATS job postings to prevent them from resurfacing on future sweeps."""
    __tablename__ = "deleted_ats_jobs"

    id = Column(String, primary_key=True, index=True)

    canonical_company = Column(String, index=True, nullable=True)
    company_name = Column(String, index=True, nullable=True)
    job_title = Column(String, nullable=True)
    job_url = Column(String, index=True, nullable=True)

    deleted_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc)
    )


class TrackJobsRun(Base):
    """Stores Track Jobs acquisition run metadata for Day 2+ polling."""
    __tablename__ = "track_jobs_runs"

    id = Column(String, primary_key=True, index=True)
    run_time = Column(DateTime, nullable=False)
    status = Column(String, nullable=False)