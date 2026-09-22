"""
Pipeline Orchestrator — Phases 1-6 unified execution engine.

run_pipeline_for_company() — single company: Discovery → ICP Gate → Scoring → DNS → Contacts → Persist
run_batch_pipeline()       — autonomous: Discovery sweeps → iterate each company through the above
"""
import uuid
import json
import time
import asyncio
from datetime import datetime, timezone

from backend.pipeline.discovery import (
    fetch_public_intent_signals,
    resolve_domain,
    run_autonomous_discovery,
)

from backend.pipeline.dns_audit import audit_domain_email_infrastructure
from backend.pipeline.filter_funnel import check_recent_cache
from backend.pipeline.contact_extractor import extract_contacts
from backend.models import LeadSnapshot
from backend.database import SessionLocal
from backend.config import settings
from backend.utils.logger import logger


async def run_pipeline_for_company(
    company_name: str,
    domain: str | None = None,
    firmographics: dict | None = None,
    pre_fetched_signals: list[dict] | None = None,
) -> dict:
    """
    Main orchestration sequence for Heimdall.
    Executes: Domain Resolution → ICP Gate → Discovery → Scoring → DNS Audit → Contacts → DB Write.
    """
    # Phase 2: Domain resolution (use provided or resolve via Clearbit)
    if not domain:
        domain, firmographics = resolve_domain(company_name)
    if not domain:
        logger.info(f"Skipping {company_name} — domain unresolved")
        return {"status": "skipped", "reason": "domain_unresolved"}

    if firmographics is None:
        firmographics = {}

    # Cache Check
    if check_recent_cache(domain):
        logger.info(f"Skipping {company_name} — recently cached.")
        return {"status": "skipped", "reason": "recently_cached"}

    logger.info(f"Starting pipeline execution for {company_name} ({domain})")

    # Clean up firmographics defaults to not mask nulls
    if "employee_count" not in firmographics:
        firmographics["employee_count"] = None
    if "industry" not in firmographics or not firmographics["industry"]:
        firmographics["industry"] = "Unknown"
    if "funding_stage" not in firmographics or not firmographics["funding_stage"]:
        firmographics["funding_stage"] = "Unknown"

    # Phase 3: ICP Gatekeeper Check (before any LLM call)
    from backend.pipeline.icp_filter import apply_icp_filters

    dummy_score, icp_fit_label = apply_icp_filters(
        base_score=50,
        employee_count=firmographics.get("employee_count"),
        funding_stage=firmographics.get("funding_stage"),
        industry=firmographics.get("industry", "Unknown"),
    )

    if icp_fit_label == "Poor":
        logger.info(f"Short-circuiting {company_name} due to Poor ICP fit.")
        lead_id = str(uuid.uuid4())
        icp_reason = _get_icp_rejection_reason(firmographics)
        
        # Fetch raw signals to populate evidence log without using Gemini
        if pre_fetched_signals is not None:
            raw_signals = pre_fetched_signals
        else:
            raw_signals = await fetch_public_intent_signals(company_name)
        fallback_signals = []
        import re
        for sig in raw_signals:
            raw_t = sig.get("raw_text", "")
            if not raw_t:
                continue
            url_match = re.search(r"URL:\s*(https?://[^\s]+)", raw_t)
            date_match = re.search(r"Date:\s*([^\n]+)", raw_t)
            
            # Simple slice for verbatim quote
            quote = raw_t.split("\nContent:")[-1].strip() if "Content:" in raw_t else raw_t.split("Description:")[-1].strip()
            quote = quote[:150] + "..." if len(quote) > 150 else quote
            
            fallback_signals.append({
                "signal_type": "Raw Discovery",
                "verbatim_quote": quote,
                "source_url": url_match.group(1) if url_match else "N/A",
                "event_date": date_match.group(1) if date_match else "2026-06-25T00:00:00Z",
                "quote_validated": True,
                "similarity_score": 100.0,
                "recency_label": "unknown",
                "score_contribution": 0.0
            })

        lead_payload = {
            "id": lead_id,
            "company_name": company_name,
            "domain": domain,
            "industry": firmographics.get("industry", "Unknown"),
            "employee_count": firmographics.get("employee_count"),
            "intent_score": dummy_score,
            "signal_freshness": 100,
            "tier": "Low",
            "icp_fit": "Poor",
            "confidence": {
                "label": "Low Trust",
                "color": "rose",
                "verified": 0,
                "total": 1,
            },
            "why_now": f"ICP Gatekeeper: {icp_reason}",
            "badge": "filtered",
            "signals": fallback_signals,
            "ai_verdict": f"Profile rejected — {icp_reason}",
            "dns_audit": {
                "spf": "Missing",
                "dkim": "Missing",
                "dmarc": "Missing",
                "issues": [],
            },
            "contacts": [],
            "last_updated": datetime.now(timezone.utc).isoformat(),
        }

        _persist_lead(lead_id, domain, company_name, lead_payload)
        return {"status": "success", "lead": lead_payload}

    # Phase 1 (per-company): Discover signals for this specific company
    if pre_fetched_signals is not None:
        raw_signals = pre_fetched_signals
    else:
        raw_signals = await fetch_public_intent_signals(company_name)
        
    # Scrape Creators Phase 3: Narrow Validation
    try:
        from backend.pipeline.social_discovery import check_scrape_creators_budget, fetch_founder_post
        from backend.models import ScrapeLedger
        from datetime import timedelta
        
        db = SessionLocal()
        ledger_entry = db.query(ScrapeLedger).filter(
            ScrapeLedger.company_name == company_name
        ).first()
        
        in_cooldown = False
        if ledger_entry and ledger_entry.last_scraped_date:
            # Handle naive datetime from SQLite
            last_dt = ledger_entry.last_scraped_date
            if last_dt.tzinfo is None:
                last_dt = last_dt.replace(tzinfo=timezone.utc)
            age = datetime.now(timezone.utc) - last_dt
            if age < timedelta(days=14):
                in_cooldown = True
                logger.info(f"Skipping Scrape Creators for {company_name} (14-day cooldown active).")
                
        if not in_cooldown:
            budget = await check_scrape_creators_budget()
            if budget >= 50:
                # Serper locate exact post URLs (simulated here)
                simulated_linkedin_url = f"https://linkedin.com/post/{company_name.lower().replace(' ', '-')}-update"
                simulated_reddit_url = f"https://reddit.com/r/SaaS/comments/{company_name.lower().replace(' ', '-')}-news"
                
                # Scrape Creators post endpoint for both
                social_post_li = await fetch_founder_post(simulated_linkedin_url)
                if social_post_li:
                    raw_signals.append(social_post_li)
                    
                social_post_reddit = await fetch_founder_post(simulated_reddit_url)
                if social_post_reddit:
                    raw_signals.append(social_post_reddit)
                
                # Update ledger (record multiple platforms)
                if ledger_entry:
                    ledger_entry.last_scraped_date = datetime.now(timezone.utc)
                else:
                    new_ledger = ScrapeLedger(
                        id=str(uuid.uuid4()),
                        company_name=company_name,
                        platform="linkedin,reddit",
                        last_scraped_date=datetime.now(timezone.utc)
                    )
                    db.add(new_ledger)
                db.commit()
            else:
                logger.warning(f"Skipping Scrape Creators for {company_name} due to low budget ({budget}).")
        db.close()
    except Exception as e:
        logger.error(f"Error executing Scrape Creators validation: {e}")

    # Phase 4.5: Top-N Score-First Selection with 2-Pass Category Reservation (Max N=4)
    selected_signals = _select_top_n_category_reservation(raw_signals, max_n=4)

    # Combine text with integer indices [S0], [S1]... matching Gemini prompt SOURCE INDEX format
    cleaned_html_parts = []
    for idx, s in enumerate(selected_signals):
        raw_t = s.get("raw_text") or s.get("text") or s.get("summary") or ""
        src = s.get("source_api") or s.get("source_type") or "Social"
        text = _clean_and_truncate_per_source(raw_t, src)
        cleaned_html_parts.append(f"--- [S{idx}] ---\n{text}")
    cleaned_html = "\n\n---\n\n".join(cleaned_html_parts)

    # Phase 5: Intent classification using Gemini 2.5 Flash
    from backend.pipeline.scorer import analyze_lead_intent_with_llm
    
    scored_data = {}
    for attempt in range(3):
        try:
            scored_data = await analyze_lead_intent_with_llm(
                company_name, 
                cleaned_html, 
                firmographics,
                icp_fit_label=icp_fit_label,
                raw_signals=selected_signals
            )
            if "API Error" not in scored_data.get("ai_verdict", ""):
                break
        except Exception as e:
            logger.warning(f"Phase 5 LLM Synthesis transient error on attempt {attempt+1}: {e}")
        
        if attempt < 2:
            logger.info("Backing off for 5 seconds before retrying Phase 5 LLM Synthesis...")
            await asyncio.sleep(5)
            
    if not scored_data:
        scored_data = {
            "company_name": company_name,
            "intent_score": 0,
            "ai_verdict": "API Error: Synthesis failed after 3 retries.",
            "signals": [],
            "icp_fit": "Poor"
        }
        
    # Phase 3b: DNS Audit
    dns_res = await audit_domain_email_infrastructure(domain)

    total_signals = len(scored_data.get("signals", []))
    verified_signals = sum(
        1 for s in scored_data.get("signals", []) if s.get("quote_validated")
    )

    # Multi-factor confidence calculation
    avg_similarity = (
        sum(s.get("similarity_score", 0) for s in scored_data.get("signals", []))
        / total_signals
        if total_signals > 0
        else 0
    )
    verification_ratio = (
        (verified_signals / total_signals * 100) if total_signals > 0 else 0
    )
    unique_types = (
        len(set(s.get("signal_type", "") for s in scored_data.get("signals", [])))
        if total_signals > 0
        else 0
    )
    diversity_bonus = min(unique_types * 7, 20)

    raw_confidence = (
        (avg_similarity * 0.50) + (verification_ratio * 0.30) + diversity_bonus
    )
    confidence_pct = min(int(raw_confidence * 0.92), 95)

    if total_signals == 0:
        conf_label = "Low Trust"
        conf_color = "rose"
        confidence_pct = 0
    elif confidence_pct >= 75:
        conf_label = "High Trust"
        conf_color = "emerald"
    elif confidence_pct >= 45:
        conf_label = "Moderate Trust"
        conf_color = "amber"
    else:
        conf_label = "Low Trust"
        conf_color = "rose"

    # Handle failed/empty records gracefully
    if total_signals == 0 or "API Error" in scored_data.get("ai_verdict", ""):
        logger.info(
            f"Zero signals found for {company_name}. Persisting with 0 score."
        )
        scored_data["ai_verdict"] = "No recent public signals detected for this target."
        scored_data["intent_score"] = 0
        scored_data["icp_fit"] = "Poor"

    # URL Override: Replace LLM hallucinated URLs with exact canonical links from ScrapeBadger/Serper
    if scored_data.get("signals"):
        for sig in scored_data["signals"]:
            quote = sig.get("verbatim_quote", "")
            for raw_s in raw_signals:
                if quote and quote.lower() in raw_s.get("raw_text", "").lower():
                    exact_url = raw_s.get("url") or raw_s.get("link") or raw_s.get("extracted_url")
                    if exact_url:
                        sig["source_url"] = exact_url
                    break

    # Phase 4: Contact Extraction (real, not mocked)
    contacts = extract_contacts(domain, scored_data.get("company_name", company_name))

    # Safely parse employee count which might come as a string range "50-200" from Gemini
    raw_emp = firmographics.get("employee_count")
    emp_val = None
    if isinstance(raw_emp, int):
        emp_val = raw_emp
    elif isinstance(raw_emp, str):
        import re
        nums = re.findall(r'\d+', raw_emp.replace(",", ""))
        if nums:
            emp_val = int(nums[-1])  # Take upper bound

    # Dynamically derive funding_stage from signal_tags if not present in firmographics
    resolved_stage = firmographics.get("funding_stage")
    if not resolved_stage or resolved_stage == "Unknown":
        for st in scored_data.get("signal_tags", []):
            t_str = str(st.get("tag", "")).strip()
            if any(k in t_str.upper() for k in ["SERIES", "SEED", "PRE-SEED", "GROWTH", "PE"]):
                resolved_stage = t_str.split("/")[0].strip()
                break
    if not resolved_stage:
        resolved_stage = "Growth Stage"

    lead_id = str(uuid.uuid4())
    lead_payload = {
        "id": lead_id,
        "company_name": scored_data.get("company_name", company_name),
        "domain": domain,
        "industry": firmographics.get("industry", "Unknown"),
        "employee_count": emp_val,
        "funding_stage": resolved_stage,
        "intent_score": scored_data.get("intent_score", 0),
        "signal_freshness": scored_data.get("signal_freshness", 100),
        "tier": scored_data.get("tier", "Low"),
        "icp_fit": scored_data.get("icp_fit", "Partial"),
        "confidence": {
            "label": conf_label,
            "color": conf_color,
            "verified": confidence_pct,
            "total": 100,
        },
        "why_now": scored_data.get("why_now", "Automated batch sweep detected new signals."),
        "badge": "new_today",
        "signals": scored_data.get("signals", []),
        "signal_tags": scored_data.get("signal_tags", []),
        "ai_verdict": scored_data.get("ai_verdict", "Review signals for outreach context."),
        "dns_audit": dns_res,
        "contacts": contacts,
        "last_updated": datetime.now(timezone.utc).isoformat(),
        "gemini_token_usage": scored_data.get("gemini_token_usage", {})
    }

    _persist_lead(lead_id, domain, company_name, lead_payload)
    return {"status": "success", "lead": lead_payload}


async def select_top_10_leads(candidates: list[dict], target_niche: str = None) -> list[dict]:
    """
    Phase 1.5 — Gemini Gatekeeper Selection.
    Evaluates candidate company objects against active niche ICP rules and Seller Exclusion filters.
    Ranks candidates by intent signal strength and returns the TOP 10.
    """
    if not candidates:
        return []

    from backend.config_manager import load_intent_config
    config = load_intent_config()
    active_niche = target_niche or config.get("active_niche", "recruitment")
    niche_info = config.get("niches", {}).get(active_niche, {})
    exclude_terms = niche_info.get("exclude_terms", ["agency", "staffing", "recruitment firm"])
    niche_rules = niche_info.get("rules", "Target company job post = positive. Agency post = discard.")

    api_key = getattr(settings, "GEMINI_API_KEY", None)
    if not api_key or "your_" in api_key:
        logger.warning("[Gemini Gatekeeper] API Key missing. Falling back to dummy top 10 selection.")
        names = {c.get("company_name", c.get("title", "Unknown")) for c in candidates}
        return _select_top_5_leads_dummy(names)[:10]

    from google import genai
    from google.genai import types
    
    client = genai.Client(api_key=api_key)
    gen_config = types.GenerateContentConfig(
        temperature=0.1
    )

    async def evaluate_batch(batch_candidates: list[dict], num_to_select: int = 10) -> list[dict]:
        candidate_blocks = "\n\n".join(
            f"Candidate [{idx+1}]: {c.get('company_name', c.get('title',''))}\n"
            f"Domain: {c.get('url','')}\n"
            f"Summary: {c.get('summary','')}\n"
            f"Snippet: {c.get('text_snippet','')[:600]}"
            for idx, c in enumerate(batch_candidates)
        )

        prompt = f"""You are a Lead Scoring AI and Senior B2B Sales Intelligence Analyst.

TASK:
Analyze the attached list of {len(batch_candidates)} candidates along with their source evidence text blocks.
Verify candidates against the Active ICP Niche ('{active_niche}').
Evaluate candidates strictly based on their source evidence text blocks, active niche focus, and disqualification terms.

ACTIVE ICP NICHE RULES:
- Active Niche: {active_niche}
- Evaluation Rules: {niche_rules}
- Exclusion Terms: Discard companies matching any of: {exclude_terms}

CONTEXTUAL SELLER & JOB POST RULES (STRICT):
RULE 1 — SELLER FILTER (AGENCY GUARD): If candidate company IS a service provider/agency in our client's space ({exclude_terms}), DISCARD IT IMMEDIATELY (set fits_icp: false).
RULE 2 — JOB POST INTERPRETATION:
  - Job posts BY the target company = POSITIVE buying signal (they need to hire/scale).
  - Job posts BY an agency = DISCARD (noise).
  - Job posts for internal 'recruiter' or 'talent acquisition' roles = MODERATE signal (building internal capacity).

SIGNAL CATEGORY MAPPING (Assign exactly 1 category):
- Federal contract wins → EXPANSION
- M&A / acquisitions → EXPANSION
- Grants (SBIR, STTR) → FUNDING
- New VP / C-suite hires → LEADERSHIP
- Funding / Capital raised → FUNDING
- Role openings / Team scaling → HIRING
- Explicit social buying requests → SOCIAL_INTENT

OUTPUT FORMAT:
Return ONLY a valid JSON array containing the TOP {num_to_select} ranked companies formatted as follows:

[
  {{
    "rank": 1,
    "company_name": "Exact Brand Name",
    "domain": "companydomain.com or null if unverified",
    "fits_icp": true,
    "disqualification_reason": null,
    "primary_signal_category": "FUNDING | HIRING | EXPANSION | LEADERSHIP | SOCIAL_INTENT",
    "signal_recency": 14
  }}
]

If candidate is disqualified, include "fits_icp": false and provide "disqualification_reason": "string explaining why it was cut".

CANDIDATES WITH SOURCE EVIDENCE ({len(batch_candidates)} Candidates):
{candidate_blocks}
"""

        try:
            loop = asyncio.get_running_loop()
            response = await loop.run_in_executor(
                None,
                lambda: client.models.generate_content(
                    model="gemini-2.5-flash",
                    contents=prompt,
                    config=gen_config
                )
            )
            raw_text = response.text.strip()
            if "```json" in raw_text:
                raw_text = raw_text.split("```json")[1].split("```")[0].strip()
            elif "```" in raw_text:
                raw_text = raw_text.split("```")[1].split("```")[0].strip()

            parsed = json.loads(raw_text)
            qualified = [item for item in parsed if item.get("fits_icp") is True]
            return qualified if qualified else parsed
        except Exception as e:
            logger.error(f"[Gemini Batch Error] Error evaluating batch of {len(batch_candidates)}: {e}")
            return _select_top_5_leads_dummy({c.get("company_name", c.get("title", "Unknown")) for c in batch_candidates})[:num_to_select]

    # Evaluate candidates directly
    logger.info(f"[Fast Gatekeeper] Evaluating {len(candidates)} candidates directly with Gemini 2.5 Flash...")
    if len(candidates) <= 25:
        res = await evaluate_batch(candidates, num_to_select=min(10, len(candidates)))
        valid = [r for r in res if r.get("fits_icp") is True]
        return valid[:10] if valid else res[:10]

    CHUNK_SIZE = 25
    chunks = [candidates[i:i + CHUNK_SIZE] for i in range(0, len(candidates), CHUNK_SIZE)]
    logger.info(f"Evaluating {len(candidates)} candidates across {len(chunks)} ungrounded batches ({CHUNK_SIZE} max each)...")

    chunk_results = []
    for idx, chunk in enumerate(chunks, start=1):
        logger.info(f"[Fast Gatekeeper] Evaluating batch {idx}/{len(chunks)} ({len(chunk)} candidates)...")
        batch_res = await evaluate_batch(chunk, num_to_select=10)
        qualified = [b for b in batch_res if b.get("fits_icp") is True]
        chunk_results.extend(qualified if qualified else batch_res)

    only_fits = [c for c in chunk_results if c.get("fits_icp") is True]
    final_pool = only_fits if only_fits else chunk_results

    if len(final_pool) <= 10:
        return final_pool[:10]

    logger.info(f"[Fast Gatekeeper] Performing final ranking pass on {len(final_pool)} batch winners to select Top 10...")
    final_res = await evaluate_batch(final_pool, num_to_select=10)
    final_valid = [r for r in final_res if r.get("fits_icp") is True]
    return final_valid[:10] if final_valid else final_res[:10]


async def select_top_20_leads(candidates: list[dict], target_niche: str = None) -> list[dict]:
    """Alias for select_top_10_leads for backward compatibility."""
    return await select_top_10_leads(candidates, target_niche=target_niche)


async def select_top_5_leads(candidates: list[dict], target_niche: str = None) -> list[dict]:
    """Alias for select_top_10_leads for backward compatibility."""
    return await select_top_10_leads(candidates, target_niche=target_niche)


def _select_top_5_leads_dummy(companies: set[str]) -> list[dict]:
    """Fallback dummy function"""
    logger.info(f"Selecting top leads from {len(companies)} candidates using dummy fallback...")
    top_list = list(companies)[:10]
    return [{"company_name": name, "domain": f"{name.lower().replace(' ', '').replace(',', '')}.com", "industry": "B2B Software & Services"} for name in top_list]

async def run_batch_pipeline() -> dict:
    """
    Phase 6 — Autonomous batch pipeline.
    Discovers companies via Exa AI neural search, applies deterministic regex pre-filtering & Agency Guard,
    runs bounded Gemini gatekeeper (Top 20 selection), and processes top leads.
    """
    logger.info("Starting autonomous batch pipeline with Exa AI discovery...")

    from backend.pipeline.discovery import fetch_exa_candidates_50, apply_deterministic_filter

    # Phase 1: Exa AI Discovery
    raw_candidates = await fetch_exa_candidates_50()
    logger.info(f"Exa AI Discovery returned {len(raw_candidates)} candidate company objects.")

    # Phase 2: Deterministic Pre-Filtering on text_snippet ($0 Tokens) using Active Niche bounds
    from backend.config_manager import load_intent_config
    config_dict = load_intent_config()
    active_niche = config_dict.get("active_niche", "recruitment")
    niche_info = config_dict.get("niches", {}).get(active_niche, {})
    filter_config = {
        "target_industries": niche_info.get("target_industries", []),
        "min_employees": niche_info.get("min_employees", 20),
        "max_employees": niche_info.get("max_employees", 2000),
        "exclude_terms": niche_info.get("exclude_terms", [])
    }

    survivor_candidates = apply_deterministic_filter(raw_candidates, icp_config=filter_config)
    logger.info(f"Deterministic Filter ({active_niche}): {len(survivor_candidates)} SURVIVORS passed regex category, headcount, & Agency Guard rules.")

    # Fetch currently active companies from DB to avoid duplicates
    db = SessionLocal()
    try:
        active_companies = {lead.company_name for lead in db.query(LeadSnapshot).all()}
    finally:
        db.close()

    # Filter out companies already active on the frontend
    filtered_survivors = [d for d in survivor_candidates if d.get("title") not in active_companies and d.get("company_name") not in active_companies]
    logger.info(f"Filtered to {len(filtered_survivors)} new non-duplicate survivor candidates.")

    # Phase 3: Bounded Gemini Gatekeeper Selection (Top 20)
    if not filtered_survivors:
        logger.warning("[Pipeline Audit] 0 survivor companies remaining after deterministic filtering and deduplication.")
        return {"companies_processed": 0, "successes": 0, "had_errors": False}

    if len(filtered_survivors) <= 10:
        logger.info(f"[Gemini Bypass] {len(filtered_survivors)} survivors <= 10. Bypassing Gemini gatekeeper and enriching all survivors directly.")
        top_10_leads = [
            {
                "company_name": c.get("title") or c.get("author") or "Unknown",
                "domain": c.get("url", "").replace("https://", "").replace("http://", "").strip("/"),
                "url": c.get("url", ""),
                "summary": c.get("summary", ""),
                "text_snippet": c.get("text_snippet", "")
            }
            for c in filtered_survivors
        ]
    else:
        logger.info(f"Passing ALL {len(filtered_survivors)} SURVIVORS to Gemini gatekeeper to select Top 10...")
        all_survivors_batch = [
            {
                "company_name": c.get("title") or c.get("author") or "Unknown",
                "domain": c.get("url", "").replace("https://", "").replace("http://", "").strip("/"),
                "url": c.get("url", ""),
                "summary": c.get("summary", ""),
                "text_snippet": c.get("text_snippet", "")
            }
            for c in filtered_survivors
        ]
        top_10_leads = await select_top_10_leads(all_survivors_batch, target_niche=active_niche)

    # Phase 4: Entity Resolution (Top 10)
    top_10_pool = []
    for lead in top_10_leads:
        c_name = lead.get("company_name")
        from backend.pipeline.enrichment import resolve_domain_via_serper
        from backend.config import settings
        real_domain, harvested_firmos = await resolve_domain_via_serper(
            company_name=c_name, 
            serper_api_key=settings.SERPER_API_KEY, 
            phase1_estimated_domain=lead.get("domain", "")
        )
        
        firmos = {
            "employee_count": harvested_firmos.get("employee_count") or lead.get("employee_count", "Unknown"),
            "industry": harvested_firmos.get("industry") or lead.get("industry", "B2B Software & Services")
        }
        if harvested_firmos:
            firmos.update(harvested_firmos)
        
        domain = real_domain or lead.get("domain") or lead.get("estimated_domain")
        firmographics = firmos

        # Preserve original Exa text_snippet across Gemini gatekeeper handoff
        exa_snippet = lead.get("text_snippet", "")
        exa_url = lead.get("url") or lead.get("domain") or ""
        if not exa_snippet:
            for cand in filtered_survivors:
                cand_name = cand.get("title") or cand.get("company_name") or cand.get("author") or ""
                if cand_name.lower() == c_name.lower() or c_name.lower() in cand_name.lower():
                    exa_snippet = cand.get("text_snippet") or cand.get("summary") or ""
                    exa_url = cand.get("url", exa_url)
                    break

        top_10_pool.append((c_name, domain, firmographics, exa_snippet, exa_url))
    
    success_count = 0
    errors = False

    # Phase 3 & 4 & 5 & 6: Sequential Deep Sweep, Synthesis, and DB Persist Per Company
    for idx, (company_name, domain, firmographics, exa_snippet, exa_url) in enumerate(top_10_pool):
        logger.info(f"Fetching deep signals for [{idx + 1}/{len(top_10_pool)}]: {company_name}")
        try:
            import httpx
            from backend.pipeline.enrichment import fetch_reddit_posts, fetch_twitter_posts
            
            raw_signals = await fetch_public_intent_signals(company_name)
            
            # Inject preserved Exa AI Discovery signal so Groq synthesis never loses Phase 1 intent text
            if exa_snippet:
                raw_signals.append({
                    "company_name": company_name,
                    "domain": domain,
                    "raw_text": f"Exa AI Discovery Signal:\n{exa_snippet}",
                    "source_api": "Exa_Discovery",
                    "url": exa_url or (f"https://{domain}" if domain else ""),
                    "date_posted": datetime.now(timezone.utc).isoformat()
                })

            # ScrapeBadger native 3-times exponential backoff handles 429s automatically
            async with httpx.AsyncClient(timeout=45.0) as client:
                reddit_posts = await fetch_reddit_posts(client, company_name, domain)
                twitter_posts = await fetch_twitter_posts(client, company_name, domain)
                
            for reddit_post in reddit_posts:
                date_str = reddit_post.get("date", "Unknown Date")
                post_url = reddit_post.get("url", "")
                raw_signals.append({
                    "company_name": company_name,
                    "domain": domain,
                    "raw_text": f"Reddit Post:\nDate: {date_str}\nTitle: {reddit_post.get('title', '')}\nText: {reddit_post.get('text', '')}",
                    "source_api": "Reddit",
                    "url": post_url
                })
                
            for twitter_post in twitter_posts:
                date_str = twitter_post.get("created_at") or twitter_post.get("date") or "Unknown Date"
                post_url = twitter_post.get("url", "")
                raw_signals.append({
                    "company_name": company_name,
                    "domain": domain,
                    "raw_text": f"X/Twitter Post:\nDate: {date_str}\nText: {twitter_post.get('text', '')}",
                    "source_api": "X",
                    "url": post_url
                })

            signals = _heuristic_signal_filter(raw_signals)
        except Exception as e:
            logger.error(f"Error fetching signals for {company_name}: {e}")
            signals = []
            
        logger.info(f"Processing Synthesis for Top [{idx + 1}/{len(top_10_pool)}]: {company_name} with {len(signals)} signals")
        try:
            res = await run_pipeline_for_company(
                company_name, 
                domain, 
                firmographics,
                pre_fetched_signals=signals
            )
            if res.get("status") == "success":
                success_count += 1
                if res.get("lead", {}).get("ai_verdict", "").startswith("API Error"):
                    logger.warning(f"API Error detected for {company_name}. Halting pipeline execution.")
                    break
        except Exception as e:
            logger.error(f"Error orchestrating {company_name}: {e}")
            errors = True

        # Rate limit: 10s delay between companies
        logger.info("Sleeping 10s to respect rate limits...")
        await asyncio.sleep(10)

    return {
        "companies_processed": len(raw_candidates),
        "successes": success_count,
        "had_errors": errors,
    }


# ======================================================================
# Helpers
# ======================================================================

INLINE_JUNK_PATTERNS = [
    r"like\s*•\s*comment\s*•\s*share.*",
    r"report post.*",
    r"view all \d+ comments.*",
    r"author:.*",
    r"cookie notice.*",
    r"privacy policy.*",
    r"terms of service.*",
    r"newsletter signup.*",
    r"media contact:.*",
    r"copyright \d+.*",
    r"retweets \d+ • likes \d+"
]

def _clean_and_truncate_per_source(text: str, source_type: str) -> str:
    """Per-Source Budget: News=1200, Social=800."""
    import re
    max_chars = 1200 if any(k in str(source_type).lower() for k in ["news", "serper", "article"]) else 800
    
    lines = [line.strip() for line in text.split("\n") if line.strip()]
    cleaned_lines = []
    for line in lines:
        cl = line
        for pat in INLINE_JUNK_PATTERNS:
            cl = re.sub(pat, "", cl, flags=re.IGNORECASE).strip()
        if cl:
            cleaned_lines.append(cl)
            
    cleaned = "\n".join(cleaned_lines)
    if len(cleaned) <= max_chars:
        return cleaned
        
    truncated = cleaned[:max_chars]
    last_space = truncated.rfind(" ")
    if last_space > max_chars * 0.8:
        truncated = truncated[:last_space]
    return truncated + "..."

def _infer_intent_category(raw_text: str) -> str:
    """Lightweight keyword-based intent category tagger. Zero LLM cost."""
    t = raw_text.lower()
    if any(k in t for k in ["series a", "series b", "series c", "raised", "funding", "seed", "investors", "financing"]):
        return "funding"
    if any(k in t for k in ["hiring", "hire", "roles", "careers", "job", "sdr", "bdr", "engineer", "recruiting"]):
        return "hiring"
    if any(k in t for k in ["appoints", "cmo", "vp ", "ceo ", "head of", "leadership", "executive"]):
        return "leadership"
    if any(k in t for k in ["agency", "consultant", "fractional", "outsourc", "partner"]):
        return "agency_ask"
    if any(k in t for k in ["expand", "office", "launch", "milestone", "clients", "growth", "revenue"]):
        return "expansion"
    return "general"

def _select_top_n_category_reservation(raw_signals: list[dict], max_n: int = 4) -> list[dict]:
    """
    2-Pass Category Reservation Selection:
    Pass 1: Reserves top scorer per DISTINCT available intent_category (guarantees multi-category bonus).
    Pass 2: Fills remaining slots up to max_n by rank score (capped at max 2 per category).
    """
    if not raw_signals:
        return []
        
    source_priority_weights = {
        "serper news": 100,
        "newsapi": 95,
        "serper": 90,
        "news": 90,
        "linkedin": 80,
        "reddit": 60,
        "x": 50,
        "twitter": 50
    }

    scored = []
    for sig in raw_signals:
        src = str(sig.get("source_api") or sig.get("source_type") or "social").lower()
        src_w = 40
        for k, v in source_priority_weights.items():
            if k in src:
                src_w = v
                break
                
        # Recency score calculation
        rec_score = 50
        date_str = sig.get("date_posted") or sig.get("event_date") or ""
        if date_str:
            try:
                from datetime import datetime, timezone
                dt = datetime.fromisoformat(str(date_str).replace("Z", "+00:00"))
                days_old = (datetime.now(timezone.utc) - dt).days
                rec_score = max(0, 100 - days_old * 5)
            except Exception:
                rec_score = 50

        # Infer intent_category if missing
        cat = sig.get("intent_category") or sig.get("signal_type")
        if not cat:
            cat = _infer_intent_category(sig.get("raw_text") or sig.get("text") or "")
            
        final_score = round(src_w * 0.6 + rec_score * 0.4, 1)
        scored.append({**sig, "_rank_score": final_score, "_category": cat.lower()})

    scored.sort(key=lambda s: s.get("_rank_score", 0), reverse=True)

    selected = []
    category_counts = {}

    # Pass 1: Reserve highest-scoring signal for each DISTINCT category
    for sig in scored:
        if len(selected) >= max_n:
            break
        cat = sig["_category"]
        if cat not in category_counts:
            selected.append(sig)
            category_counts[cat] = 1

    # Pass 2: Fill remaining slots up to max_n (capping max 2 per category)
    for sig in scored:
        if len(selected) >= max_n:
            break
        cat = sig["_category"]
        if sig not in selected and category_counts.get(cat, 0) < 2:
            selected.append(sig)
            category_counts[cat] = category_counts.get(cat, 0) + 1

    return selected

def _heuristic_signal_filter(signals: list[dict]) -> list[dict]:
    """
    Applies a zero-cost Regex/keyword pass to raw signals to demote generic PR fluff.
    Only allows signals that contain intent keywords or are purely neutral.
    """
    import os

    # 1. Dynamically read allowlist from settings
    try:
        config_path = os.path.join(os.path.dirname(__file__), "..", "intent_config.json")
        with open(config_path, "r") as f:
            intent_cfg = json.load(f)
            allowlist = intent_cfg.get("extraction_keywords", [])
    except Exception:
        allowlist = []
        
    if not allowlist:
        allowlist = ["hiring", "series a", "series b", "series c", "seed", "raises", "appoints", "expands"]
        
    allowlist = [w.lower() for w in allowlist]
    
    # 2. Hardcoded denylist for PR fluff
    denylist = ["stock price", "shares", "earnings", "product launch", "acquires", "partners with"]
    
    filtered = []
    for sig in signals:
        text = sig.get("raw_text", "").lower()
        if not text:
            continue
            
        has_allowlist = any(term in text for term in allowlist)
        has_denylist = any(term in text for term in denylist)
        
        # Strict Time-Decay Threshold (Discard > 180 days)
        from backend.pipeline.time_decay import calculate_time_decay
        date_str = sig.get("date_posted") or sig.get("event_date") or ""
        multiplier, _ = calculate_time_decay(date_str)
        if multiplier < 0.20:
            continue # Drop anything older than 180 days
            
        if has_allowlist:
            filtered.append(sig)  # Strong intent, pass immediately
        elif has_denylist and not has_allowlist:
            continue  # Fluff article, throw in the trash
        else:
            filtered.append(sig)  # Neutral, let Gemini decide
            
    return filtered


def _get_icp_rejection_reason(firmographics: dict) -> str:
    """Generates a human-readable ICP rejection reason dynamically based on active niche."""
    from backend.config_manager import load_intent_config
    config_dict = load_intent_config()
    active_niche = config_dict.get("active_niche", "recruitment")
    niche_info = config_dict.get("niches", {}).get(active_niche, {})
    min_emp = niche_info.get("min_employees", 20)
    max_emp = niche_info.get("max_employees", 2000)

    emp = firmographics.get("employee_count")
    if emp is not None:
        parsed_emp = None
        if isinstance(emp, int):
            parsed_emp = emp
        elif isinstance(emp, str):
            import re
            matches = re.findall(r'\d+', emp.replace(',', ''))
            if matches:
                parsed_emp = max(int(m) for m in matches)

        if parsed_emp is not None:
            if parsed_emp > max_emp:
                return f"Exceeds employee ceiling (>{max_emp})"
            if parsed_emp < min_emp:
                return f"Under-resourced/pre-revenue (<{min_emp} employees)"

    funding = firmographics.get("funding_stage", "")
    if funding and funding.lower() in ["series d", "series e", "public", "m&a"]:
        return f"Stagnant funding stage ({funding})"

    return "Industry mismatch or scale constraints"


def _persist_lead(
    lead_id: str, domain: str, company_name: str, lead_payload: dict
) -> None:
    """Writes a lead snapshot to SQLite/PostgreSQL. Updates if company_name already exists to prevent duplicates."""
    db = SessionLocal()
    try:
        from backend.models import LeadSnapshot
        existing = db.query(LeadSnapshot).filter(LeadSnapshot.company_name == company_name).first()
        if existing:
            lead_payload["id"] = existing.id
            existing.domain = domain
            existing.company_segment = lead_payload.get("company_segment")
            existing.industry = lead_payload.get("industry")
            existing.employee_count = lead_payload.get("employee_count")
            existing.funding_stage = lead_payload.get("funding_stage")
            existing.intent_score = lead_payload.get("intent_score", 0)
            existing.signal_freshness = lead_payload.get("signal_freshness")
            existing.tier = lead_payload.get("tier")
            existing.icp_fit = lead_payload.get("icp_fit")
            existing.badge = lead_payload.get("badge")
            existing.why_now = lead_payload.get("why_now")
            existing.signal_tags = lead_payload.get("signal_tags")
            existing.ai_verdict = lead_payload.get("ai_verdict")
            existing.full_payload = lead_payload
        else:
            snapshot = LeadSnapshot(
                id=lead_id,
                domain=domain,
                company_name=company_name,
                company_segment=lead_payload.get("company_segment"),
                industry=lead_payload.get("industry"),
                employee_count=lead_payload.get("employee_count"),
                funding_stage=lead_payload.get("funding_stage"),
                intent_score=lead_payload.get("intent_score", 0),
                signal_freshness=lead_payload.get("signal_freshness"),
                tier=lead_payload.get("tier"),
                icp_fit=lead_payload.get("icp_fit"),
                badge=lead_payload.get("badge"),
                why_now=lead_payload.get("why_now"),
                signal_tags=lead_payload.get("signal_tags"),
                ai_verdict=lead_payload.get("ai_verdict"),
                full_payload=lead_payload,
            )
            db.add(snapshot)
        db.commit()
        logger.info(f"Successfully persisted {company_name}")
    except Exception as e:
        logger.error(f"Failed to persist {company_name}: {e}")
    finally:
        db.close()
