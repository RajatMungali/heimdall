# Project Heimdall (Prospector AI) — Autonomous Lead Intelligence & Intent Scoring Platform

**Project Heimdall** (Prospector AI / Project Lead Intelligence) is an enterprise-grade, autonomous B2B lead discovery, intent scoring, and executive contact extraction platform. It identifies high-intent accounts through public intent triggers (hiring surges, funding, tech stack changes, social posts), scores them using hybrid LLM evaluation with quote verification, audits domain deliverability, and equips sales teams with actionable outreach intelligence.

---

## Key Features

- **Autonomous Multi-Source Discovery Sweeps**  
  Aggregates public intent signals across web search (Exa AI), job boards (JobSpy, Serper, NewsAPI), social platforms (LinkedIn, X/Twitter, Reddit via Scrape Badger/Creators), and Meta Ads.

- **ICP Gatekeeper & Funnel Optimization**  
  Applies strict Ideal Customer Profile (ICP) filters (employee headcount, funding stage, industry) before invoking LLM models—saving up to 80% on API costs while short-circuiting non-target leads.

- **Hybrid Lead Scoring & Verbatim Quote Verification**  
  Combines rule-based firmographics with LLM intent analysis. Uses fuzzy string matching (`RapidFuzz`) to validate raw evidence quotes against source material and calculates signal freshness using time-decay algorithms.

- **Domain Deliverability & DNS Infrastructure Audits**  
  Programmatically checks target domain MX, SPF, DKIM, and DMARC records to ensure cold outreach deliverability and identify misconfigured domains.

- **Executive Contact Extraction**  
  Resolves decision-maker handles, LinkedIn company IDs, bio links, and contact channels for immediate sales action.

- **High-Performance Command Center UI**  
  Built with React 18, TypeScript, Vite, Tailwind CSS, and Framer Motion:
  - **Live Lead Table**: Filter by ICP fit, intent score, tier, and company segment.
  - **Lead Detail Drawer & Pitcher Mode**: Generates AI outreach pitches and signal breakdowns.
  - **Social Intent Stream**: Real-time monitoring of founder posts matching intent keywords.
  - **Interactive Pipeline Modal**: Live visualization of multi-stage scanning and intent scoring.
  - **Tracked Leads & Settings**: Bookmark high-priority leads and customize ICP scoring thresholds.

- **Automated Scheduled Sweeps**  
  Integrated `APScheduler` background runner executes daily autonomous sweeps to refresh intent signals.

---

## Architecture & Tech Stack

### Backend
- **Framework**: Python 3.11, [FastAPI](https://fastapi.tiangolo.com/), Uvicorn
- **Database & ORM**: SQLAlchemy 2.0 with SQLite (local) / Supabase PostgreSQL (production)
- **AI & Data Enrichment**:
  - Google Gemini API (`google-genai`), Anthropic Claude
  - Exa AI (neural search & discovery)
  - Scrape Badger / Scrape Creators (social signal extraction)
  - spaCy (`en_core_web_sm`), RapidFuzz (fuzzy quote verification)
  - dnspython (DNS deliverability checks)
- **Scheduling**: APScheduler (cron background sweeps)

### Frontend
- **Framework**: React 18, TypeScript, Vite
- **Styling & UI**: Tailwind CSS, Framer Motion, Lucide Icons

---

## Repository Structure

```text
Project Heimdall/
├── backend/
│   ├── config.py                 # Pydantic environment configuration
│   ├── database.py               # SQLAlchemy database session & engine
│   ├── main.py                   # FastAPI server entry point & lifespan scheduler
│   ├── models.py                 # ORM database models (LeadSnapshot, ScrapeLedger, etc.)
│   ├── pipeline/
│   │   ├── discovery.py          # Exa AI & search discovery sweeps
│   │   ├── enrichment.py         # Company firmographics & job openings enrichment
│   │   ├── icp_filter.py         # ICP gatekeeper filter logic
│   │   ├── filter_funnel.py      # HTML trimming & keyword gating
│   │   ├── scorer.py             # Hybrid intent scoring & time-decay engine
│   │   ├── dns_audit.py          # MX, SPF, DKIM, DMARC deliverability audits
│   │   ├── contact_extractor.py  # Decision-maker contact resolution
│   │   ├── social_classifier.py # LLM social post intent classifier
│   │   ├── social_discovery.py  # Social platform scrapers
│   │   ├── streaming_orchestrator.py # Real-time streaming pipeline engine
│   │   └── orchestrator.py       # Batch pipeline orchestration
│   ├── routers/
│   │   ├── leads.py              # Lead snapshots & search API
│   │   ├── pipeline.py           # Manual & batch pipeline trigger API
│   │   ├── settings.py           # ICP & Intent configuration API
│   │   └── social_posts.py       # Social signals API
│   ├── requirements.txt          # Python dependencies
│   └── schema_supabase.sql       # PostgreSQL / Supabase migration schema
└── frontend/
    ├── src/
    │   ├── App.tsx               # Main dashboard component & layout router
    │   ├── components/           # UI components (LeadTable, LeadDetailDrawer, PitcherMode, etc.)
    │   ├── lib/api.ts            # Frontend API client
    │   └── types/lead.ts         # TypeScript type contracts
    ├── package.json              # Frontend dependencies & scripts
    └── vite.config.ts            # Vite proxy & build configuration
```

---

## Getting Started

### Prerequisites
- **Python 3.11+**
- **Node.js 18+** & **npm**

---

### Backend Setup

1. **Navigate to the root directory:**
   ```bash
   cd "Project Heimdall"
   ```

2. **Create and activate a virtual environment:**
   ```bash
   python -m venv venv
   # On Windows PowerShell:
   .\venv\Scripts\Activate.ps1
   # On macOS/Linux:
   source venv/bin/activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r backend/requirements.txt
   ```

4. **Configure Environment Variables:**
   Create a `backend/.env` file:
   ```env
   DATABASE_URL=sqlite:///./heimdall.db
   GEMINI_API_KEY=your_gemini_api_key
   EXA_API_KEY=your_exa_api_key
   SCRAPE_CREATORS_API_KEY=your_scrape_creators_api_key
   AIRTABLE_API_KEY=your_airtable_api_key
   ```

5. **Run the FastAPI server:**
   ```bash
   uvicorn backend.main:app --reload --port 8000
   ```
   The backend API will be available at `http://127.0.0.1:8000`.

---

### Frontend Setup

1. **Navigate to the frontend directory:**
   ```bash
   cd frontend
   ```

2. **Install npm dependencies:**
   ```bash
   npm install
   ```

3. **Start the Vite dev server:**
   ```bash
   npm run dev
   ```
   The UI will be available at `http://localhost:5173`. (API requests to `/api/*` are automatically proxied to port 8000).

---

## API Endpoints Reference

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/api/health` | Service health status & background scheduler telemetry |
| `GET` | `/api/leads` | List all processed lead snapshots with intent scores |
| `GET` | `/api/leads/{id}` | Retrieve detailed lead profile (signals, DNS audit, contacts) |
| `POST` | `/api/pipeline/run` | Execute discovery & scoring pipeline for a company |
| `POST` | `/api/pipeline/stream` | Stream real-time pipeline execution progress |
| `GET` | `/api/social-posts` | Fetch classified social post intent signals |
| `GET` | `/api/audit/dns?domain=...` | Programmatic DNS email deliverability check |
| `GET/POST`| `/api/settings/icp` | View or update Ideal Customer Profile configuration |
| `GET/POST`| `/api/settings/intent` | View or update intent keyword scoring triggers |

---

## License & Attributions

Built for **Crework Labs / CreworkTeam**. Internal proprietary project.
