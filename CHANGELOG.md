# Changelog

All notable changes to the **Prospector AI / Project Heimdall** codebase will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

### Added
- **Aiven Cloud Kafka & Event Streaming Architecture**:
  - Integrated Aiven Cloud Kafka as the core event streaming bus (`kafka_service.py`), supporting `SASL_SSL` security protocol with `ssl.create_default_context()` TLS handshake configuration.
  - Implemented auto-retry connection loop (`while True`) in the background Kafka consumer (`consume_enrichment_events`) to gracefully handle missing topics or temporary broker rebalances.
  - **Kafka Topics & Telemetry Channels**:
    - `enrichment.requested`: Outbound trigger payload dispatched upon lead enrichment initialization.
    - `enrichment.completed`: Inbound callback payload consumed asynchronously when FullEnrich finishes contact resolution.
    - `lead.contacts.updated`: Telemetry event broadcasted across the system when a contact's email deliverability status is verified.
  - **Kafka & Streaming Environment Variables**:
    - `KAFKA_BOOTSTRAP_SERVERS` (`kafka-2b8b596a-courage9605-e047.j.aivencloud.com:10152`)
    - `KAFKA_SECURITY_PROTOCOL` (`SASL_SSL`)
    - `KAFKA_SASL_MECHANISM` (`PLAIN` / `SCRAM-SHA-256`)
    - `KAFKA_SASL_USER` (`avnadmin`)
    - `KAFKA_SASL_PASSWORD` (Aiven SASL secret token)
    - `PUBLIC_WEBHOOK_URL` (Public HTTPS callback target for FullEnrich webhook receivers)
- **FullEnrich Contact Intelligence & SSE Real-time Streaming**:
  - **Endpoints**: `POST /api/fullenrich/enrich` (enrichment trigger & decision-maker search), `GET /api/fullenrich/stream/{job_id}` (real-time SSE stream), `GET /api/fullenrich/status/{job_id}` (DB status fallback), and `POST /api/webhooks/fullenrich` (asynchronous webhook receiver).
  - **Frontend Integration**: Updated `ATSJobsView.tsx` and `api.ts` to export and prepend `API_BASE_URL` (`import.meta.env.VITE_API_BASE_URL`) to all Server-Sent Events (SSE) streaming connections (`${API_BASE_URL}/api/fullenrich/stream/${item.id}`) and POST triggers (`${API_BASE_URL}/api/fullenrich/enrich`), eliminating 404 errors on Vercel deployments.
- Added `Revenue` (`ARR est.`) 4th KPI card to **Company Insights $\rightarrow$ FIRMOGRAPHIC INSIGHTS** in `JobsTab.tsx`, displaying normalized annual revenue metrics matching reference layout.
- Added `event_date` field to `SignalModel` in `backend/routers/leads.py`, `backend/pipeline/scorer.py`, and `ExtractedSignal` in `frontend/src/types/lead.ts` for exact signal publication dates.
- Created `scratch/test_apify_ats_actors.py` test script to benchmark and compare two Apify ATS job scraper actors (`memo23/ats-jobs-scraper` and `fantastic-jobs/jobs-scraper`) for publication dates, JSON payload endpoints, and normalized dataset output.
- Created `scratch/test_lab23_exa.py` test script to query and audit raw Exa AI search outputs, timestamps, structured facts, and grounding citations for Lab 23 Technology (`lab23technology.com`).
- Created `scratch/test_live_exa_gemini_pipeline.py` live end-to-end integration test script connecting real Exa AI searches directly to live Gemini 2.5 Flash API inference with deterministic Python URL and date linking.
- Created `scratch/test_exa_url_date_linking.py` test script verifying deterministic Python linking of Exa canonical URLs and publication dates into final lead signal JSON payloads.
- Created `scratch/test_company_exa.py` test script configured for testing Exa AI output for a specific company (canonical identity, deep buying signals, structured financial/headcount facts schema, and similar company discovery) with CLI arguments and JSON export.
- Created `scratch/test_zyte_job_fetch.py` test script specifically configured to test Zyte's Automatic Extraction API (`https://api.zyte.com/v1/extract`) for a target company's career page (`Figma` on Greenhouse), saving complete extracted data to `scratch/zyte_extraction_output.json`.
- Added `ZYTE_API_KEY` configuration option to `ENV.md` and `backend/.env.example`.

- Updated ATS jobs frontend filtering in `frontend/src/components/ATSJobsView.tsx` to maintain active job requisitions within the 15–60 days open window and strictly exclude any roles older than 75 days.
- Changed ATS job drawer action button wording from `Apply Directly` to `Link` in `frontend/src/components/ATSJobDetailDrawer.tsx`.
- Refreshed ATS job query payload (`DEFAULT_SEARCH_PAYLOAD`) in `backend/routers/ats_jobs.py` with 5 tech roles: `Staff Software Engineer`, `Senior Frontend Engineer`, `Cloud Security Engineer`, `Data Platform Architect`, and `DevSecOps Engineer`.
- Added a discreet telemetry sync control in the footer of `Settings.tsx` (`Sync stream`) that triggers live lead discovery sweeps (`/api/pipeline/run-test`) with real-time status feedback.
- Implemented new Band & Recency-Driven Scoring Architecture (`Scoring1.pdf`) in `backend/pipeline/scorer.py`:
  - Deterministic chronological base bands: `< 2 weeks (95-100)`, `< 1 month (90-95)`, `< 1.5 months (85-90)`, `< 2 months (80-85)`, `< 3 months (75-80)`, `job in last 24h / stale 30-70d (75-80)`, `job 2-3d / stale 15-30d (70-75)`.
  - Base signal hierarchy prioritizing most recent non-job signal within 3 months, ensuring job postings only set base when no non-job signal exists.
  - Deterministic add-ons engine: supporting signals 1-2mo (`+3`), 2-3mo (`+2`), stale posts >3mo (`+1`), job timing (`+1` to `+2`), and job volume (`+2` to `+4`), with combined job cap (`max +4`) and global add-on cap (`max +6`).
  - Strict ceiling enforcement: base $<95$ cannot exceed 94 (reserving 95-100 strictly for $<2$w signals).
  - Hard overrides: layoffs / hiring freeze forced to `0`, "no agencies" / "direct applicants only" capped at `40`, and score $<70$ hidden from active dashboard.
  - Multi-tier LLM resiliency fallback: Gemini `gemini-2.5-flash` $\rightarrow$ Groq `oss-120b` $\rightarrow$ Groq `oss-20b` $\rightarrow$ deterministic rule-based parser.
- Created `scratch/test_new_scoring_engine.py` test suite verifying all PDF edge cases and worked examples.
- Updated Groq model in `backend/pipeline/scorer.py` and `backend/routers/leads.py` to `oss-120b`.
- Fixed frontend recency badge in `LeadDetailDrawer.tsx` which previously overrode all labels containing `"month"` (e.g. `6-12 months`, `12+ months`) to hardcoded `'< 1 month'`, restoring true backend labels and dynamic calculation from `event_date`.
- Fixed TypeScript interface for `Contact` in `frontend/src/types/lead.ts` by adding optional `linkedin_url` and `department` fields.
- Removed all hardcoded metric fallbacks across `JobsTab.tsx` and `LeadDetailDrawer.tsx`: Median Tenure now returns `N/A`, missing Revenue returns `Undisclosed`, missing headcount/growth returns `0`, department distribution defaults to `0` without fake numbers, and removed fabricated fallback signals from `LeadDetailDrawer.tsx`.

- Expanded ATS search queries in `DEFAULT_SEARCH_PAYLOAD` in `backend/routers/ats_jobs.py` to diverse high-intent roles (e.g. `Cybersecurity Engineer`, `Staff Backend Engineer`, `DevOps Engineer`, `Cloud Solutions Architect`, `Data Engineering Lead`, `Engineering Manager`) and increased batch capacity to 20 items per sweep.
- Added `fetchLatestATSJobs`, `triggerATSJobsFetch`, and `deleteATSJob` API helper functions to `frontend/src/lib/api.ts`.
- Removed all hardcoded fallback jobs from `ATSJobsView.tsx`, isolating purely backend-fetched ATS snapshots and adding an animated rotating loading spinner during fetching state.
- Fixed ATS jobs deduplication in `backend/routers/ats_jobs.py` from strict 1-job-per-company filtering to `(company, title, url)` multi-role tracking so all open positions from scanned companies are returned and displayed.
- Strictly isolated `ATSJobsView.tsx` to query only the dedicated ATS Job Portal table (`ats_job_snapshots` in the database via `/api/ats-jobs/latest`), decoupling general pipeline lead models while preserving the table UI layout, KPIs, and detail drawer.
- Fixed backend route `@router.get("/latest")` and `@router.get("")` in `backend/routers/ats_jobs.py` to always return all stored cumulative `ATSJobSnapshot` records from the database table.
- Redesigned `TrackedLeadsView.tsx` matching the reference wireframe layout: company header with avatar, `New lead` pill, external link, metadata pills row, 4 sub-tabs (`Signals`, `Company Insights`, `Jobs`, `Decision Makers`), mint green hero fit card (`bg-[#F2FBF6] border-[#D1F3E0]`), and `SIGNAL TIMELINE` card with blue square icons, and full white-theme compatibility (removing all pitch-black blocks).
- Reorganized navigation bar items in `Sidebar.tsx` and `App.tsx` to the exact order: **`Dashboard`**, **`Track Jobs`**, **`Saved Leads`** (and `Settings`), removing the temporary `Find leads` option.
- Configured deterministic Python linking in `backend/pipeline/scorer.py` and `backend/pipeline/streaming_orchestrator.py` so exact canonical URLs and `event_date` ISO timestamps are attached directly from Exa source metadata based on `source_post_index`, eliminating reliance on LLM date extraction.
- Assigned individual `[Sx]` source index tags to Exa structured facts mapped directly to their verified grounding citation URLs (e.g. news/expansion press releases) so structured signals always have exact, verifiable source URLs and publication dates.
- Added strict signal selection and deduplication rules to Gemini system instructions and Python post-processing in `backend/pipeline/scorer.py` to filter out redundant/overlapping quotes and constrain output to top 2-4 distinct, high-impact major buying triggers.
- Replaced blank square placeholders across the **Find leads** tab in `LeadTable.tsx` with attractive `Podcast` broadcast wave vector SVG icons for the hero badge, discovery buttons, and empty state container.
- Swapped navigation items order in `Sidebar.tsx` and `App.tsx` to: **`Dashboard`**, **`Find leads`**, **`Track leads`**, **`Track jobs`**, and **`Settings`**.
- Updated the loading action button label in `ATSJobsView.tsx` to **`Searching Leads...`** with an active spinning refresh indicator during Apify and AI sweeps.
- Configured the **Find leads** tab (`isPipelineTab`) in `LeadTable.tsx` with white-theme compatible styling matching the visual reference: mint header banner (`bg-[#F2FBF6] border-[#D1F3E0]`), `Ready to run` / `• Searching` status badge, square outline action buttons, and center empty state (`No leads yet`) with trigger search button.
- Reverted the **ATS Job Portal** UI in `ATSJobsView.tsx` matching the reference image layout: restored the top header with `ATS Job Portal` title, `Real-time ATS job scraping & executive hiring market intelligence synthesis.` subtitle, and `Fetch ATS Jobs` green gradient action button.
- Restored the **Executive Macro Hiring Summary** banner (`FormattedMistralSummary`) in `ATSJobsView.tsx` with structured multi-column market intelligence cards.
- Restored the **Mistral AI** executive macro summary generation and prompt (`generate_job_batch_summary`) in `backend/pipeline/mistral_service.py` and `backend/routers/ats_jobs.py`.
- Configured the **Headcount by Department** breakdown in `JobsTab.tsx` to display direct headcount numbers only instead of percentages, dynamically pulling real employee counts per department or calculating from the total headcount.
- Refactored the **"Only postings with a detected change show here — quiet ones stay tracked in the background"** subtitle in `JobsTab.tsx` into a highlighted callout badge with an indigo pulsing dot, bold highlighted header, and soft shadow styling.
- Added the **IT** field (`15.0%`, `#6366F1`) to the **Headcount by Department** donut chart and legend breakdown in `JobsTab.tsx`.
- Enhanced the font size, contrast, and container styling for the reasoning / change notes and section header under **Flagged — 15+ days active** in `JobsTab.tsx` with dedicated high-contrast pill cards (`text-slate-800 dark:text-zinc-100 font-semibold text-xs sm:text-[13px]`).
- Integrated custom rounded briefcase vector SVG with curved flap strap and center circular clasp for **Track jobs** / Job Search in `Sidebar.tsx` and `App.tsx` matching reference image specifications.
- Configured the searching state UI in `ATSJobsView.tsx` matching reference design: shows blue animated pulsing dot with `Searching` badge and `Searching...` button label with square icon during search sweeps.
- Configured exact SVGs and tab labels for the left sidebar in `Sidebar.tsx` and `App.tsx` matching reference design: `Dashboard` (`LayoutGrid`), `Find leads` (`Podcast`/broadcast signal icon), `Track jobs` (`Briefcase`), `Track leads` (`Bookmark`), and `Settings` (`SettingsIcon`).
- Configured the **Find leads** header bar in `ATSJobsView.tsx` with light/white-theme mint background (`bg-[#F2FBF6] border-[#D1F3E0]`), dark bold typography (`text-slate-900`), and light-themed button styles (`bg-white border-emerald-300 text-slate-800`), eliminating the hardcoded black bar in light mode.
- Configured **ATSJobsView.tsx** buttons and empty state elements with clean white-themed styling (`bg-white dark:bg-zinc-800 border-slate-200 text-slate-800`), fixing dark background boxes to match the light theme seamlessly.
- Hidden the **Social Signals** navigation item from the sidebar in `Sidebar.tsx` while preserving all underlying backend endpoints, databases, and schemas.
- Redesigned **ATSJobsView.tsx** to match the reference design: styled top banner in dark forest green (`bg-[#071D12] border-[#0D3823]`) with `Find leads` title, `Ready to run` badge, and trigger action button, added column sub-header filter bar (`COMPANY`, `SCORE`, `SIGNALS`, `WHY NOW`, `FILTER`), and created the matching dark empty state (`No leads yet`).
- Configured **Jobs tab** in `JobsTab.tsx` with a clean white-themed UI and white-themed badge pills (`bg-slate-100 dark:bg-zinc-800 border-slate-200`, soft amber and blue badges, and light square icons), strictly rendering dynamic jobs extracted from real company data without hardcoded phantom jobs.
- Redesigned the **Jobs tab** elements in `JobsTab.tsx` to match the exact visual reference: added segmented sections (`Just posted` $\le 14$ days with circular counter badges and `Flagged — 15+ days active` with `JD changed`, `Reposted`, and `40+ days active` badges and change notes), right-aligned days-open pills, and a background monitoring footer.
- Expanded **KEY TAKEAWAYS** in `JobsTab.tsx` to 4 meaningful insights (`No HR personnel found`, `Hiring focused on execution roles`, `Heavy Engineering concentration`, and `Positive headcount acceleration`).
- Separated **HEADCOUNT BY DEPARTMENT** and **KEY TAKEAWAYS** into two distinct side-by-side cards in `JobsTab.tsx`, displaying the 4 core department slices (`Engineering`, `Marketing`, `Business dev`, `Operations`) alongside key hiring insights with blue square badges.
- Updated **HIRING TREND (PAST 6 MONTHS)** chart in `JobsTab.tsx` with clean Y-axis ticks and short X-axis month markers matching visual specifications.
- Redesigned the **12-Month Headcount Trajectory** chart in `JobsTab.tsx` with smooth Catmull-Rom spline curves, thick electric blue line styling, solid circular node markers, soft gradient area fills, exact left Y-axis ticks, and bottom X-axis month labels matching reference specifications.
- Configured **Signal Timeline** recency badge in `LeadDetailDrawer.tsx` to display the `< 30 days` and `< 1 month` relative recency pattern matching the visual design.
- Refactored **FIRMOGRAPHIC INSIGHTS** top summary in `JobsTab.tsx` into a 4-column metric grid (`Total headcount`, `YoY headcount growth`, `Revenue`, `Median tenure`).
- Styled the **Score and Justification** hero card in `LeadDetailDrawer.tsx` (Signals tab) with a subtle mint-green background (`bg-[#F4FBF7] dark:bg-emerald-950/20 border-[#D3F2E1]`), bold emerald score display, `/ 100` indicator, and structured fit justification typography matching visual reference.
- Refactored `LeadDetailDrawer.tsx` signals view to a clean white-themed layout: redesigned the **Signal Timeline** into a border-divided list matching reference specs without the vertical axis line, featuring blue square badges, structured quote typography, and recency indicators.

### Removed
- Removed the **WHY NOW AND RECOMMENDED ANGLE** section and suggested opener target banner from `LeadDetailDrawer.tsx` (Signals tab).
- Removed the **Executive Macro Hiring Summary** banner and `FormattedMistralSummary` component from `ATSJobsView.tsx`.
- Disabled the Mistral AI macro hiring summary prompt in `backend/pipeline/mistral_service.py` and `backend/routers/ats_jobs.py` (`fetch_ats_jobs`), eliminating redundant LLM API calls and preventing token wastage.
- Removed the **Finding Summary** tab from `LeadDetailDrawer.tsx`, streamlining the drawer panel navigation into the 4 primary operational views: `Signals`, `Company Insights`, `Jobs`, and `Decision Makers`.
- Removed the **Growth & Hiring Signal Breakdown** category progress bars from `LeadDetailDrawer.tsx` to streamline the intelligence signals view.
- Configured custom width specs for side drawer panels: set `LeadDetailDrawer.tsx` (Companies page detail view) to **75% width** (`md:w-[75%]`) and `ATSJobDetailDrawer.tsx` (ATS Job Portal detail view) to **40% width** (`md:w-[40%]`).
- Simplified company pipeline job search cascade from a 3-tier system to a 2-tier system (**Apify Career Scraper → TheirStack** as the sole fallback), completely removing `fetch_company_jobs_serper` from `streaming_orchestrator.py`.
- Optimized mobile responsive padding and headcount donut breakdown grid across `JobsTab.tsx` and `LeadDetailDrawer.tsx`, expanding drawer panel to 75% width and stacking donut chart elements on tighter viewports to eliminate label overlaps.
- Implemented canonical company-level job deduplication (`get_canonical_company_key`) in `backend/routers/ats_jobs.py` (`fetch_ats_jobs` & `get_latest_ats_jobs`) and `ATSJobsView.tsx` (`filteredJobs`), stripping common corporate/tech suffixes (`AI`, `Inc`, `Corp`, `LLC`, `Tech`, etc.) to prevent duplicate job cards for the same company (e.g. `Eightfold AI` vs `Eightfold`).
- Configured default Apify search queries payload in `backend/routers/ats_jobs.py` (`queries: ["Software Engineer", "DevOps Engineer", "Machine Learning Engineer", "Cybersecurity Engineer", "Data Engineer"]`).
- Refactored `backend/routers/ats_jobs.py` (`fetch_ats_jobs` & `get_latest_ats_jobs`) to query and return cumulative deduplicated job snapshots across all past and new runs, ensuring historical job posts remain preserved and visible alongside newly fetched posts.
- Created `scratch/cleanup_undated_ats_jobs.py` database cleanup script and added `has_valid_date_posted` validation in `backend/routers/ats_jobs.py`, ensuring job posts lacking a valid `date_posted` field are purged and excluded from storage.
- Re-designed `SocialPostsView.tsx` cards UI to match the ATS Job Post cards UI (`p-5 rounded-3xl` glassmorphic cards, platform icon box, top header with company/author tag, badge row with platform, intent level, date, and `View Full Signal Details` footer link). Created `SocialPostDetailDrawer.tsx` (40% width slide-over detail panel) for inspecting social signals.
- Updated loading indicator text in `ATSJobsView.tsx` to `Loading ATS Job Postings...` (removed `from NeonDB` suffix).
- Updated company and platform brand logo containers across `SocialPostsView.tsx` and `ATSJobsView.tsx` to full circles (`w-10 h-10 rounded-full overflow-hidden`) with full `object-cover` scaling so logos seamlessly cover the entire circle badge.
- Separated `getHeaderTabIcon` in `SocialPostsView.tsx` with fixed `w-3.5 h-3.5 shrink-0` inline icons, ensuring platform filter tabs in the top header remain cleanly formatted while post cards display full circular logos.

### Removed
- Removed the **Research** action button (`Compass` button) from the header toolbar in `LeadDetailDrawer.tsx`.
- Removed the `- Apify + Mistral AI -` header badge from `ATSJobsView.tsx`.
- Removed the Search & Filter Controls bar (`Search by title, company, location...`, `Workplace`, `ATS` dropdowns) from `ATSJobsView.tsx` for a cleaner UI layout.

### Fixed
- Fixed graph width in `JobsTab.tsx` for both **12-Month Headcount Trajectory** and **Hiring Trend (Past 6 Months)**: applied `preserveAspectRatio="none"` and full-width X coordinate scaling (`w-full`, expanded margins from `x=60` to `x=790`), ensuring spline curves, gradient area fills, and grid lines stretch across 100% width of the card container without right-side whitespace gaps.
- Fixed recurring ATS job cards (e.g. `Eightfold AI`) resurfacing after deletion: created `DeletedATSJob` table model in `backend/models.py`, implemented company-wide cascade deletion across all stored snapshots in `backend/routers/ats_jobs.py` (`delete_ats_job`), and added permanent blacklist filtering in `fetch_ats_jobs` and `get_latest_ats_jobs` so deleted jobs and companies never reappear on page reloads or future fetch sweeps.
- Fixed text contrast invisibility in `LeadDetailDrawer.tsx` Score & Justification card under light theme mode: added specific `.score-banner-card` rules and inline style guards in `index.css` and `LeadDetailDrawer.tsx` to prevent global `html.light-theme p` / `html.light-theme h4` CSS resets from overriding light-colored text on dark green surfaces.
- Fixed JSX closing `div` tag mismatch in `LeadDetailDrawer.tsx` following the Score and Justification section redesign.
- Prepended `API_BASE_URL` (`import.meta.env.VITE_API_BASE_URL`) to `DELETE /api/ats-jobs/${jobId}` in `ATSJobsView.tsx`, resolving `404 Not Found` errors when attempting to delete ATS job cards in production deployment on Vercel.

### Added
- Implemented **ATS Job Search Portal** feature:
  - Created `ATSJobRun` and `ATSJobSnapshot` SQLAlchemy models in `backend/models.py` for NeonDB persistence.
  - Created `backend/pipeline/mistral_service.py` to generate executive macro hiring summaries using Mistral AI.
  - Created `backend/routers/ats_jobs.py` REST API (`/api/ats-jobs/fetch`, `/api/ats-jobs/latest`, `/api/ats-jobs/runs`) enforcing `$0.04` Apify cost guardrails.
  - Added **ATS Job Portal** sidebar navigation tab (`Briefcase` icon) in `Sidebar.tsx` and route handler in `App.tsx`.
  - Built `ATSJobsView.tsx` with one-click fetch button (`Fetch ATS Jobs`), clean executive summary cards, workplace/source filters, and job card grid.
  - Built `ATSJobDetailDrawer.tsx` slide-over drawer showing full job description, must-have/preferred qualifications, compensation, and direct application links.
  - Optimized Mistral AI prompt in `mistral_service.py` to produce a concise summary under 100 words (reduced `max_tokens` from 800 to 250 for token efficiency).
  - Stripped emojis and removed Budget Cap header badge in `ATSJobsView.tsx` for a clean corporate UI format.
  - Filtered out `Top In-Demand Tech Stacks & Skills`, `Seniority`, and `Strategic Insights` sections from the UI summary banner as requested.
  - Updated summary banner heading to `Executive Macro Hiring Summary` and repositioned Search & Filter Controls bar above the summary banner in `ATSJobsView.tsx`.
  - Prepended `API_BASE_URL` (`import.meta.env.VITE_API_BASE_URL`) to `/api/ats-jobs/latest` and `/api/ats-jobs/fetch` in `ATSJobsView.tsx`, preventing 404 errors when deployed on Vercel.
  - Updated default Apify payload in `backend/routers/ats_jobs.py` and `scratch/test_jobo_ats_jobs_api.py` to use exact JSON configuration (`posted_before: "30 days"`, `locations: [...]`).
  - Implemented `is_strict_us_location` and `is_posted_before_30_days` post-processing validation in `backend/routers/ats_jobs.py` to filter out non-US locations and enforce jobs posted before 30 days ago.
  - Added `date_posted` column to `ATSJobSnapshot` model in `backend/models.py` and auto-migration in `backend/main.py`.
  - Added formatted **Posted Date** badge (`<Calendar /> Posted: MMM DD, YYYY`) to both job cards in `ATSJobsView.tsx` and the slide-over panel in `ATSJobDetailDrawer.tsx` (strictly rendering when `job.date_posted` is present, avoiding fallback to DB insertion `created_at` timestamp).
  - Updated frontend branding logo in `Header.tsx`, `Sidebar.tsx` (desktop & mobile), and `index.html` favicon to use `/Lead Intelligence Logo.png` with transparent background container formatting.
  - Removed whitespace gap between desktop sidebar container and main workspace panel in `App.tsx` and `Sidebar.tsx`.
  - Fixed mobile drawer width overflow in `LeadDetailDrawer.tsx` and `ATSJobDetailDrawer.tsx` by scoping `min-w-[400px]` to `sm:min-w-[400px]` with `max-w-full overflow-x-hidden`.
  - Removed solid white background in `ATSJobsView.tsx`, making the page background transparent (`bg-transparent`) with glassmorphic cards (`backdrop-blur-md`) matching the application dark/glass design system.
- Created `scratch/test_verify_ats_job_dataflow.py` test script to verify full end-to-end data flow: Apify API (`jobo.world/ats-jobs-api`) -> Mistral AI Summary -> NeonDB Storage -> `GET /api/ats-jobs/latest` Dashboard Feed.
- Created `scratch/test_ping_backend_company_records.py` test script to query NeonDB directly and ping local FastAPI `/api/leads/` HTTP endpoint to inspect database company records.
- Created `scratch/test_jobo_ats_jobs_api.py` to test Apify actor `jobo.world/ats-jobs-api` with custom payload and cost capping guardrails (`maxTotalChargeUsd=0.04`, `maxItems=10`, `timeout=60`).
- Created `test_fetch_db.py` test script to inspect database records and export company lead snapshots to local JSON files (`company_record_<name>.json`).
- Created `backend/migrate_supabase_to_neon.py` to copy all historical lead snapshots, social posts, and pipeline statuses directly from Supabase PostgreSQL to Neon PostgreSQL.
- Created root `CHANGELOG.md` to track code modifications, updates, and releases.
- Created root `ENV.md` and `backend/.env.example` documenting all required and optional environment variables.
- Added workspace rule in `.agents/AGENTS.md` mandating automated updates to `CHANGELOG.md` and `ENV.md` on git changes.

### Changed
- Strengthened intent scoring recency decay multipliers in `scorer.py`: 3-6 months reduced to 0.35x, 6-12 months to 0.15x, and >12 months to 0.02x. Applied 40% penalty and hard cap of 55 for leads without fresh signals in the last 90 days.
- Updated nightly 2:00 AM UTC background cron quota (`daily_quota`) from 30 to 20 companies across `main.py`, `pipeline.py`, `streaming_orchestrator.py`, and `airtable_connector.py`.
- Removed all emojis from `README.md` for a clean, formal corporate documentation style.
### Fixed
- Added top-level `json` and `re` module imports to `backend/routers/leads.py` to resolve `NameError: name 'json' is not defined` inside `_clean_and_parse_json()`.
- Fixed OpenRouter/Groq JSON parsing error (`Invalid control character`) in `leads.py` by introducing `_clean_and_parse_json()` helper with `strict=False` and control character sanitization.
### Removed
- Removed Serper and Google Search feed endpoints (`fetch_serper_reddit`, `fetch_scrapecreators_google`) from `social_discovery.py`, while retaining ScrapeCreators (`fetch_scrapecreators_threads`) for Threads social feeds.
- Removed Google tab filter and Google brand icon from `SocialPostsView.tsx` on the frontend Social Media page.

---

## [1.0.0] - 2026-08-10

### Added
- Complete root `README.md` documentation covering system architecture, FastAPI backend, React/Vite frontend, pipeline components, and API reference.
- Updated `.gitignore` rules to ignore scratch test scripts, temporary JSON dumps, SQLite/PostgreSQL databases, and environment secret files.
- Remote Git repository setup pointed to `https://github.com/CreworkTeam/Project-Lead-Intelligence.git`.

### Changed
- Refactored project settings and database initialization with Supabase schema support and SQLite fallback.
- Standardized `LeadDetailResponse` payload interface between frontend TypeScript components and backend Pydantic models.

### Fixed
- Fixed background scheduler duplicate thread issues on FastAPI Uvicorn reloads using lifespan context management.
- Fixed timestamp backfilling for historical lead snapshots.
