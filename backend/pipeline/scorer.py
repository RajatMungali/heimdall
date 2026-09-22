import os
import re
import copy
import json
import asyncio
import httpx
from datetime import datetime, timezone
from google import genai
from google.genai import types
from pydantic import BaseModel, Field
from backend.validation.quote_validator import validate_quote
from backend.config import settings
from backend.utils.logger import logger


# ======================================================================
# Pydantic data interface structures
# Keys align with the Strict Data Contract Protocol
# ======================================================================

class ExtractedSignal(BaseModel):
    signal_type: str
    verbatim_quote: str
    source_url: str = ""
    event_date: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


class GeminiScoringPayload(BaseModel):
    company_name: str
    intent_score: int
    tier: str
    signals: list[ExtractedSignal]
    ai_verdict: str


def process_hybrid_lead_scoring(
    raw_extracted_payload: dict,
    firmographics: dict,
    raw_source_text: str = "",
    icp_fit_label: str = "Strong"
) -> dict:
    """
    Implements Band & Recency-Driven Scoring Architecture (Scoring1.pdf):
    1. Base score set by most recent non-job signal within 3 months:
       - < 2 weeks (< 14d): 95 - 100
       - < 1 month (14 - 30d): 90 - 95
       - < 1.5 months (30 - 45d): 85 - 90
       - < 2 months (45 - 60d): 80 - 85
       - < 3 months (60 - 90d): 75 - 80
       - Job in last 24h / Stale open 30-70d (only if no non-job signal): 75 - 80
       - Job 2-3d old / Stale open 15-30d (only if no non-job signal): 70 - 75
    2. Add-ons:
       - Additional non-job signals: 1-2mo (+3), 2-3mo (+2), stale posts >3mo (+1)
       - Job supporting signal: today / stale 30-70d (+2), 2-3d / stale 15-30d (+1), stale >3mo (+1)
       - Job volume: <3 (0), 3-6 (+2), 7-9 (+3), 10+ (+4)
       - Combined Job Cap: Max +4
       - Global Add-On Cap: Max +6
    3. Ceilings:
       - If Base < 95 -> Max score <= 94 (95-100 reserved strictly for base < 2 weeks)
       - If Base >= 95 -> Max score <= 100
    4. Hard Overrides:
       - Layoffs / recent hiring freeze -> Final score = 0
       - "No agencies" / "Direct applicants only" -> Max score <= 40
       - Score < 70 -> Filtered from dashboard
    """
    signals_processed = []
    import re
    date_match = re.search(r'Date:\s*(\d{4}-\d{2}-\d{2})', raw_source_text)
    fallback_date_str = date_match.group(1) if date_match else None
    clean_source = re.sub(r'\s+', ' ', raw_source_text.strip().lower()) if raw_source_text else ""
    raw_lower = raw_source_text.lower() if raw_source_text else ""

    # Process each extracted signal
    for sig in raw_extracted_payload.get("signals", []):
        sig_type = sig.get("signal_type", "")
        quote = sig.get("verbatim_quote", "")
        
        # Per-signal date resolution
        sig_date_str = sig.get("event_date")
        if not sig_date_str and quote:
            m_match = re.search(r'(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{4})', quote, re.IGNORECASE)
            if m_match:
                month_name, year_str = m_match.groups()
                try:
                    m_num = datetime.strptime(month_name[:3].title(), "%b").month
                    sig_date_str = f"{year_str}-{m_num:02d}-01"
                except Exception:
                    pass

            if not sig_date_str and clean_source:
                clean_quote = re.sub(r'\s+', ' ', quote.strip().lower())
                sub_len = min(12, len(clean_quote))
                sub_str = clean_quote[:sub_len] if len(clean_quote) >= 5 else clean_quote
                q_idx = clean_source.find(sub_str) if sub_str else -1
                if q_idx != -1:
                    preceding_text = raw_source_text[:q_idx]
                    all_dates = re.findall(r'Date:\s*(\d{4}-\d{2}-\d{2})', preceding_text)
                    if all_dates:
                        sig_date_str = all_dates[-1]

        event_date = sig_date_str or fallback_date_str
        days_old = 180
        if event_date:
            try:
                dt = datetime.fromisoformat(str(event_date).replace("Z", "+00:00"))
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                days_old = max(0, (datetime.now(timezone.utc) - dt).days)
            except Exception:
                days_old = 180

        # Recency Label
        if days_old < 14:
            recency_label = "< 2 weeks"
        elif days_old <= 30:
            recency_label = "< 1 month"
        elif days_old <= 45:
            recency_label = "< 1.5 months"
        elif days_old <= 60:
            recency_label = "< 2 months"
        elif days_old <= 90:
            recency_label = "< 3 months"
        elif days_old <= 180:
            recency_label = "3-6 months"
        elif days_old <= 365:
            recency_label = "6-12 months"
        else:
            recency_label = "12+ months"

        # Validate quote against source text
        is_valid, sim_score = validate_quote(quote, raw_source_text)
        
        # Determine if signal is a job posting
        is_job_sig = any(k in str(sig_type).lower() or k in quote.lower() for k in [
            "job opening", "hiring role", "open position", "openings", "we are hiring", "job post", "recruiting for"
        ])

        signals_processed.append({
            "signal_type": sig_type,
            "verbatim_quote": quote,
            "quote_validated": is_valid,
            "similarity_score": round(sim_score, 1),
            "source_url": sig.get("source_url", ""),
            "recency_label": recency_label,
            "event_date": str(event_date) if event_date else None,
            "days_old": days_old,
            "is_job_signal": is_job_sig
        })

    # Separate valid non-job signals vs job signals
    valid_non_job_signals = [
        s for s in signals_processed 
        if s["quote_validated"] and not s["is_job_signal"]
    ]
    valid_job_signals = [
        s for s in signals_processed 
        if s["quote_validated"] and s["is_job_signal"]
    ]

    # Deduplicate non-job signals about the same event (e.g. duplicate articles for the same Series A)
    deduped_non_job = []
    seen_event_types = set()
    for s in sorted(valid_non_job_signals, key=lambda x: x["days_old"]):
        etype = re.sub(r'[^a-z0-9]', '', str(s["signal_type"]).lower())
        if etype and etype in seen_event_types:
            continue
        if etype:
            seen_event_types.add(etype)
        deduped_non_job.append(s)

    # -------------------------------------------------------------
    # 1. BASE SCORE DETERMINATION (Priority: Most recent non-job signal < 3 months)
    # -------------------------------------------------------------
    fresh_non_job_90d = [s for s in deduped_non_job if s["days_old"] <= 90]
    
    base_signal = None
    base_band_name = ""
    base_score = 50.0

    llm_raw_base = raw_extracted_payload.get("base_score") or raw_extracted_payload.get("intent_score")

    if fresh_non_job_90d:
        # Sort by recency: lowest days_old sets the base
        fresh_non_job_90d.sort(key=lambda x: x["days_old"])
        base_signal = fresh_non_job_90d[0]
        days = base_signal["days_old"]

        if days < 14:
            base_band_name = "< 2 weeks (95-100)"
            band_min, band_max, band_default = 95, 100, 97
        elif days <= 30:
            base_band_name = "< 1 month (90-95)"
            band_min, band_max, band_default = 90, 95, 92
        elif days <= 45:
            base_band_name = "< 1.5 months (85-90)"
            band_min, band_max, band_default = 85, 90, 87
        elif days <= 60:
            base_band_name = "< 2 months (80-85)"
            band_min, band_max, band_default = 80, 85, 82
        else:  # <= 90
            base_band_name = "< 3 months (75-80)"
            band_min, band_max, band_default = 75, 80, 77

        if isinstance(llm_raw_base, (int, float)) and band_min <= llm_raw_base <= band_max:
            base_score = float(llm_raw_base)
        else:
            base_score = float(band_default)

    elif valid_job_signals:
        # Job postings set base ONLY if no other signal exists
        min_job_days = min(s["days_old"] for s in valid_job_signals)
        if min_job_days <= 1 or (30 <= min_job_days <= 70):
            base_band_name = "Job <24h / Stale 30-70d (75-80)"
            base_score = 77.0
        elif min_job_days <= 3 or (15 <= min_job_days < 30):
            base_band_name = "Job 2-3d / Stale 15-30d (70-75)"
            base_score = 72.0
        else:
            base_band_name = "Stale Job >3mo (60-70)"
            base_score = 65.0
        base_signal = valid_job_signals[0]
    else:
        # No signals within 3 months and no jobs
        base_band_name = "Stale > 3 months (< 70)"
        base_score = 55.0

    # -------------------------------------------------------------
    # 2. CALIBRATED ADD-ONS COMPUTATION
    # -------------------------------------------------------------
    supporting_signals_addon = 0.0
    # Additional non-job signals (excluding the base signal)
    supporting_non_job = [s for s in deduped_non_job if s != base_signal]
    for s in supporting_non_job:
        if 30 <= s["days_old"] <= 60:
            supporting_signals_addon += 3.0  # 1-2 months old (+3)
        elif 60 < s["days_old"] <= 90:
            supporting_signals_addon += 2.0  # 2-3 months old (+2)
        elif s["days_old"] > 90:
            supporting_signals_addon += 1.0  # specifically stale posts > 3 months (+1)

    # Job Posting Timing Add-On (only if non-job set the base)
    job_timing_addon = 0.0
    if base_signal and not base_signal.get("is_job_signal") and valid_job_signals:
        min_job_days = min(s["days_old"] for s in valid_job_signals)
        if min_job_days <= 1 or (30 <= min_job_days <= 70):
            job_timing_addon = 2.0  # Today or stale 30-70d (+2)
        elif min_job_days <= 3 or (15 <= min_job_days < 30):
            job_timing_addon = 1.0  # 2-3d or stale 15-30d (+1)
        elif min_job_days > 90:
            job_timing_addon = 1.0  # Stale post > 3 months (+1)

    # Job Posting Volume Add-On
    open_jobs_count = (
        firmographics.get("open_roles_count")
        or raw_extracted_payload.get("open_jobs_count")
        or len(valid_job_signals)
    )
    try:
        open_jobs_count = int(open_jobs_count)
    except Exception:
        open_jobs_count = len(valid_job_signals)

    if open_jobs_count >= 10:
        job_volume_addon = 4.0  # 10+ jobs (+4)
    elif open_jobs_count >= 7:
        job_volume_addon = 3.0  # 7-9 jobs (+3)
    elif open_jobs_count >= 3:
        job_volume_addon = 2.0  # 3-6 jobs (+2)
    else:
        job_volume_addon = 0.0  # <3 jobs (0)

    # Combined Job Add-On Cap (Max +4 across job timing & volume)
    combined_job_addon = min(job_timing_addon + job_volume_addon, 4.0)

    # Global Add-On Cap (Max +6 across all supporting signals + jobs)
    total_addons = min(supporting_signals_addon + combined_job_addon, 6.0)

    # -------------------------------------------------------------
    # 3. CALCULATED SCORE & STRICT CEILING RULES
    # -------------------------------------------------------------
    calculated_pre_ceiling = base_score + total_addons
    applied_ceiling = None

    if base_score < 95.0:
        # Ceiling Rule: If base < 95, score CANNOT exceed 94 (95-100 reserved for <2w base)
        if calculated_pre_ceiling > 94.0:
            final_intent_score = 94
            applied_ceiling = 94
        else:
            final_intent_score = int(round(calculated_pre_ceiling))
    else:
        # Base >= 95 (under 2 weeks) -> Can go up to 100
        final_intent_score = min(int(round(calculated_pre_ceiling)), 100)
        if calculated_pre_ceiling > 100.0:
            applied_ceiling = 100

    # -------------------------------------------------------------
    # 4. HARD OVERRIDES (Layoffs -> 0, No Agencies -> 40, SKIP -> 0)
    # -------------------------------------------------------------
    hard_override = None
    override_reason = ""

    # Layoff / Hiring Freeze Check
    layoff_keywords = ["layoff", "layoffs", "laid off", "workforce reduction", "hiring freeze", "downsizing", "job cuts"]
    has_layoffs = (
        raw_extracted_payload.get("hard_override") == "LAYOFF" or
        any(k in raw_lower for k in layoff_keywords) or
        any(k in s["verbatim_quote"].lower() for s in signals_processed for k in layoff_keywords)
    )

    if has_layoffs:
        final_intent_score = 0
        hard_override = "LAYOFF"
        override_reason = "Recent layoffs or hiring freeze detected."

    # "No Agencies" Check
    agency_block_keywords = ["no agencies", "no recruitment agencies", "direct applicants only", "no third party recruiters", "no staffing agencies", "agencies do not contact"]
    has_agency_block = (
        raw_extracted_payload.get("hard_override") == "NO_AGENCIES" or
        any(k in raw_lower for k in agency_block_keywords) or
        any(k in s["verbatim_quote"].lower() for s in signals_processed for k in agency_block_keywords)
    )

    if has_agency_block and final_intent_score > 40:
        final_intent_score = 40
        hard_override = "NO_AGENCIES"
        override_reason = "Job postings explicitly disallow external agency/staffing outreach."

    # Agency Guard Disqualification
    if raw_extracted_payload.get("intent_classification") == "SKIP" or base_score == 0:
        final_intent_score = 0
        hard_override = "DISQUALIFIED"
        override_reason = "Classified as staffing/recruitment agency or out of ICP."

    # -------------------------------------------------------------
    # 5. DASHBOARD FILTER & TIERING (< 70 filtered)
    # -------------------------------------------------------------
    is_dashboard_visible = final_intent_score >= 70
    if final_intent_score >= 85:
        assigned_tier = "High"
        intent_class = "HOT"
    elif final_intent_score >= 70:
        assigned_tier = "Medium"
        intent_class = "WARM"
    else:
        assigned_tier = "Low"
        intent_class = "SKIP"

    # Attach score contributions back to signals for display in UI drawer
    for s in signals_processed:
        if s == base_signal:
            s["score_contribution"] = round(base_score, 1)
        elif s in supporting_non_job:
            if 30 <= s["days_old"] <= 60:
                s["score_contribution"] = 3.0
            elif 60 < s["days_old"] <= 90:
                s["score_contribution"] = 2.0
            else:
                s["score_contribution"] = 1.0
        elif s in valid_job_signals:
            s["score_contribution"] = round(combined_job_addon / max(1, len(valid_job_signals)), 1)
        else:
            s["score_contribution"] = 0.0

    extracted_industry = raw_extracted_payload.get("industry") or firmographics.get("industry", "Technology & Services")
    company_segment = raw_extracted_payload.get("company_segment") or firmographics.get("company_segment", "Growth Scale-up")
    
    raw_why_now = raw_extracted_payload.get("why_now", "")
    if raw_why_now:
        cleaned = re.sub(r'(?i)sentence\s*\d*:?\s*', '', raw_why_now)
        cleaned = re.sub(r'(?i)\(catalyst\):?\s*', '', cleaned)
        cleaned = re.sub(r'(?i)\(opportunity\):?\s*', '', cleaned)
        cleaned = re.sub(r'(?i)catalyst:?\s*', '', cleaned)
        cleaned = re.sub(r'(?i)opportunity:?\s*', '', cleaned)
        why_now = re.sub(r'\s+', ' ', cleaned).strip()
        if not why_now:
            why_now = raw_why_now
    else:
        one_line = raw_extracted_payload.get("one_line_reason", "")
        if one_line:
            why_now = f"{one_line} Recommend targeted outreach based on recent trigger events."
        else:
            why_now = f"Public intent indicators detected for {raw_extracted_payload.get('company_name', 'this company')}. Recommend outreach."

    ai_verdict = raw_extracted_payload.get("ai_verdict", "Review signals for outreach context.")
    if isinstance(ai_verdict, list):
        ai_verdict = " ".join([str(v) for v in ai_verdict])

    one_line_reason = raw_extracted_payload.get("one_line_reason") or why_now.split(". ")[0]

    return {
        "company_name": raw_extracted_payload.get("company_name"),
        "industry": extracted_industry,
        "company_segment": company_segment,
        "intent_score": final_intent_score,
        "intent_classification": intent_class,
        "one_line_reason": one_line_reason,
        "signal_freshness": 100 if base_score >= 90 else (80 if base_score >= 80 else 60),
        "tier": assigned_tier,
        "icp_fit": icp_fit_label,
        "is_dashboard_visible": is_dashboard_visible,
        "signals": signals_processed,
        "why_now": why_now,
        "signal_tags": raw_extracted_payload.get("signal_tags", []),
        "gemini_token_usage": raw_extracted_payload.get("gemini_token_usage", "Unknown"),
        "scoring_breakdown": {
            "base_score": base_score,
            "base_signal_name": base_signal.get("signal_type") if base_signal else "None",
            "base_band": base_band_name,
            "supporting_signals_addon": supporting_signals_addon,
            "job_timing_addon": job_timing_addon,
            "job_volume_addon": job_volume_addon,
            "combined_job_addon": combined_job_addon,
            "total_addons": total_addons,
            "calculated_pre_ceiling_score": calculated_pre_ceiling,
            "applied_ceiling": applied_ceiling,
            "hard_override": hard_override,
            "override_reason": override_reason,
            "final_score": final_intent_score,
            "is_dashboard_visible": is_dashboard_visible
        },
        "ai_verdict": ai_verdict,
        "raw_gemini_output": raw_extracted_payload
    }


COLOR_THEME_MAP = {
    "funding": "indigo",
    "hiring": "emerald",
    "agency_intent": "rose",
    "product": "amber",
    "expansion": "amber",
    "leadership": "indigo",
    "social_intent": "rose"
}


def sanitize_exa_payload_for_llm(raw_exa_json: dict) -> dict:
    """
    Strips internal Exa diagnostic metadata (pipeline_metadata, grounding citation objects)
    and returns a compact, token-optimized JSON payload containing only essential fields:
    - company_name & domain
    - structured_facts (headcount, industry, funding_stage, funding_amount, funding_date, open_roles_count, recent_hiring_signal)
    - evidence_sources (title, url, published_date, summary, text_snippet)
    """
    if not isinstance(raw_exa_json, dict):
        return raw_exa_json

    company_name = raw_exa_json.get("company_name", "Target Company")
    domain = raw_exa_json.get("domain", "")

    # Extract clean content from native_exa_structured_extraction
    native_ext = raw_exa_json.get("native_exa_structured_extraction", {})
    raw_content = native_ext.get("content", {}) if isinstance(native_ext, dict) else {}

    structured_facts = {
        "headcount": raw_content.get("headcount"),
        "industry": raw_content.get("industry"),
        "funding_stage": raw_content.get("funding_stage"),
        "funding_amount": raw_content.get("funding_amount"),
        "funding_date": raw_content.get("funding_date"),
        "open_roles_count": raw_content.get("open_roles_count"),
        "recent_hiring_signal": raw_content.get("recent_hiring_signal")
    }
    # Remove null/empty facts
    structured_facts = {k: v for k, v in structured_facts.items() if v}

    # Extract clean evidence sources
    raw_sources = raw_exa_json.get("harvested_sources", [])
    clean_sources = []
    if isinstance(raw_sources, list):
        for s in raw_sources:
            if not isinstance(s, dict):
                continue
            clean_sources.append({
                "title": s.get("title", ""),
                "url": s.get("url", ""),
                "published_date": s.get("published_date") or s.get("publishedDate"),
                "summary": s.get("summary", ""),
                "snippet": (s.get("text_snippet") or s.get("text") or "")[:400]
            })

    return {
        "company_name": company_name,
        "domain": domain,
        "structured_facts": structured_facts,
        "evidence_sources": clean_sources
    }


async def analyze_lead_intent_with_llm(
    company_name: str,
    cleaned_html: str,
    firmographics: dict,
    icp_fit_label: str = "Strong",
    raw_signals: list = None
) -> dict:
    """
    Calls Gemini API (or Groq fallback) to extract signals and then applies hybrid scoring.
    """
    from dotenv import dotenv_values
    
    env_vars = dotenv_values("backend/.env")
    gemini_key = env_vars.get("GEMINI_API_KEY") or os.getenv("GEMINI_API_KEY") or getattr(settings, "GEMINI_API_KEY", "")
    groq_key = env_vars.get("GROQ_API_KEY") or os.getenv("GROQ_API_KEY") or getattr(settings, "GROQ_API_KEY", "")

    # Priority 1: Gemini API
    if gemini_key:
        for attempt in range(2):
            try:
                config_path = os.path.join(os.path.dirname(__file__), "..", "intent_config.json")
                active_niche = "recruitment"
                niche_rules = "Target companies posted job = positive signal. Agency post = discard."
                if os.path.exists(config_path):
                    with open(config_path, "r") as f:
                        intent_cfg = json.load(f)
                        active_niche = intent_cfg.get("active_niche", "recruitment")
                        niche_info = intent_cfg.get("niches", {}).get(active_niche, {})
                        niche_rules = niche_info.get("rules", niche_rules)

                # Static System Instruction (Cacheable across all company scoring calls)
                system_instruction = f"""You are a strict, ultra-precise JSON data extraction engine for B2B Sales Intelligence. Output raw JSON ONLY.

TARGET CLIENT NICHE: {active_niche}

AGENCY GUARD: Discard candidate company ONLY if it is itself a RECRUITMENT / STAFFING / HR placement agency (e.g., Randstad, Robert Half, staffing agency), OR if a job post was posted BY a recruitment agency. Do NOT discard general IT services, software consulting, or tech product companies — they buy recruitment services!

COMPLAINT GUARD: Ignore end-user complaints, angry customer reviews, or support issues directed at a company.

THOUGHT LEADERSHIP GUARD: Discard industry commentary, advice posts, opinion pieces, educational tips, and newsletter promotions.

JOB POST SIGNAL RULES:
- Posted BY candidate company = positive buying signal.
- Posted BY a recruitment agency = discard (see AGENCY GUARD).
- Explicit "No agencies" / "Direct applicants only" in job postings = set "hard_override": "NO_AGENCIES".

HARD OVERRIDE RULES:
- If company announced layoffs, workforce reduction, or hiring freeze: set "hard_override": "LAYOFF".
- If job posting disallows agency outreach: set "hard_override": "NO_AGENCIES".
- Otherwise: set "hard_override": "NONE".

BASE SCORE CHRONOLOGICAL BANDS (Find most recent non-job signal within 3 months):
- Under 2 weeks (< 14d): Band 95 - 100
- Under 1 month (14 - 30d): Band 90 - 95
- Under 1.5 months (30 - 45d): Band 85 - 90
- Under 2 months (45 - 60d): Band 80 - 85
- Under 3 months (60 - 90d): Band 75 - 80
- If only job postings exist (no non-job signal): Job in last 24h / Stale 30-70d = 75-80, Job 2-3d / Stale 15-30d = 70-75.
- Signals > 3 months old CANNOT set base score.

SIGNAL SELECTION RULES (CONCISE & ESSENTIAL ONLY):
- Extract ONLY the top 2 to 4 distinct, high-impact major buying signals.
- DO NOT output duplicate quotes from the same article or sentence.

OUTPUT JSON SCHEMA:
{{
  "company_name": "<Target Company Name>",
  "industry": "<Specific Industry Name>",
  "company_segment": "<Market Segment>",
  "base_score": <integer within the identified band based on qualitative strength>,
  "base_band": "< 2 weeks" | "< 1 month" | "< 1.5 months" | "< 2 months" | "< 3 months" | "job_only" | "stale",
  "base_signal_name": "<Exact Name of Most Recent Non-Job Trigger Event>",
  "hard_override": "NONE" | "LAYOFF" | "NO_AGENCIES",
  "intent_classification": "HOT" | "WARM" | "SKIP",
  "one_line_reason": "<1-sentence concise reason why post/company was flagged>",
  "why_now": "<1-2 sentence natural summary of the trigger event and urgency>",
  "open_jobs_count": <estimated integer count of open roles found, e.g. 11>,
  "signal_tags": [
    {{
      "tag": "<Exact Milestone Found>",
      "category": "FUNDING|HIRING|EXPANSION|LEADERSHIP|SOCIAL_INTENT"
    }}
  ],
  "signals": [
    {{
      "signal_type": "<Keyword or topic matched>",
      "verbatim_quote": "<Exact word-for-word substring copied directly from text>",
      "source_post_index": <integer 0, 1, 2... index of [S0], [S1], [S2] where quote was found>,
      "is_grant": false
    }}
  ],
  "ai_verdict": "Comprehensive 3-sentence summary giving overall picture/findings of the company and explicitly answering: 'Is this a good business/company to reach out to for the recruitment service?'"
}}"""

                user_prompt = f"""Analyze candidate company: {company_name}

=== INPUT EVIDENCE TEXT ===
{cleaned_html}
==========================="""

                client = genai.Client(api_key=gemini_key)
                loop = asyncio.get_running_loop()
                response = await loop.run_in_executor(
                    None,
                    lambda: client.models.generate_content(
                        model="gemini-2.5-flash",
                        contents=user_prompt,
                        config=types.GenerateContentConfig(
                            system_instruction=system_instruction,
                            response_mime_type="application/json",
                            temperature=0.1
                        )
                    )
                )
                raw_text = response.text.strip()
                if "```json" in raw_text:
                    raw_text = raw_text.split("```json")[1].split("```")[0].strip()
                elif "```" in raw_text:
                    raw_text = raw_text.split("```")[1].split("```")[0].strip()
                
                meta = getattr(response, "usage_metadata", None)
                meta_dict = {}
                if meta:
                    if hasattr(meta, "model_dump"):
                        try:
                            meta_dict = meta.model_dump()
                        except Exception:
                            pass
                    if not meta_dict and hasattr(meta, "__dict__"):
                        meta_dict = {k: v for k, v in meta.__dict__.items() if not k.startswith("_")}
                    if not meta_dict:
                        meta_dict = {
                            "promptTokenCount": getattr(meta, "prompt_token_count", None),
                            "candidatesTokenCount": getattr(meta, "candidates_token_count", None),
                            "totalTokenCount": getattr(meta, "total_token_count", None),
                            "cachedContentTokenCount": getattr(meta, "cached_content_token_count", None),
                            "thoughtsTokenCount": getattr(meta, "thoughts_token_count", None)
                        }

                prompt_toks = getattr(meta, "prompt_token_count", 0) if meta else 0
                comp_toks = getattr(meta, "candidates_token_count", 0) if meta else 0
                think_toks = getattr(meta, "thoughts_token_count", 0) if meta else 0
                tot_toks = getattr(meta, "total_token_count", 0) if meta else 0

                token_usage_dict = {
                    "prompt_tokens": prompt_toks,
                    "completion_tokens": comp_toks,
                    "thinking_tokens": think_toks,
                    "total_tokens": tot_toks,
                    "raw_usage_metadata": meta_dict
                }
                logger.info(f"Gemini Token Usage for {company_name}: {meta_dict}")
                
                raw_payload = json.loads(raw_text)
                if isinstance(raw_payload, list):
                    if len(raw_payload) > 0 and isinstance(raw_payload[0], dict):
                        raw_payload = raw_payload[0]
                    else:
                        raw_payload = {}
                elif not isinstance(raw_payload, dict):
                    raw_payload = {}

                raw_payload["company_name"] = company_name
                raw_payload["gemini_token_usage"] = token_usage_dict

                import copy
                raw_gemini_pure = copy.deepcopy(raw_payload)

                # Deterministically attach color_theme to signal_tags
                if raw_payload.get("signal_tags") and isinstance(raw_payload["signal_tags"], list):
                    for st in raw_payload["signal_tags"]:
                        if isinstance(st, dict):
                            cat = str(st.get("category", "")).lower()
                            st["color_theme"] = COLOR_THEME_MAP.get(cat, "indigo")

                # Python Index-to-URL mapper with Defensive Out-of-Bounds Logging & String/1-based Fallbacks
                if raw_payload.get("signals") and isinstance(raw_payload["signals"], list):
                    valid_signals = []
                    for sig in raw_payload["signals"]:
                        if not isinstance(sig, dict):
                            continue
                        quote = sig.get("verbatim_quote", "")

                        # Only run index-to-URL mapping when raw_signals is provided (batch pipeline)
                        if raw_signals is not None:
                            raw_idx = sig.get("source_post_index")
                            resolved_idx = None
                            
                            # Robust resolution for int, str ("1", "S1", "[S1]") and 0-based/1-based indexing
                            if raw_idx is not None:
                                parsed_num = None
                                if isinstance(raw_idx, int):
                                    parsed_num = raw_idx
                                elif isinstance(raw_idx, str):
                                    m = re.search(r'\d+', raw_idx)
                                    if m:
                                        try:
                                            parsed_num = int(m.group(0))
                                        except ValueError:
                                            pass

                                if parsed_num is not None and parsed_num >= 0:
                                    # 1. Try 0-based first
                                    if 0 <= parsed_num < len(raw_signals):
                                        resolved_idx = parsed_num
                                    # 2. Try 1-based fallback
                                    elif 1 <= parsed_num <= len(raw_signals):
                                        resolved_idx = parsed_num - 1

                            # Fallback 1: Text Substring Search across raw_signals if index is -1 or out-of-bounds
                            if resolved_idx is None and quote:
                                q_clean = quote.lower().replace("\n", " ").strip()
                                for idx_s, src_item in enumerate(raw_signals):
                                    src_text = (
                                        (src_item.get("summary") or "") + " " +
                                        (src_item.get("text_snippet") or "") + " " +
                                        (src_item.get("text") or "")
                                    ).lower().replace("\n", " ")
                                    if len(q_clean) > 8 and q_clean[:20] in src_text:
                                        resolved_idx = idx_s
                                        break

                            # Fallback 2: Keyword Domain Matcher for Structured Facts (Funding/Hiring/Leadership)
                            if resolved_idx is None and quote:
                                sig_type_lower = sig.get("signal_type", "").lower()
                                q_lower = quote.lower()
                                for idx_s, src_item in enumerate(raw_signals):
                                    u_low = (src_item.get("url") or "").lower()
                                    if any(k in sig_type_lower or k in q_lower for k in ["funding", "investment", "round", "raised", "seed", "angel", "133k"]):
                                        if any(domain_kw in u_low for domain_kw in ["tracxn", "crunchbase", "prospeo", "cbinsights"]):
                                            resolved_idx = idx_s
                                            break
                                    elif any(k in sig_type_lower or k in q_lower for k in ["hiring", "open_roles", "openings", "roles"]):
                                        if any(domain_kw in u_low for domain_kw in ["job", "career", "openings"]):
                                            resolved_idx = idx_s
                                            break

                            if resolved_idx is not None:
                                item_src = raw_signals[resolved_idx]
                                sig["source_url"] = item_src.get("url") or item_src.get("link") or item_src.get("extracted_url")
                                
                                # Deterministically attach exact event_date from Exa source JSON metadata
                                src_date = item_src.get("published_date") or item_src.get("publishedDate") or item_src.get("date") or item_src.get("date_posted")
                                if not src_date and isinstance(item_src.get("structured_facts"), dict):
                                    src_date = item_src["structured_facts"].get("funding_date")
                                if not src_date and isinstance(firmographics, dict):
                                    src_date = firmographics.get("funding_date")
                                
                                if src_date:
                                    sig["event_date"] = str(src_date)

                                sig["quote_validated"] = True
                            else:
                                logger.warning(
                                    f"[Gemini Index Warning] Could not resolve source_url for quote '{quote[:30]}' "
                                    f"in company '{company_name}' (source_post_index: {raw_idx}). Setting source_url to None."
                                )
                                sig["source_url"] = None
                                sig["quote_validated"] = False

                        if quote and quote.lower() in cleaned_html.lower():
                            valid_signals.append(sig)

                    # Deduplicate overlapping quotes and limit to top 4 distinct major signals
                    deduped_signals = []
                    seen_quotes = []
                    for sig in valid_signals:
                        q_norm = re.sub(r'\s+', ' ', sig.get("verbatim_quote", "").strip().lower())
                        if not q_norm or len(q_norm) < 8:
                            continue

                        is_redundant = False
                        for existing_q in seen_quotes:
                            if q_norm in existing_q or existing_q in q_norm:
                                is_redundant = True
                                break
                        if not is_redundant:
                            deduped_signals.append(sig)
                            seen_quotes.append(q_norm)
                            if len(deduped_signals) >= 4:
                                break

                    raw_payload["signals"] = deduped_signals if deduped_signals else valid_signals[:4]

                scored_output = process_hybrid_lead_scoring(raw_payload, firmographics, cleaned_html, icp_fit_label=icp_fit_label)
                scored_output["raw_gemini_output"] = raw_gemini_pure
                return scored_output

            except Exception as e:
                logger.warning(f"[Scorer] Gemini API attempt {attempt + 1} failed: {e}.")
                if attempt == 0:
                    await asyncio.sleep(2.5)
                elif attempt == 1:
                    logger.warning("[Scorer] Gemini failed. Trying Groq multi-tier fallback...")

    # Multi-Tier Fallback to Groq API (oss-120b -> oss-20b)
    if groq_key:
        groq_models = ["oss-120b", "oss-20b", "llama-3.3-70b-versatile"]
        for g_model in groq_models:
            try:
                logger.info(f"[Scorer] Attempting Groq fallback using model '{g_model}' for {company_name}...")
                prompt = f"""Analyze {company_name} using the provided text below...\n{cleaned_html}"""
                url = "https://api.groq.com/openai/v1/chat/completions"
                headers = {"Authorization": f"Bearer {groq_key}", "Content-Type": "application/json"}
                payload = {
                    "model": g_model,
                    "messages": [
                        {"role": "system", "content": "Output raw JSON ONLY."},
                        {"role": "user", "content": prompt}
                    ],
                    "temperature": 0.1,
                    "response_format": {"type": "json_object"}
                }
                async with httpx.AsyncClient(timeout=35.0) as client:
                    response = await client.post(url, headers=headers, json=payload)
                    response.raise_for_status()
                    resp_data = response.json()
                    raw_text = resp_data["choices"][0]["message"].get("content", "")
                    if "```json" in raw_text:
                        raw_text = raw_text.split("```json")[1].split("```")[0].strip()
                    elif "```" in raw_text:
                        raw_text = raw_text.split("```")[1].split("```")[0].strip()
                    raw_payload = json.loads(raw_text)
                    raw_payload["company_name"] = company_name
                    logger.info(f"[Scorer] Successfully evaluated {company_name} via Groq model '{g_model}'!")
                    return process_hybrid_lead_scoring(raw_payload, firmographics, cleaned_html, icp_fit_label=icp_fit_label)
            except Exception as e:
                logger.warning(f"[Scorer] Groq model '{g_model}' failed: {e}.")

    # Tier 3: Rule-Based Fallback when APIs fail or are exhausted
    extracted_signals = []
    text_lower = cleaned_html.lower()
    kw_list = ["hiring", "sdr", "series a", "seed", "funding", "raised", "expansion", "redesign", "meta ads", "shopify"]
    found_matches = [kw for kw in kw_list if kw in text_lower]
    
    for match in found_matches[:4]:
        extracted_signals.append({
            "signal_type": f"{match}_detected",
            "verbatim_quote": f"Detected high-intent indicator '{match}' in public brand signals.",
            "source_url": f"https://{company_name.lower().replace(' ', '')}.com",
            "event_date": datetime.now(timezone.utc).isoformat()
        })

    fallback_score = min(50 + (len(found_matches) * 10), 80)
    fallback_payload = {
        "company_name": company_name,
        "base_score": fallback_score,
        "signals": extracted_signals,
        "why_now": f"Matched {len(found_matches)} core intent triggers in public discovery sweeps.",
        "ai_verdict": f"[Fallback Engine] Public intent signals detected for {company_name} (including {', '.join(found_matches[:2]) if found_matches else 'general growth'}). Recommend targeted outreach highlighting how your services can support their recent growth."
    }

    return process_hybrid_lead_scoring(fallback_payload, firmographics, cleaned_html, icp_fit_label=icp_fit_label)
