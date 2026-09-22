-- ======================================================================
-- Heimdall Lead Intelligence Platform — Supabase PostgreSQL Schema
-- Run this in your Supabase SQL Editor if you prefer manual table setup.
-- ======================================================================

-- Step 1: Create dedicated schema for Heimdall (Option A - prevents table collisions)
CREATE SCHEMA IF NOT EXISTS heimdall;

-- Set search path to heimdall schema
SET search_path TO heimdall, public;

-- ----------------------------------------------------------------------
-- Table 1: lead_snapshots (Company Intelligence Dashboard)
-- ----------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS heimdall.lead_snapshots (
    id VARCHAR PRIMARY KEY,
    domain VARCHAR NOT NULL,
    company_name VARCHAR,
    industry VARCHAR,
    employee_count INTEGER,
    funding_stage VARCHAR,
    intent_score INTEGER NOT NULL DEFAULT 0,
    signal_freshness INTEGER DEFAULT 100,
    tier VARCHAR,
    icp_fit VARCHAR,
    badge VARCHAR,
    social_segment VARCHAR,
    meta_ads_active BOOLEAN DEFAULT FALSE,
    meta_ads_count INTEGER DEFAULT 0,
    bio_url VARCHAR,
    why_now TEXT,
    ai_verdict TEXT,
    full_payload JSONB,
    last_updated TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_lead_snapshots_domain ON heimdall.lead_snapshots(domain);
CREATE INDEX IF NOT EXISTS idx_lead_snapshots_company_name ON heimdall.lead_snapshots(company_name);
CREATE INDEX IF NOT EXISTS idx_lead_snapshots_intent_score ON heimdall.lead_snapshots(intent_score);

-- ----------------------------------------------------------------------
-- Table 2: social_posts (Social Media Thread Discovery)
-- ----------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS heimdall.social_posts (
    id VARCHAR PRIMARY KEY,
    platform VARCHAR NOT NULL,
    author_name VARCHAR,
    author_handle VARCHAR,
    content TEXT NOT NULL,
    post_url VARCHAR NOT NULL,
    keyword_matched VARCHAR,
    company_name VARCHAR,
    published_at VARCHAR,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_social_posts_platform ON heimdall.social_posts(platform);
CREATE INDEX IF NOT EXISTS idx_social_posts_keyword ON heimdall.social_posts(keyword_matched);
CREATE INDEX IF NOT EXISTS idx_social_posts_url ON heimdall.social_posts(post_url);

-- ----------------------------------------------------------------------
-- Table 3: scrape_ledger (Scrape Cooldown Tracker)
-- ----------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS heimdall.scrape_ledger (
    id VARCHAR PRIMARY KEY,
    company_name VARCHAR NOT NULL,
    founder_handle VARCHAR,
    platform VARCHAR NOT NULL,
    last_scraped_date TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_scrape_ledger_company ON heimdall.scrape_ledger(company_name);

-- ----------------------------------------------------------------------
-- Table 4: pipeline_status (Background Scheduler Telemetry)
-- ----------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS heimdall.pipeline_status (
    id VARCHAR PRIMARY KEY,
    last_run_time VARCHAR,
    lead_count_processed INTEGER DEFAULT 0,
    status VARCHAR DEFAULT 'Idle',
    errors_encountered BOOLEAN DEFAULT FALSE
);
