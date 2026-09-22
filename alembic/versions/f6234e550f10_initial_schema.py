"""initial_schema

Revision ID: f6234e550f10
Revises: 
Create Date: 2026-08-24 22:44:26.088846

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f6234e550f10'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── Table: lead_snapshots ─────────────────────────────────────────────
    op.create_table(
        'lead_snapshots',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('domain', sa.String(), nullable=False),
        sa.Column('company_name', sa.String(), nullable=True),
        sa.Column('company_segment', sa.String(), nullable=True, server_default='Growth Scale-up'),
        sa.Column('industry', sa.String(), nullable=True),
        sa.Column('employee_count', sa.Integer(), nullable=True),
        sa.Column('funding_stage', sa.String(), nullable=True),
        sa.Column('intent_score', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('signal_freshness', sa.Integer(), nullable=True, server_default='100'),
        sa.Column('tier', sa.String(), nullable=True),
        sa.Column('icp_fit', sa.String(), nullable=True),
        sa.Column('badge', sa.String(), nullable=True),
        sa.Column('social_segment', sa.String(), nullable=True),
        sa.Column('meta_ads_active', sa.Boolean(), nullable=True, server_default='false'),
        sa.Column('meta_ads_count', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('bio_url', sa.String(), nullable=True),
        sa.Column('why_now', sa.Text(), nullable=True, server_default='Verified public buying intent triggers detected.'),
        sa.Column('signal_tags', sa.JSON(), nullable=True),
        sa.Column('ai_verdict', sa.Text(), nullable=True),
        sa.Column('company_linkedin_id', sa.String(), nullable=True),
        sa.Column('annual_revenue', sa.String(), nullable=True),
        sa.Column('company_insights', sa.JSON(), nullable=True),
        sa.Column('job_openings', sa.JSON(), nullable=True),
        sa.Column('full_payload', sa.JSON(), nullable=True),
        sa.Column('last_updated', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_lead_snapshots_id', 'lead_snapshots', ['id'], unique=False)
    op.create_index('ix_lead_snapshots_domain', 'lead_snapshots', ['domain'], unique=False)
    op.create_index('ix_lead_snapshots_company_name', 'lead_snapshots', ['company_name'], unique=False)

    # ── Table: pipeline_status ────────────────────────────────────────────
    op.create_table(
        'pipeline_status',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('last_run_time', sa.String(), nullable=True),
        sa.Column('lead_count_processed', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('status', sa.String(), nullable=True, server_default='Idle'),
        sa.Column('errors_encountered', sa.Boolean(), nullable=True, server_default='false'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_pipeline_status_id', 'pipeline_status', ['id'], unique=False)

    # ── Table: scrape_ledger ──────────────────────────────────────────────
    op.create_table(
        'scrape_ledger',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('company_name', sa.String(), nullable=False),
        sa.Column('founder_handle', sa.String(), nullable=True),
        sa.Column('platform', sa.String(), nullable=False),
        sa.Column('last_scraped_date', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_scrape_ledger_id', 'scrape_ledger', ['id'], unique=False)
    op.create_index('ix_scrape_ledger_company_name', 'scrape_ledger', ['company_name'], unique=False)

    # ── Table: social_posts ───────────────────────────────────────────────
    op.create_table(
        'social_posts',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('platform', sa.String(), nullable=False),
        sa.Column('author_name', sa.String(), nullable=True),
        sa.Column('author_handle', sa.String(), nullable=True),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('post_url', sa.String(), nullable=False),
        sa.Column('keyword_matched', sa.String(), nullable=True),
        sa.Column('company_name', sa.String(), nullable=True),
        sa.Column('summary', sa.Text(), nullable=True),
        sa.Column('published_at', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_social_posts_id', 'social_posts', ['id'], unique=False)
    op.create_index('ix_social_posts_platform', 'social_posts', ['platform'], unique=False)

    # ── Table: scrape_cache ───────────────────────────────────────────────
    op.create_table(
        'scrape_cache',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('post_url', sa.String(), nullable=False),
        sa.Column('processed_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('post_url')
    )
    op.create_index('ix_scrape_cache_id', 'scrape_cache', ['id'], unique=False)
    op.create_index('ix_scrape_cache_post_url', 'scrape_cache', ['post_url'], unique=True)

    # ── Table: ats_job_runs ───────────────────────────────────────────────
    op.create_table(
        'ats_job_runs',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('run_time', sa.DateTime(), nullable=True),
        sa.Column('job_count', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('general_summary', sa.Text(), nullable=True),
        sa.Column('query_payload', sa.JSON(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_ats_job_runs_id', 'ats_job_runs', ['id'], unique=False)

    # ── Table: ats_job_snapshots ──────────────────────────────────────────
    op.create_table(
        'ats_job_snapshots',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('run_id', sa.String(), nullable=True),
        sa.Column('title', sa.String(), nullable=False),
        sa.Column('normalized_title', sa.String(), nullable=True),
        sa.Column('company_name', sa.String(), nullable=True),
        sa.Column('company_website', sa.String(), nullable=True),
        sa.Column('company_logo', sa.String(), nullable=True),
        sa.Column('location', sa.String(), nullable=True),
        sa.Column('workplace_type', sa.String(), nullable=True),
        sa.Column('employment_type', sa.String(), nullable=True),
        sa.Column('experience_level', sa.String(), nullable=True),
        sa.Column('compensation_min', sa.Float(), nullable=True),
        sa.Column('compensation_max', sa.Float(), nullable=True),
        sa.Column('compensation_currency', sa.String(), nullable=True),
        sa.Column('compensation_period', sa.String(), nullable=True),
        sa.Column('ats_source', sa.String(), nullable=True),
        sa.Column('apply_url', sa.String(), nullable=True),
        sa.Column('listing_url', sa.String(), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('summary', sa.Text(), nullable=True),
        sa.Column('qualifications', sa.JSON(), nullable=True),
        sa.Column('responsibilities', sa.JSON(), nullable=True),
        sa.Column('benefits', sa.JSON(), nullable=True),
        sa.Column('date_posted', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['run_id'], ['ats_job_runs.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_ats_job_snapshots_id', 'ats_job_snapshots', ['id'], unique=False)
    op.create_index('ix_ats_job_snapshots_run_id', 'ats_job_snapshots', ['run_id'], unique=False)
    op.create_index('ix_ats_job_snapshots_company_name', 'ats_job_snapshots', ['company_name'], unique=False)

    # ── Table: deleted_ats_jobs ───────────────────────────────────────────
    op.create_table(
        'deleted_ats_jobs',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('canonical_company', sa.String(), nullable=True),
        sa.Column('company_name', sa.String(), nullable=True),
        sa.Column('job_title', sa.String(), nullable=True),
        sa.Column('job_url', sa.String(), nullable=True),
        sa.Column('deleted_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_deleted_ats_jobs_id', 'deleted_ats_jobs', ['id'], unique=False)
    op.create_index('ix_deleted_ats_jobs_canonical_company', 'deleted_ats_jobs', ['canonical_company'], unique=False)
    op.create_index('ix_deleted_ats_jobs_company_name', 'deleted_ats_jobs', ['company_name'], unique=False)
    op.create_index('ix_deleted_ats_jobs_job_url', 'deleted_ats_jobs', ['job_url'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_deleted_ats_jobs_job_url', table_name='deleted_ats_jobs')
    op.drop_index('ix_deleted_ats_jobs_company_name', table_name='deleted_ats_jobs')
    op.drop_index('ix_deleted_ats_jobs_canonical_company', table_name='deleted_ats_jobs')
    op.drop_index('ix_deleted_ats_jobs_id', table_name='deleted_ats_jobs')
    op.drop_table('deleted_ats_jobs')

    op.drop_index('ix_ats_job_snapshots_company_name', table_name='ats_job_snapshots')
    op.drop_index('ix_ats_job_snapshots_run_id', table_name='ats_job_snapshots')
    op.drop_index('ix_ats_job_snapshots_id', table_name='ats_job_snapshots')
    op.drop_table('ats_job_snapshots')

    op.drop_index('ix_ats_job_runs_id', table_name='ats_job_runs')
    op.drop_table('ats_job_runs')

    op.drop_index('ix_scrape_cache_post_url', table_name='scrape_cache')
    op.drop_index('ix_scrape_cache_id', table_name='scrape_cache')
    op.drop_table('scrape_cache')

    op.drop_index('ix_social_posts_platform', table_name='social_posts')
    op.drop_index('ix_social_posts_id', table_name='social_posts')
    op.drop_table('social_posts')

    op.drop_index('ix_scrape_ledger_company_name', table_name='scrape_ledger')
    op.drop_index('ix_scrape_ledger_id', table_name='scrape_ledger')
    op.drop_table('scrape_ledger')

    op.drop_index('ix_pipeline_status_id', table_name='pipeline_status')
    op.drop_table('pipeline_status')

    op.drop_index('ix_lead_snapshots_company_name', table_name='lead_snapshots')
    op.drop_index('ix_lead_snapshots_domain', table_name='lead_snapshots')
    op.drop_index('ix_lead_snapshots_id', table_name='lead_snapshots')
    op.drop_table('lead_snapshots')
