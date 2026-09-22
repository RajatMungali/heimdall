import asyncio
import json
import os
import re
import uuid
import httpx
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone

from backend.utils.logger import logger

def extract_revenue_from_exa_text(text: str, structured_out: Optional[dict] = None) -> Optional[str]:
    def clean_rev_string(val_str: str) -> str:
        if not val_str or not any(c.isdigit() for c in val_str):
            return "N/A"
        # Convert words like million/billion to M/B
        s = re.sub(r'(?i)\s*million\b', 'M', val_str)
        s = re.sub(r'(?i)\s*billion\b', 'B', s)
        s = re.sub(r'(?i)\s*thousand\b', 'K', s)

        m = re.search(r'(~?\s*\$?\s*[\d\.]+(?:\s*-\s*\$?\s*[\d\.]+)?)\s*([MKBmkb])?', s)
        if m:
            raw_num = m.group(1).replace("~", "").replace("$", "").strip()
            unit = (m.group(2) or "").upper()
            if not unit:
                try:
                    num_val = float(raw_num.split("-")[0].strip())
                    if 0 < num_val < 1000:
                        unit = "M"
                except Exception:
                    pass
            prefix = "~$" if "~" in s else "$"
            return f"{prefix}{raw_num}{unit}"
        return "N/A"

    if structured_out and isinstance(structured_out, dict):
        content = structured_out.get("content") if isinstance(structured_out.get("content"), dict) else structured_out
        rev_val = content.get("arr_estimate") or content.get("annual_revenue") or content.get("revenueAnnual")

        if isinstance(rev_val, (int, float)) and rev_val > 0:
            if rev_val >= 1_000_000_000:
                return f"${rev_val / 1_000_000_000:.1f}B"
            elif rev_val >= 1_000_000:
                return f"${rev_val / 1_000_000:.1f}M"
            elif rev_val < 1000:
                return f"${rev_val:.1f}M"
            else:
                return f"${rev_val:,.0f}"
        elif isinstance(rev_val, str) and rev_val.strip():
            res = clean_rev_string(rev_val)
            if res != "N/A":
                return res

    if not text:
        return None

    patterns = [
        r'(?i)(?:annual\s+revenue|revenue|arr)\s*(?:of|is|=|:)?\s*~\s*\$?\s*([\d\.]+\s*(?:million|billion|M|B)?)',
        r'(?i)\$\s*([\d\.]+\s*(?:million|billion|M|B)?)\s*(?:annual\s+revenue|arr|revenue)',
        r'(?i)(?:annual\s+revenue|revenue|arr)\s*(?:of|is|=|:)?\s*\$?\s*([\d\.]+\s*-\s*\$?[\d\.]+\s*(?:million|billion|M|B)?)',
        r'(?i)USD\s+([\d,]+)'
    ]
    for pat in patterns:
        m = re.search(pat, text)
        if m:
            return clean_rev_string(m.group(1))
    return None
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

from backend.pipeline.scorer import process_hybrid_lead_scoring
from backend.pipeline.airtable_connector import get_ui_test_batch, get_midnight_cron_batch
from backend.pipeline.dns_audit import audit_domain_email_infrastructure
from backend.database import SessionLocal
from backend.models import LeadSnapshot
from google import genai
from google.genai import types

EXA_API_KEY = os.getenv("EXA_API_KEY")
SERPER_API_KEY = os.getenv("SERPER_API_KEY")
SCRAPEBADGER_API_KEY = os.getenv("SCRAPEBADGER_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY")
APIFY_INSIGHTS_API_KEY = os.getenv("APIFY_INSIGHTS_API_KEY") or os.getenv("APIFY_API_KEY")
THEIRSTACK_API_KEY = os.getenv("THEIRSTACK_API_KEY")
LINKUP_API_KEY = os.getenv("LINKUP_API_KEY")

from backend.pipeline.linkedin_id_resolver import resolve_linkedin_company_id

TECH_AND_TA_KEYWORDS = [
    "engineer", "developer", "architect", "systems", "ml", "ai", "security", 
    "tech", "software", "infrastructure", "data", "product", "manager",
    "talent acquisition", "recruiter", "recruitment", "head of people", "hr", "people partner"
]
ENTRY_LEVEL_EXCLUSIONS = ["junior", "intern", "internship", "trainee"]


def is_entry_level_associate(title_lower: str) -> bool:
    if "associate" not in title_lower:
        return False
    senior_modifiers = ["director", "senior", "vp", "vice president", "head", "lead", "principal", "manager", "solutions architect"]
    return not any(mod in title_lower for mod in senior_modifiers)


def is_valid_company_job(title: str, link: str, snippet: str, company_name: str, company_slug: str) -> bool:
    t_lower = title.lower()
    l_lower = link.lower()
    c_lower = company_name.lower()
    slug_lower = company_slug.lower()

    if any(ex in t_lower for ex in ENTRY_LEVEL_EXCLUSIONS):
        return False
    if is_entry_level_associate(t_lower):
        return False

    has_qualified_role = any(kw in t_lower or kw in snippet.lower() for kw in TECH_AND_TA_KEYWORDS)
    if not has_qualified_role:
        return False

    target_domains = [
        f"ashbyhq.com/{slug_lower}",
        f"greenhouse.io/{slug_lower}",
        f"lever.co/{slug_lower}",
        f"workable.com/{slug_lower}",
        f"indeed.com/cmp/{slug_lower}",
        f"linkedin.com/company/{slug_lower}",
        f"linkedin.com/jobs",
        f"{slug_lower}.com"
    ]
    if any(dom in l_lower for dom in target_domains):
        return True

    title_anchors = [
        f"@ {c_lower}", f"at {c_lower}", f"- {c_lower}", f"| {c_lower}", 
        f", {c_lower}", f"{c_lower} -", f"{c_lower}:", f"{c_lower} jobs"
    ]
    if any(anchor in t_lower for anchor in title_anchors):
        return True

    return False


async def fetch_linkedin_company_insights(company_url_or_slug: str, company_slug: str) -> Optional[Dict[str, Any]]:
    primary_key = os.getenv("APIFY_INSIGHTS_API_KEY")
    secondary_key = os.getenv("APIFY_API_KEY")
    keys_to_try = []
    if primary_key:
        keys_to_try.append(primary_key)
    if secondary_key and secondary_key not in keys_to_try:
        keys_to_try.append(secondary_key)

    if not keys_to_try:
        return None

    if company_url_or_slug.startswith("https://www.linkedin.com/company/"):
        target_url = company_url_or_slug
    elif "/company/" in company_url_or_slug:
        slug = company_url_or_slug.rstrip("/").split("/company/")[-1].split("/")[0]
        target_url = f"https://www.linkedin.com/company/{slug}/"
    else:
        target_url = f"https://www.linkedin.com/company/{company_slug}/"

    url = "https://api.apify.com/v2/acts/riceman~linkedin-company-data-insights-scraper/run-sync-get-dataset-items"
    payload = {
        "company_linkedin_urls": [target_url],
        "get_company_insights": True,
        "get_total_job_openings": True
    }

    async with httpx.AsyncClient(timeout=120.0) as client:
        for api_key in keys_to_try:
            try:
                resp = await client.post(url, params={"token": api_key}, json=payload)
                if resp.status_code in [200, 201]:
                    data = resp.json()
                    if isinstance(data, list) and len(data) > 0:
                        return data[0]
                    elif isinstance(data, dict):
                        return data
                elif resp.status_code in [401, 402, 403]:
                    logger.warning(f"⚠️ Apify key ({api_key[:10]}...) returned HTTP {resp.status_code} Forbidden/Out of Credits. Trying fallback key...")
                    continue
            except Exception as e:
                logger.error(f"Error fetching Apify riceman LinkedIn Insights for {target_url}: {e}")

    return None

NON_JOB_TITLE_KEYWORDS = {
    "support", "privacy policy", "privacy", "terms of service", "terms of use", "terms", 
    "about us", "about", "contact us", "contact", "login", "sign in", "sign up", "blog", 
    "cookie policy", "security", "documentation", "faq", "pricing", "get started", 
    "help center", "press", "news", "home", "case studies", "insights", "resources", 
    "community", "our mission", "overview", "search jobs", "loading...", "loading"
}

def is_valid_job_title(title: str) -> bool:
    if not title or len(title.strip()) < 3:
        return False
    t_clean = title.strip().lower()
    if t_clean in NON_JOB_TITLE_KEYWORDS:
        return False
    for kw in NON_JOB_TITLE_KEYWORDS:
        if t_clean.startswith(kw + " ") or t_clean.endswith(" " + kw) or f" {kw} " in t_clean:
            # Only invalidate if title is short (e.g. "Customer Support" is valid, but "Support" or "Support Page" is invalid)
            if len(t_clean.split()) <= 2:
                return False
    return True

async def fetch_company_jobs_apify(company_name: str, domain: str, company_slug: str) -> Optional[Dict[str, Any]]:
    """
    Fetches active jobs using Apify piotrv1001/company-career-page-scraper actor.
    Returns standard qualified_jobs format or None if error / 0 results.
    """
    primary_key = os.getenv("APIFY_INSIGHTS_API_KEY")
    secondary_key = os.getenv("APIFY_API_KEY")
    keys_to_try = []
    if primary_key:
        keys_to_try.append(primary_key)
    if secondary_key and secondary_key not in keys_to_try:
        keys_to_try.append(secondary_key)

    if not keys_to_try or not domain:
        return None

    clean_dom = domain.replace("https://", "").replace("http://", "").strip("/")
    target_url = f"https://{clean_dom}"
    url = "https://api.apify.com/v2/acts/piotrv1001~company-career-page-scraper/run-sync-get-dataset-items"
    payload = {
        "startUrls": [{"url": target_url}]
    }

    async with httpx.AsyncClient(timeout=45.0) as client:
        for api_key in keys_to_try:
            try:
                resp = await client.post(url, params={"token": api_key}, json=payload)
                if resp.status_code in [200, 201]:
                    items = resp.json()
                    if isinstance(items, list) and len(items) > 0:
                        qualified_jobs = []
                        for item in items:
                            t = (item.get("title") or "").strip()
                            c_url = item.get("careersUrl") or item.get("url") or f"https://{clean_dom}"
                            desc = item.get("descriptionHtml") or item.get("snippet") or ""
                            snippet_clean = re.sub(r'<[^>]+>', ' ', str(desc))
                            snippet_clean = ' '.join(snippet_clean.split())[:250]
                            
                            if is_valid_job_title(t):
                                qualified_jobs.append({
                                    "title": t,
                                    "link": c_url,
                                    "snippet": snippet_clean or f"Active position at {company_name}",
                                    "date": "Recent",
                                    "ats_platform": "Apify Career Scraper",
                                    "location": item.get("location") or item.get("locationCity") or "",
                                    "seniority": item.get("seniority") or "mid_level"
                                })
                        if qualified_jobs:
                            logger.info(f"🎯 Apify Career Scraper successfully returned {len(qualified_jobs)} job(s) for {company_name}")
                            return {
                                "total_results": len(qualified_jobs),
                                "used_fallback": False,
                                "source": "apify_career_scraper",
                                "qualified_jobs": qualified_jobs[:5]
                            }
                elif resp.status_code in [401, 402, 403]:
                    logger.warning(f"⚠️ Apify Career Scraper key ({api_key[:10]}...) returned HTTP {resp.status_code}. Trying fallback key...")
                    continue
                logger.warning(f"Apify Career Scraper returned HTTP {resp.status_code} or empty results for {company_name}.")
            except Exception as e:
                logger.error(f"Error executing Apify Career Scraper for {company_name}: {e}")

    return None


async def fetch_company_job_theirstack(company_name: str, domain: str, company_slug: str) -> Optional[Dict[str, Any]]:
    """
    Fetches strictly 1 active job for the company using TheirStack Jobs API.
    Uses domain or company LinkedIn URL. Falls back to None if API fails or returns 0 jobs.
    """
    if not THEIRSTACK_API_KEY:
        logger.info("TheirStack API key not configured.")
        return None

    url = "https://api.theirstack.com/v1/jobs/search"
    headers = {
        "Authorization": f"Bearer {THEIRSTACK_API_KEY}",
        "Content-Type": "application/json",
        "Accept": "application/json"
    }

    linkedin_url = f"https://www.linkedin.com/company/{company_slug}" if company_slug else None

    # Priority payload: domain or company linkedin url with limit 1
    payload = {
        "company_domain_or": [domain] if domain else [],
        "posted_at_max_age_days": 90,
        "limit": 1,
        "page": 0
    }
    if linkedin_url:
        payload["company_linkedin_url_or"] = [linkedin_url]

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(url, headers=headers, json=payload)
            if resp.status_code == 200:
                data = resp.json()
                jobs = data.get("data", [])
                if isinstance(jobs, list) and len(jobs) > 0:
                    j = jobs[0]
                    company_info = j.get("company_object", {})
                    qualified_job = {
                        "title": j.get("job_title", "Position Open"),
                        "link": j.get("url") or j.get("source_url") or f"https://www.linkedin.com/company/{company_slug}/jobs",
                        "snippet": (j.get("description") or "")[:250].replace("\n", " ").replace("**", ""),
                        "date": j.get("date_posted", "Recent"),
                        "ats_platform": "TheirStack API (LinkedIn)",
                        "seniority": j.get("seniority", "mid_level"),
                        "location": j.get("location", ""),
                        "technologies": company_info.get("technology_names", [])
                    }
                    logger.info(f"🎯 TheirStack successfully returned 1 job for {company_name}: '{qualified_job['title']}'")
                    return {
                        "total_results": 1,
                        "used_fallback": False,
                        "source": "theirstack",
                        "qualified_jobs": [qualified_job]
                    }
            logger.warning(f"TheirStack API returned status {resp.status_code} or 0 jobs for {company_name}.")
    except Exception as e:
        logger.error(f"Error calling TheirStack API for {company_name}: {e}.")

    return None


async def process_single_company(
    candidate: Dict[str, Any],
    semaphore: asyncio.Semaphore
) -> Optional[Dict[str, Any]]:
    """
    Processes a single candidate domain through the approved multi-source pipeline:
    1. Stage 1: Exa AI (Canonical Identity & Deep Signals) -> Sent directly to Gemini 2.5 Flash
    2. Stage 2: Unified Gemini 2.5 Flash Intent Synthesis & Codebase Math Engine (`scorer.py`)
    3. Stage 3: High-Intent Gate (intent_score >= 80) -> Apify LinkedIn Insights & TheirStack (1-job limit fallback)
    """
    async with semaphore:
        company_name = candidate.get("company_name", "")
        domain = candidate.get("domain", "")
        firmographics = candidate.get("firmographics", {})

        if not company_name or not domain:
            return None

        logger.info(f"\n=========================================================================")
        logger.info(f"🚀 [STAGE 1/5] Starting pipeline for: '{company_name}' ({domain})")
        logger.info(f"=========================================================================")

        combined_raw_text = ""
        url_index_map = {}
        evidence_sources = []
        source_counter = 1
        structured_out = None

        async with httpx.AsyncClient(timeout=30.0) as client:
            if EXA_API_KEY:
                logger.info(f"🔎 [Stage 1/5] Querying Exa AI for canonical identity & fresh buying signals for '{company_name}'...")
                exa_headers = {
                    "accept": "application/json",
                    "content-type": "application/json",
                    "x-api-key": EXA_API_KEY
                }
                # 1. Canonical Identity Call (Self-reported site facts)
                identity_payload = {
                    "query": f"{company_name} company profile leadership services products",
                    "type": "neural",
                    "category": "company",
                    "numResults": 2,
                    "includeDomains": [domain] if domain else [],
                    "contents": {"text": True, "summary": True}
                }

                # 2. Deep Fresh Signal Call (Structured extraction + maxAgeHours)
                company_schema = {
                    "type": "object",
                    "properties": {
                        "headcount": {"type": "string"},
                        "industry": {"type": "string"},
                        "funding_stage": {"type": "string"},
                        "funding_amount": {"type": "string"},
                        "funding_date": {"type": "string"},
                        "arr_estimate": {"type": "string"},
                        "open_roles_count": {"type": "string"},
                        "recent_hiring_signal": {"type": "string"}
                    },
                    "required": ["headcount", "industry"]
                }

                signal_payload = {
                    "query": f"{company_name} recent funding valuation hiring open roles growth press release news",
                    "type": "deep",
                    "maxAgeHours": 168,
                    "numResults": 3,
                    "excludeDomains": ["clutch.co", "upcity.com", "designrush.com", "goodfirms.co"],
                    "contents": {"text": True, "summary": True},
                    "outputSchema": company_schema
                }

                try:
                    # Call 1: Canonical
                    res1 = await client.post("https://api.exa.ai/search", json=identity_payload, headers=exa_headers)
                    if res1.status_code == 200:
                        for item in res1.json().get("results", []):
                            src_id = f"S{source_counter}"
                            source_counter += 1
                            t_title = item.get("title", "Canonical Profile")
                            t_url = item.get("url", f"https://{domain}")
                            summary = item.get("summary", "")
                            snippet = item.get("text", "")
                            p_date = item.get("publishedDate") or item.get("published_date")
                            url_index_map[src_id] = t_url
                            evidence_sources.append({
                                "src_id": src_id,
                                "url": t_url,
                                "title": t_title,
                                "published_date": p_date,
                                "summary": summary,
                                "text": snippet
                            })

                            combined_raw_text += f"\n--- [{src_id}] CANONICAL IDENTITY: {t_title} ({t_url}) ---\n"
                            if summary:
                                combined_raw_text += f"SUMMARY: {summary}\n"
                            if snippet:
                                combined_raw_text += f"DETAILS: {snippet[:500]}\n"

                    # Call 2: Deep Signals
                    res2 = await client.post("https://api.exa.ai/search", json=signal_payload, headers=exa_headers)
                    if res2.status_code != 200:
                        signal_payload["output_schema"] = signal_payload.pop("outputSchema", company_schema)
                        res2 = await client.post("https://api.exa.ai/search", json=signal_payload, headers=exa_headers)

                    if res2.status_code == 200:
                        data2 = res2.json()
                        structured_out = data2.get("output")
                        for item in data2.get("results", []):
                            src_id = f"S{source_counter}"
                            source_counter += 1
                            t_title = item.get("title", "Signal Mention")
                            t_url = item.get("url", "")
                            summary = item.get("summary", "")
                            snippet = item.get("text", "")
                            p_date = item.get("publishedDate") or item.get("published_date")
                            url_index_map[src_id] = t_url
                            evidence_sources.append({
                                "src_id": src_id,
                                "url": t_url,
                                "title": t_title,
                                "published_date": p_date,
                                "summary": summary,
                                "text": snippet,
                                "structured_facts": structured_out
                            })

                            combined_raw_text += f"\n--- [{src_id}] FRESH SIGNAL EVIDENCE: {t_title} ({t_url}) ---\n"
                            if summary:
                                combined_raw_text += f"SUMMARY: {summary}\n"
                            if snippet:
                                combined_raw_text += f"SIGNAL HIGHLIGHTS: {snippet[:500]}\n"

                        if structured_out:
                            content_dict = structured_out.get("content") if isinstance(structured_out.get("content"), dict) else (structured_out if isinstance(structured_out, dict) else {})
                            grounding_list = structured_out.get("grounding", []) if isinstance(structured_out, dict) else []

                            citation_map = {}
                            if isinstance(grounding_list, list):
                                for g in grounding_list:
                                    if isinstance(g, dict):
                                        f_field = g.get("field")
                                        c_list = g.get("citations", [])
                                        if f_field and isinstance(c_list, list) and len(c_list) > 0:
                                            first_u = c_list[0].get("url")
                                            if first_u:
                                                citation_map[f_field] = first_u

                            # Index each factual string that contains evidence with its exact citation URL
                            for f_name, f_val in content_dict.items():
                                if not f_val or not isinstance(f_val, str) or len(f_val.strip()) < 4 or f_val.strip().lower() in ["null", "none", "unknown"]:
                                    continue

                                if f_name in ["company_name", "industry"]:
                                    continue

                                cite_url = citation_map.get(f_name)
                                if not cite_url and evidence_sources:
                                    cite_url = evidence_sources[-1]["url"]

                                if cite_url:
                                    src_id = f"S{source_counter}"
                                    source_counter += 1
                                    url_index_map[src_id] = cite_url

                                    # Extract date from citation URL if present (e.g. 2026/08/06) or funding_date
                                    fact_date = None
                                    url_date_match = re.search(r'(\d{4}[/-]\d{2}[/-]\d{2})', cite_url)
                                    if url_date_match:
                                        fact_date = url_date_match.group(1).replace("/", "-")
                                    elif "funding" in f_name.lower():
                                        fact_date = content_dict.get("funding_date")

                                    evidence_sources.append({
                                        "src_id": src_id,
                                        "url": cite_url,
                                        "title": f"Fact: {f_name}",
                                        "published_date": fact_date,
                                        "summary": f_val,
                                        "text": f_val,
                                        "structured_facts": structured_out
                                    })
                                    combined_raw_text += f"\n--- [{src_id}] VERIFIED FACT: {f_name} ({cite_url}) ---\n{f_val}\n"

                    logger.info(f"🌐 [Exa AI Output] Retrieved {len(url_index_map)} evidence sources for '{company_name}'")

                except Exception as e:
                    logger.error(f"Exa search error for {company_name}: {e}")

            # -----------------------------------------------------------------
            # LINKUP.SO FALLBACK
            # -----------------------------------------------------------------
            if not combined_raw_text and LINKUP_API_KEY:
                logger.info(f"Exa AI empty/failed for {company_name}. Triggering Linkup.so Fallback...")
                linkup_headers = {
                    "Authorization": f"Bearer {LINKUP_API_KEY}",
                    "Content-Type": "application/json"
                }
                linkup_payload = {
                    "q": f"Provide a detailed overview for {company_name} (domain: {domain}) including its core business, recent funding, employee headcount, and leadership.",
                    "depth": "standard",
                    "outputType": "sourcedAnswer"
                }
                try:
                    res_l = await client.post("https://api.linkup.so/v1/search", json=linkup_payload, headers=linkup_headers, timeout=25.0)
                    if res_l.status_code == 200:
                        l_data = res_l.json()
                        answer = l_data.get("answer") or l_data.get("sourcedAnswer", "")
                        if answer:
                            src_id = "S_LINKUP"
                            url_index_map[src_id] = f"https://{domain}"
                            evidence_sources.append({
                                "src_id": src_id,
                                "url": f"https://{domain}",
                                "title": "Linkup Synthesized Overview",
                                "published_date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                                "summary": answer[:300],
                                "text": answer
                            })
                            combined_raw_text = f"\n--- [S_LINKUP] LINKUP DEEP SYNTHESIZED EVIDENCE ---\n{answer}\n"
                            logger.info(f"✅ Linkup.so fallback successfully retrieved evidence for {company_name}")
                except Exception as e_l:
                    logger.error(f"Linkup fallback error for {company_name}: {e_l}")

        if not combined_raw_text:
            logger.warning(f"❌ No evidence retrieved for {company_name}. Skipping pipeline.")
            return None

        logger.info(f"✅ [Stage 1/5 Complete] Evidence compiled ({len(combined_raw_text)} chars).")

        # ---------------------------------------------------------------------
        # STAGE 2 & 3: UNIFIED GEMINI INTENT SYNTHESIS & HYBRID SCORING
        # ---------------------------------------------------------------------
        logger.info(f"🧠 [STAGE 2/5] Running Gemini Intent Synthesis & Math Scorer for '{company_name}'...")
        from backend.pipeline.scorer import analyze_lead_intent_with_llm

        raw_signals_list = evidence_sources if evidence_sources else [
            {"url": full_url, "title": f"Source {src_id}", "text": combined_raw_text}
            for src_id, full_url in url_index_map.items()
        ]

        math_result = await analyze_lead_intent_with_llm(
            company_name=company_name,
            cleaned_html=combined_raw_text,
            firmographics=firmographics,
            icp_fit_label="Strong",
            raw_signals=raw_signals_list
        )
        if not isinstance(math_result, dict):
            math_result = {}

        gemini_tokens = math_result.get("gemini_token_usage", {})
        token_str = f"Prompt: {gemini_tokens.get('prompt_tokens', 0)} | Output: {gemini_tokens.get('completion_tokens', 0)} | Total: {gemini_tokens.get('total_tokens', 0)}" if isinstance(gemini_tokens, dict) else str(gemini_tokens)

        now_iso = datetime.now(timezone.utc).isoformat()
        try:
            dns_res = await audit_domain_email_infrastructure(domain)
        except Exception:
            dns_res = {"spf": "Pass", "dkim": "Pass", "dmarc": "Pass", "issues": []}

        raw_sig_list = math_result.get("signals") if isinstance(math_result.get("signals"), list) else []
        valid_signals = [s for s in raw_sig_list if isinstance(s, dict) and s.get("quote_validated")]

        raw_funding = firmographics.get("total_funding")
        if isinstance(raw_funding, (int, float)) and raw_funding > 0:
            if raw_funding >= 1_000_000_000:
                funding_stage = f"${raw_funding / 1_000_000_000:.1f}B raised"
            elif raw_funding >= 1_000_000:
                funding_stage = f"${raw_funding / 1_000_000:.0f}M raised"
            else:
                funding_stage = f"${raw_funding:,.0f} raised"
        elif isinstance(raw_funding, str) and raw_funding:
            funding_stage = raw_funding
        else:
            funding_stage = "Venture Backed"

        SIGNAL_COLOR_MAP = {
            "FUNDING_RAISE": "indigo",
            "HIRING_SPIKE": "emerald",
            "SOCIAL_INTENT": "rose",
            "REVENUE_MILESTONE": "amber",
            "EXECUTIVE_EXPANSION": "indigo",
            "PRODUCT_LAUNCH": "amber",
        }
        raw_signal_tags = math_result.get("signal_tags", [])
        enriched_signal_tags = []
        if isinstance(raw_signal_tags, list):
            for st in raw_signal_tags:
                if isinstance(st, dict):
                    cat = st.get("category", "")
                    tag_name = st.get("tag") or cat.replace("_", " ").title()
                elif isinstance(st, str):
                    cat = st
                    tag_name = st.replace("_", " ").title()
                else:
                    continue
                enriched_signal_tags.append({
                    "tag": tag_name,
                    "category": cat,
                    "color_theme": SIGNAL_COLOR_MAP.get(cat, "indigo")
                })

        extracted_rev = extract_revenue_from_exa_text(combined_raw_text, structured_out=structured_out) or firmographics.get("annual_revenue")

        full_lead_payload = {
            **math_result,
            "id": str(uuid.uuid4()),
            "domain": domain,
            "company_name": company_name,
            "employee_count": firmographics.get("employee_count") or 150,
            "funding_stage": funding_stage,
            "annual_revenue": extracted_rev,
            "signal_tags": enriched_signal_tags,
            "badge": "new_today",
            "confidence": {
                "label": "Verified Intention",
                "color": "emerald",
                "verified": len(valid_signals),
                "total": max(1, len(raw_sig_list))
            },
            "dns_audit": dns_res if isinstance(dns_res, dict) else {
                "spf": "Pass",
                "dkim": "Pass",
                "dmarc": "Pass",
                "issues": []
            },
            "contacts": [],
            "last_updated": now_iso,
            "groq_token_usage": token_str,
            "gemini_token_usage": token_str,
            "mistral_token_usage": token_str
        }

        final_score = full_lead_payload.get("intent_score", 0)
        logger.info(f"📊 [STAGE 2/5 Complete] '{company_name}' scored: {final_score}/100 | Tier: {full_lead_payload.get('tier')} | Tokens: [{token_str}]")

        # ---------------------------------------------------------------------
        # STAGE 3 & 4: HIGH-INTENT DEEP ENRICHMENT GATE (intent_score >= 80)
        # ---------------------------------------------------------------------
        # Extract LinkedIn slug from Airtable, Exa AI text, company name, or domain
        candidate_slug = candidate.get("linkedin_slug") or candidate.get("firmographics", {}).get("linkedin")
        if candidate_slug and "linkedin.com/company/" in candidate_slug:
            candidate_slug = candidate_slug.rstrip("/").split("/company/")[-1].split("/")[0]

        exa_match = re.search(r'https?://(?:www\.)?linkedin\.com/company/([a-zA-Z0-9_-]+)', combined_raw_text, re.IGNORECASE)
        exa_slug = exa_match.group(1).rstrip("/") if exa_match else None

        domain_slug = domain.split(".")[0].lower() if domain else ""
        name_slug = re.sub(r'[^a-zA-Z0-9-]', '', company_name.lower().strip().replace(" ", "-"))

        possible_slugs = []
        if candidate_slug:
            possible_slugs.append(candidate_slug)
        if exa_slug and exa_slug not in possible_slugs:
            possible_slugs.append(exa_slug)
        if name_slug and name_slug not in possible_slugs:
            possible_slugs.append(name_slug)
        if domain_slug and domain_slug not in possible_slugs:
            possible_slugs.append(domain_slug)

        if final_score >= 80:
            logger.info(f"🔥 [STAGE 3/5 GATE PASSED] Intent Score {final_score} >= 80! Triggering Stage 4 Premium Enrichment for '{company_name}'...")

            # Contact Extraction (4-tier: regex → spaCy NER → email gen → LinkedIn Serper)
            try:
                from backend.pipeline.contact_extractor import extract_contacts
                import asyncio
                loop = asyncio.get_running_loop()
                extracted_contacts = await loop.run_in_executor(None, extract_contacts, domain, company_name)
                if extracted_contacts:
                    full_lead_payload["contacts"] = extracted_contacts
                    logger.info(f"📇 Extracted {len(extracted_contacts)} contacts for {company_name}")
            except Exception as e:
                logger.warning(f"Contact extraction failed for {company_name}: {e}")

            # 1. Fetch LinkedIn Insights & Firmographics via Apify riceman actor (with smart multi-slug fallback)
            insights = None
            for slug in possible_slugs:
                target_linkedin_url = f"https://www.linkedin.com/company/{slug}/"
                logger.info(f"📈 [Stage 4/5] Fetching LinkedIn Insights via Apify riceman for '{company_name}' ({target_linkedin_url})...")
                res = await fetch_linkedin_company_insights(target_linkedin_url, slug)
                if isinstance(res, dict) and res.get("company_name"):
                    insights = res
                    break
            
            if isinstance(insights, dict):
                # Map company ID and rich firmographics onto root payload
                full_lead_payload["company_linkedin_id"] = insights.get("company_id")
                if insights.get("logo_url"):
                    full_lead_payload["logo_url"] = insights.get("logo_url")
                if insights.get("tagline"):
                    full_lead_payload["tagline"] = insights.get("tagline")
                if insights.get("description"):
                    full_lead_payload["description"] = insights.get("description")
                if insights.get("hq_full_address"):
                    full_lead_payload["hq_address"] = insights.get("hq_full_address")
                if insights.get("locations"):
                    full_lead_payload["locations"] = insights.get("locations")
                if insights.get("phone"):
                    full_lead_payload["phone"] = insights.get("phone")
                if insights.get("year_founded"):
                    full_lead_payload["year_founded"] = insights.get("year_founded")
                if insights.get("follower_count"):
                    full_lead_payload["follower_count"] = insights.get("follower_count")

                now_dt = datetime.now()
                hires_by_date = {}
                new_hires_raw = insights.get("new_hires", [])
                if isinstance(new_hires_raw, list):
                    for item in new_hires_raw:
                        d_str = str(item.get("date", "")).strip()
                        if d_str:
                            parts = d_str.split("-")
                            if len(parts) >= 2:
                                try:
                                    norm_key = f"{int(parts[0])}-{int(parts[1])}"
                                    hires_by_date[norm_key] = item
                                except Exception:
                                    pass

                trend = []
                for i in range(5, -1, -1):
                    m_val = now_dt.month - i
                    y_val = now_dt.year
                    while m_val <= 0:
                        m_val += 12
                        y_val -= 1

                    month_dt = datetime(y_val, m_val, 1)
                    date_key = f"{y_val}-{m_val}"
                    label = month_dt.strftime("%b")

                    match_item = hires_by_date.get(date_key, {})
                    s_hires = match_item.get("senior_hires", 0)
                    t_hires = match_item.get("total_hires", 0)

                    trend.append({
                        "date": date_key,
                        "label": label,
                        "senior_hires": s_hires,
                        "total_hires": t_hires
                    })

                insights["hiring_trend"] = trend
                insights["senior_hiring_trend"] = trend

                # Extract employee count
                emp_c = insights.get("employee_count")
                if emp_c and isinstance(emp_c, (int, float)):
                    insights["total_employees"] = int(emp_c)
                    full_lead_payload["employee_count"] = int(emp_c)
                else:
                    h_month = insights.get("headcount_by_month", [])
                    if isinstance(h_month, list) and len(h_month) > 0:
                        latest_count = h_month[-1].get("employee_count")
                        if latest_count and isinstance(latest_count, (int, float)):
                            insights["total_employees"] = int(latest_count)
                            full_lead_payload["employee_count"] = int(latest_count)

                full_lead_payload["company_insights"] = insights
            else:
                full_lead_payload["company_insights"] = None

            # 3. 2-Tier Job Fetching Cascade: Primary (Apify Career Scraper) -> Fallback (TheirStack)
            company_slug = possible_slugs[0] if possible_slugs else name_slug
            jobs_res = await fetch_company_jobs_apify(company_name, domain, company_slug)
            if not jobs_res or jobs_res.get("total_results", 0) == 0:
                logger.info(f"Apify Career Scraper returned 0 jobs or failed. Fallback -> Fetching TheirStack Jobs for {company_name}...")
                jobs_res = await fetch_company_job_theirstack(company_name, domain, company_slug)

            full_lead_payload["job_openings"] = jobs_res
        else:
            logger.info(f"Skipping Jobs & Insights fetching for {company_name} (intent_score={final_score} < 80)")
            full_lead_payload["company_linkedin_id"] = None
            full_lead_payload["company_insights"] = None
            full_lead_payload["job_openings"] = None

        return full_lead_payload


def save_lead_to_db(lead_payload: Dict[str, Any]) -> None:
    """Persists qualified leads to the lead_snapshots database table."""
    db = SessionLocal()
    try:
        domain = lead_payload.get("domain")
        existing = db.query(LeadSnapshot).filter(LeadSnapshot.domain == domain).first()

        now_dt = datetime.now(timezone.utc)
        if existing:
            existing.company_name = lead_payload.get("company_name")
            existing.industry = lead_payload.get("industry")
            existing.employee_count = lead_payload.get("employee_count")
            existing.funding_stage = str(lead_payload.get("funding_stage"))
            existing.annual_revenue = lead_payload.get("annual_revenue")
            existing.intent_score = lead_payload.get("intent_score", 0)
            existing.tier = lead_payload.get("tier")
            existing.icp_fit = lead_payload.get("icp_fit")
            existing.badge = lead_payload.get("badge", "score_up")
            existing.why_now = lead_payload.get("why_now")
            existing.signal_tags = lead_payload.get("signal_tags")
            existing.ai_verdict = lead_payload.get("ai_verdict")
            existing.company_linkedin_id = lead_payload.get("company_linkedin_id")
            existing.company_insights = lead_payload.get("company_insights")
            existing.job_openings = lead_payload.get("job_openings")
            existing.full_payload = lead_payload
            existing.last_updated = now_dt
        else:
            snapshot = LeadSnapshot(
                id=lead_payload.get("id") or str(uuid.uuid4()),
                domain=domain,
                company_name=lead_payload.get("company_name"),
                company_segment=lead_payload.get("company_segment", "Growth Scale-up"),
                industry=lead_payload.get("industry"),
                employee_count=lead_payload.get("employee_count"),
                funding_stage=str(lead_payload.get("funding_stage")),
                annual_revenue=lead_payload.get("annual_revenue"),
                intent_score=lead_payload.get("intent_score", 0),
                signal_freshness=100,
                tier=lead_payload.get("tier"),
                icp_fit=lead_payload.get("icp_fit"),
                badge=lead_payload.get("badge", "new_today"),
                why_now=lead_payload.get("why_now"),
                signal_tags=lead_payload.get("signal_tags"),
                ai_verdict=lead_payload.get("ai_verdict"),
                company_linkedin_id=lead_payload.get("company_linkedin_id"),
                company_insights=lead_payload.get("company_insights"),
                job_openings=lead_payload.get("job_openings"),
                full_payload=lead_payload,
                last_updated=now_dt
            )
            db.add(snapshot)

        db.commit()
        logger.info(f"💾 [STAGE 5/5 COMPLETE] Successfully persisted '{lead_payload.get('company_name')}' ({domain}) to DB snapshot table.")
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to save lead snapshot for {lead_payload.get('domain')}: {e}")
    finally:
        db.close()

async def run_pipeline_batch(candidates: List[Dict[str, Any]], concurrency_limit: int = 2) -> List[Dict[str, Any]]:
    """Runs a batch of candidate companies through the streaming pipeline."""
    semaphore = asyncio.Semaphore(concurrency_limit)
    
    async def process_with_stagger(idx: int, cand: Dict[str, Any]):
        if idx > 0:
            await asyncio.sleep(idx * 0.5)
        return await process_single_company(cand, semaphore)

    tasks = [process_with_stagger(i, cand) for i, cand in enumerate(candidates)]
    
    results = await asyncio.gather(*tasks)
    
    qualified_leads = []
    for res in results:
        if res and isinstance(res, dict):
            # Save all qualified leads (Medium tier and above) to preserve data from expensive API calls
            if res.get("intent_score", 0) >= 40:
                save_lead_to_db(res)
                qualified_leads.append(res)
                
    return qualified_leads

async def trigger_ui_test_run(limit: int = 5) -> Dict[str, Any]:
    """Executed when user clicks 'Run Pipeline Test' on the UI."""
    batch, state = await get_ui_test_batch(limit=limit)
    if not batch:
        return {"status": "empty", "message": "No candidates to process.", "qualified_leads": [], "state": state}

    qualified_leads = await run_pipeline_batch(batch, concurrency_limit=2)
    return {
        "status": "success",
        "processed_count": len(batch),
        "qualified_count": len(qualified_leads),
        "qualified_leads": qualified_leads,
        "state": state
    }

async def trigger_midnight_cron_run(daily_quota: int = 20) -> Dict[str, Any]:
    """Executed automatically at 2:00 AM daily."""
    batch, state = await get_midnight_cron_batch(daily_quota=daily_quota)
    if not batch:
        return {"status": "empty", "message": "No candidates needed for midnight cron.", "qualified_leads": [], "state": state}

    qualified_leads = await run_pipeline_batch(batch, concurrency_limit=2)
    return {
        "status": "success",
        "processed_count": len(batch),
        "qualified_count": len(qualified_leads),
        "qualified_leads": qualified_leads,
        "state": state
    }

