# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

### Backend Development
- Start FastAPI server: `uvicorn backend.main:app --reload --port 8000`
- Install Python dependencies: `pip install -r backend/requirements.txt`
- Run database migrations: (Check schema_supabase.sql for Supabase PostgreSQL setup)
- Run specific pipeline stages: Use orchestrator.py or individual pipeline modules
- Activate virtual environment: `source backend/.venv/bin/activate` (Linux/Mac) or `backend\.venv\Scripts\activate` (Windows)

### Frontend Development
- Start Vite dev server: `npm run dev` (from frontend directory)
- Build for production: `npm run build` (from frontend directory)
- Preview production build: `npm run preview` (from frontend directory)
- Type checking: `npm run typecheck` (from frontend directory)
- Install frontend dependencies: `npm install` (from frontend directory)

### Environment Setup
- Backend: Create `backend/.env` with DATABASE_URL, GEMINI_API_KEY, EXA_API_KEY, SCRAPE_CREATORS_API_KEY, AIRTABLE_API_KEY
- Frontend: No additional env setup needed for basic development
- Environment example: Copy `.env.example` to `.env` and fill in values

## Architecture

### High-Level Structure
- **Backend**: Python/FastAPI application handling lead discovery, enrichment, scoring, and API endpoints
- **Frontend**: React/Vite/TypeScript UI for visualizing leads, managing settings, and monitoring pipelines
- **Utilities**: Shared utility functions in `backend/utils/`
- **Scheduler**: Background job scheduling in `backend/scheduler/`
- **Validation**: Data validation logic in `backend/validation/`

### Backend Components
- **main.py**: FastAPI entry point with lifespan events for APScheduler background jobs
- **models.py**: SQLAlchemy ORM models (LeadSnapshot, ScrapeLedger, etc.)
- **config.py**: Pydantic environment configuration
- **config_manager.py**: Runtime configuration management (recently updated)
- **database.py**: SQLAlchemy database session & engine setup
- **pipeline/**: Modular pipeline stages:
  - discovery.py: Exa AI & search discovery sweeps
  - enrichment.py: Company firmographics & job openings enrichment
  - icp_filter.py: Ideal Customer Profile gatekeeper filtering
  - filter_funnel.py: HTML trimming & keyword gating
  - scorer.py: Hybrid intent scoring & time-decay engine
  - dns_audit.py: MX, SPF, DKIM, DMARC deliverability audits
  - contact_extractor.py: Decision-maker contact resolution
  - social_classifier.py: LLM social post intent classifier
  - social_discovery.py: Social platform scrapers
  - orchestrator.py: Batch pipeline orchestration
  - streaming_orchestrator.py: Real-time streaming pipeline engine
- **routers/**: API endpoint handlers:
  - leads.py: Lead snapshots & search API
  - pipeline.py: Manual & batch pipeline trigger API
  - settings.py: ICP & Intent configuration API
  - social_posts.py: Social signals API
- **utils/**: Utility functions and helpers
- **scheduler/**: APScheduler background job implementations
- **validation/**: Data validation and integrity checking

### Frontend Components
- **src/App.tsx**: Main dashboard component & layout router
- **src/components/**: UI components (LeadTable, LeadDetailDrawer, PitcherMode, etc.)
- **src/lib/api.ts**: Frontend API client for backend communication
- **src/types/lead.ts**: TypeScript type contracts for lead data

### Data Flow
1. Background scheduler (APScheduler) or manual trigger initiates pipeline runs
2. Discovery phase finds companies via Exa AI, job boards, social platforms
3. ICP filtering reduces noise before expensive LLM operations
4. Enrichment adds firmographics, job openings, social signals
5. Scoring combines rule-based firmographics with LLM intent analysis
6. DNS audit checks deliverability
7. Contact extraction resolves decision-maker information
8. Results stored in database and served via API to frontend
9. Frontend displays leads with filtering, detail views, and outreach pitch generation

### Key Technologies
- **AI/LLM**: Google Gemini, Anthropic Claude for intent analysis
- **Discovery**: Exa AI (neural search), Python-JobSpy, Scrape Badger/Creators
- **NLP**: spaCy, RapidFuzz (fuzzy quote verification)
- **Infrastructure**: dnspython (DNS checks), APScheduler (background jobs)
- **Database**: SQLAlchemy 2.0 with SQLite (dev) / Supabase PostgreSQL (prod)
- **Frontend**: React 18, TypeScript, Vite, Tailwind CSS, Framer Motion