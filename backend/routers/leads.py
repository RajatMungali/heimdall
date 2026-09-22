from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Literal, Optional, List, cast, Dict, Any
from datetime import datetime, timezone
import uuid
import json
import re
from backend.utils.logger import logger

from backend.pipeline.discovery import fetch_public_intent_signals

from backend.pipeline.dns_audit import audit_domain_email_infrastructure
from backend.models import LeadSnapshot
from backend.database import SessionLocal, get_db

router = APIRouter(prefix="/api/leads", tags=["Lead Intelligence Operations"])


# ======================================================================
# Pydantic models — STRICT DATA CONTRACT PROTOCOL
# All keys match the contract exactly. Do not shorten or modify casing.
# ======================================================================

class SignalModel(BaseModel):
    """Extracted Signal Objective Object"""
    signal_type: str
    verbatim_quote: str
    quote_validated: bool
    similarity_score: float
    source_url: Optional[str] = None
    recency_label: str
    event_date: Optional[str] = None
    score_contribution: float


class DNSAuditModel(BaseModel):
    """DNS Audit Objective Object"""
    spf: str
    dkim: str
    dmarc: str
    issues: List[str]


class ConfidenceModel(BaseModel):
    """Confidence Evaluation Object"""
    label: str
    color: str
    verified: int
    total: int


class ContactModel(BaseModel):
    """Extracted Contact Object"""
    name: str
    title: str
    email: str
    confidence: str | int
    source: Optional[str] = None


from pydantic import BaseModel, Field

class SignalTagModel(BaseModel):
    """Visual Intent Chip Object"""
    tag: str = "Intent Signal"
    category: str = "HIRING_SPIKE"
    color_theme: str = "indigo"



class LeadDetailResponse(BaseModel):
    """
    Master Lead Object — Strict Data Contract Protocol.

    Fields:
        intent_score:      DO NOT use 'score'
        signal_freshness:  DO NOT use 'freshness'
        badge:             'new_today' | 'score_up' | 'score_down' | 'signal_added' | null
    """
    id: str
    company_name: str
    domain: str
    industry: str
    company_segment: Optional[str] = "Growth Scale-up"
    employee_count: Optional[int] = None
    funding_stage: Optional[str] = None
    intent_score: int
    signal_freshness: int
    tier: Literal["High", "Medium", "Low"]
    icp_fit: Literal["Strong", "Partial", "Poor"]
    confidence: ConfidenceModel
    why_now: str = Field(
        default="Verified public buying intent triggers detected. Recommend targeted outreach.",
        description="2-sentence catalyst and strategic opportunity statement."
    )
    signal_tags: List[SignalTagModel] = Field(default_factory=list)
    badge: Optional[Literal["new_today", "score_up", "score_down", "signal_added", "filtered"]] = None
    social_segment: Optional[str] = None
    meta_ads_active: Optional[bool] = False
    meta_ads_count: Optional[int] = 0
    bio_url: Optional[str] = None
    signals: List[SignalModel]
    ai_verdict: str
    dns_audit: DNSAuditModel
    contacts: List[ContactModel] = []
    company_linkedin_id: Optional[str] = None
    annual_revenue: Optional[str] = None
    company_insights: Optional[Dict[str, Any]] = None
    job_openings: Optional[Dict[str, Any]] = None
    last_updated: str


# ======================================================================
# API Endpoints
# ======================================================================

@router.get("/", response_model=List[LeadDetailResponse])
def list_all_leads():
    """Returns a list of all processed leads from the database with bounded confidence scores."""
    db = SessionLocal()
    try:
        leads = db.query(LeadSnapshot).all()
        results = []
        for lead in leads:
            if not lead.full_payload:
                continue
            payload = dict(lead.full_payload)
            payload["id"] = lead.id
            if lead.company_linkedin_id:
                payload["company_linkedin_id"] = lead.company_linkedin_id
            if lead.annual_revenue:
                payload["annual_revenue"] = lead.annual_revenue
            if lead.job_openings is not None:
                payload["job_openings"] = lead.job_openings
            if lead.employee_count is not None:
                payload["employee_count"] = lead.employee_count
            if lead.company_insights is not None:
                payload["company_insights"] = lead.company_insights
            if isinstance(payload.get("confidence"), dict):
                ver = payload["confidence"].get("verified", 0)
                if ver > 100:
                    payload["confidence"]["verified"] = min(100, max(0, ver))
            if lead.last_updated:
                payload["last_updated"] = lead.last_updated.isoformat()
            elif not payload.get("last_updated"):
                payload["last_updated"] = datetime.now(timezone.utc).isoformat()

            # Sanitize funding_stage: must be a string
            fs = payload.get("funding_stage")
            if isinstance(fs, (int, float)):
                if fs >= 1_000_000_000:
                    payload["funding_stage"] = f"${fs / 1_000_000_000:.1f}B raised"
                elif fs >= 1_000_000:
                    payload["funding_stage"] = f"${fs / 1_000_000:.0f}M raised"
                elif fs > 0:
                    payload["funding_stage"] = f"${fs:,.0f} raised"
                else:
                    payload["funding_stage"] = "Venture Backed"

            # Sanitize signal_tags: must have tag + category + color_theme
            SIGNAL_COLOR_MAP = {
                "FUNDING_RAISE": "indigo", "HIRING_SPIKE": "emerald",
                "SOCIAL_INTENT": "rose", "REVENUE_MILESTONE": "amber",
                "EXECUTIVE_EXPANSION": "indigo", "PRODUCT_LAUNCH": "amber",
            }
            raw_tags = payload.get("signal_tags", [])
            if raw_tags and isinstance(raw_tags, list):
                fixed_tags = []
                for st in raw_tags:
                    if isinstance(st, dict):
                        cat = st.get("category", "")
                        fixed_tags.append({
                            "tag": st.get("tag") or cat.replace("_", " ").title(),
                            "category": cat,
                            "color_theme": st.get("color_theme") or SIGNAL_COLOR_MAP.get(cat, "indigo")
                        })
                payload["signal_tags"] = fixed_tags

            lead_score = payload.get("intent_score") or payload.get("icp_score") or 0
            if lead_score >= 80:
                results.append(payload)

        # Always score-descending within each bucket. Never surface the weakest lead first.
        results.sort(
            key=lambda p: (
                p.get("icp_score") if p.get("icp_score") is not None else p.get("intent_score", 0)
            ),
            reverse=True
        )
        return results
    except Exception as e:
        logger.error(f"Error fetching lead snapshots: {e}")
        return []
    finally:
        db.close()


@router.get("/{lead_id}", response_model=LeadDetailResponse)
def get_lead_profile_details(lead_id: str):
    """Fetches full analytical records along with data ledger validation quotes."""
    db = SessionLocal()
    try:
        lead = db.query(LeadSnapshot).filter(
            (LeadSnapshot.id == lead_id) | (LeadSnapshot.domain.ilike(f"%{lead_id}%"))
        ).first()
        if not lead or not lead.full_payload:
            raise HTTPException(
                status_code=404,
                detail="Requested lead tracking index not found."
            )
        payload = dict(lead.full_payload)
        payload["id"] = lead.id
        if lead.company_linkedin_id:
            payload["company_linkedin_id"] = lead.company_linkedin_id
        if lead.annual_revenue:
            payload["annual_revenue"] = lead.annual_revenue
        if lead.job_openings is not None:
            payload["job_openings"] = lead.job_openings
        if lead.employee_count is not None:
            payload["employee_count"] = lead.employee_count
        if lead.company_insights is not None:
            payload["company_insights"] = lead.company_insights
        if isinstance(payload.get("confidence"), dict):
            ver = payload["confidence"].get("verified", 0)
            if ver > 100:
                payload["confidence"]["verified"] = min(100, max(0, ver))
        return payload
    finally:
        db.close()


@router.delete("/{lead_id}")
def delete_lead_record(lead_id: str, db: Session = Depends(get_db)):
    """Removes a lead record from the persistent tracking database by ID, domain, or company_name."""
    try:
        lead = db.query(LeadSnapshot).filter(
            (LeadSnapshot.id == lead_id) | 
            (LeadSnapshot.domain == lead_id) |
            (LeadSnapshot.company_name == lead_id)
        ).first()
        
        if not lead:
            # Fallback search across all snapshots for matching payload ID
            all_leads = db.query(LeadSnapshot).all()
            for l in all_leads:
                if l.full_payload and isinstance(l.full_payload, dict) and l.full_payload.get("id") == lead_id:
                    lead = l
                    break

        if not lead:
            raise HTTPException(
                status_code=404,
                detail=f"Lead record '{lead_id}' not found."
            )
        
        db.delete(lead)
        db.commit()
        logger.info(f"🗑️ Successfully deleted lead record: '{lead.company_name}' ({lead.domain}) [ID: {lead_id}]")
        return {"status": "deleted", "id": lead_id}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error deleting lead record {lead_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{lead_id}/verdict")
def get_lazy_loaded_pitch_verdict(lead_id: str):
    """
    Phase 5.5 — Pitcher Mode / Research AI. Uses OpenRouter API for high-quality
    intent signal summaries around Hiring, Funding, Leadership Change, and Growth.
    Falls back to Groq and Gemini if OpenRouter is unavailable.
    """
    db = SessionLocal()
    try:
        lead_snap = db.query(LeadSnapshot).filter(
            (LeadSnapshot.id == lead_id) | (LeadSnapshot.domain.ilike(f"%{lead_id}%"))
        ).first()
        if not lead_snap or not lead_snap.full_payload:
            raise HTTPException(
                status_code=404,
                detail="Requested lead target vector not found."
            )
        payload = dict(lead_snap.full_payload)
        payload["id"] = lead_snap.id
        lead = LeadDetailResponse(**cast(dict, payload))
    finally:
        db.close()

    from backend.config import settings

    # Primary: OpenRouter Pitcher AI engine
    if settings.OPENROUTER_API_KEY:
        result = _generate_pitch_with_openrouter(lead, settings.OPENROUTER_API_KEY)
        if result:
            return {"lead_id": lead_id, **result}

    # Secondary: Groq Pitcher AI engine
    if settings.GROQ_API_KEY:
        result = _generate_pitch_with_groq(lead, settings.GROQ_API_KEY)
        if result:
            return {"lead_id": lead_id, **result}

    # Tertiary Fallback: Gemini Pitcher engine
    result = _generate_pitch_with_gemini(lead)
    return {"lead_id": lead_id, **result}


def _generate_pitch_with_openrouter(lead: LeadDetailResponse, api_key: str) -> dict | None:
    """
    Uses OpenRouter LLM API to generate a focused intent synopsis around
    Hiring, Funding, Leadership Change, and Growth signals.
    """
    import json
    import httpx
    import re

    try:
        signals_text = "\n".join([f"- {s.signal_type}: {s.verbatim_quote}" for s in lead.signals]) if lead.signals else "No specific signals extracted."
        
        prompt = f"""Generate a structured, point-wise synopsis of key buying intent signals for {lead.company_name}.

Main AI Verdict: {lead.ai_verdict}

Extracted Signals & Triggers:
{signals_text}

CRITICAL PROMPT INSTRUCTIONS:
1. FOCUS STRICTLY ON CORE SIGNALS: Provide a clear synopsis specifically around high-value buying signals:
   - Hiring (new SDRs, C-level roles, marketing/sales team expansion)
   - Funding (recent investment rounds, venture capital, seed/series investment)
   - Leadership Change (new executives, fractional leadership, key executive hires)
   - Growth & Scaling (new office locations, revenue milestones, expansion)
   - DO NOT include generic or random press release news.
2. FORMATTING:
   - Do NOT write an email. Do NOT include greetings (e.g., 'Hi [Name]') or sign-offs (e.g., 'Best').
   - Output MUST be a clean, point-wise brief formatted in markdown bullet points.
3. JSON OUTPUT SCHEMA:
   - Your ENTIRE response MUST be a valid JSON object matching exactly: {{"subject_line": "Intent Summary for {lead.company_name}", "email_body": "markdown bulleted summary text"}}"""

        response = httpx.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://prospector.ai",
                "X-Title": "Prospector AI"
            },
            json={
                "model": "meta-llama/llama-3.3-70b-instruct",
                "messages": [
                    {"role": "system", "content": "You are Pitcher AI, an expert sales intelligence analyst. You output raw JSON matching the schema."},
                    {"role": "user", "content": prompt}
                ],
                "response_format": {"type": "json_object"},
                "temperature": 0.3
            },
            timeout=30.0
        )
        response.raise_for_status()
        raw = response.json()["choices"][0]["message"]["content"]
        
        parsed = _clean_and_parse_json(raw)
        if isinstance(parsed, dict):
            return {
                "subject_line": parsed.get("subject_line", f"Intent Summary for {lead.company_name}"),
                "email_body": parsed.get("email_body", raw),
                "model_used": "OpenRouter Llama 3.3 70B (Pitcher AI)"
            }
    except Exception as e:
        print(f"[OpenRouter Pitcher AI Error] {e}")
    return None


def _clean_and_parse_json(raw_text: str) -> dict | None:
    """Helper to safely parse JSON strings from LLMs with unescaped control characters or markdown blocks."""
    if not raw_text:
        return None
    cleaned = raw_text.strip()
    if "```json" in cleaned:
        cleaned = cleaned.split("```json")[1].split("```")[0].strip()
    elif "```" in cleaned:
        cleaned = cleaned.split("```")[1].split("```")[0].strip()

    match = re.search(r'\{.*\}', cleaned, re.DOTALL)
    json_str = match.group(0) if match else cleaned

    try:
        return json.loads(json_str, strict=False)
    except Exception:
        # Replace unescaped control characters inside JSON strings
        sanitized = re.sub(r'[\x00-\x1f\x7f-\x9f]', lambda m: '\\n' if m.group(0) == '\n' else ('\\t' if m.group(0) == '\t' else ''), json_str)
        try:
            return json.loads(sanitized, strict=False)
        except Exception:
            return None


def _generate_pitch_with_groq(lead: LeadDetailResponse, api_key: str) -> dict | None:
    """
    Uses Groq LLM API as the dedicated Pitcher AI generator.
    """
    import json
    import httpx
    import re

    try:
        signals_text = "\n".join([f"- {s.signal_type}: {s.verbatim_quote}" for s in lead.signals]) if lead.signals else "No specific signals extracted."
        
        prompt = f"""Generate a structured, point-wise synopsis of key buying intent signals for {lead.company_name}.

Main AI Verdict: {lead.ai_verdict}

Extracted Signals & Triggers:
{signals_text}

CRITICAL PROMPT INSTRUCTIONS:
1. FOCUS STRICTLY ON CORE SIGNALS: Provide a clear synopsis specifically around high-value buying signals:
   - Hiring (new SDRs, C-level roles, marketing/sales team expansion)
   - Funding (recent investment rounds, venture capital, seed/series investment)
   - Leadership Change (new executives, fractional leadership, key executive hires)
   - Growth & Scaling (new office locations, revenue milestones, expansion)
   - DO NOT include generic or random press release news.
2. FORMATTING:
   - Do NOT write an email. Do NOT include greetings (e.g., 'Hi [Name]') or sign-offs (e.g., 'Best').
   - Output MUST be a clean, point-wise brief formatted in markdown bullet points.
3. JSON OUTPUT SCHEMA:
   - Your ENTIRE response MUST be a valid JSON object matching exactly: {{"subject_line": "Intent Summary for {lead.company_name}", "email_body": "markdown bulleted summary text"}}"""

        response = httpx.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            },
            json={
                "model": "oss-120b",
                "messages": [
                    {"role": "system", "content": "You are Pitcher AI, an expert sales intelligence analyst. You output raw JSON matching the schema."},
                    {"role": "user", "content": prompt}
                ],
                "response_format": {"type": "json_object"},
                "temperature": 0.3
            },
            timeout=30.0
        )
        response.raise_for_status()
        raw = response.json()["choices"][0]["message"]["content"]
        
        parsed = _clean_and_parse_json(raw)
        if isinstance(parsed, dict):
            return {
                "subject_line": parsed.get("subject_line", f"Intent Summary for {lead.company_name}"),
                "email_body": parsed.get("email_body", raw),
                "model_used": "Groq Llama 3.3 70B (Pitcher AI)"
            }
    except Exception as e:
        print(f"[Groq Pitcher AI Error] {e}")
    return None


def _generate_summary_with_grok(lead: LeadDetailResponse, api_key: str) -> dict | None:
    """
    Uses xAI's Grok API to generate the intent summary.
    """
    import json
    import httpx
    import re

    try:
        signals_text = "\n".join([f"- {s.signal_type}: {s.verbatim_quote}" for s in lead.signals]) if lead.signals else "No specific signals extracted."
        
        prompt = f"""Generate a point-wise summary of intent signals for {lead.company_name}.

Main AI Verdict: {lead.ai_verdict}

Extracted Intent Signals:
{signals_text}

CRITICAL INSTRUCTIONS:
1. Do NOT write an email. Do NOT include greetings (e.g., 'Hi [Name]') or sign-offs (e.g., 'Best').
2. Create a perfect point-wise brief of all the intent layers fetched from the AI verdict and the extracted signals.
3. The output MUST be a bulleted summary report designed to be shown to a non-tech user.
4. Keep it clear, concise, and highly informative.

Return JSON: {{"subject_line": "Intent Summary for {lead.company_name}", "email_body": string (the summary formatted in markdown bullet points)}}"""

        response = httpx.post(
            "https://api.x.ai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            },
            json={
                "model": "grok-beta",
                "messages": [
                    {"role": "system", "content": "You are an expert analyst. Always output valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                "response_format": {"type": "json_object"}
            },
            timeout=30.0
        )
        response.raise_for_status()
        raw = response.json()["choices"][0]["message"]["content"]
        
        # Safe Extraction
        match = re.search(r'\{.*\}', raw, re.DOTALL)
        if match:
            parsed = json.loads(match.group(0))
            return {
                "subject_line": parsed.get("subject_line", f"Intent Summary for {lead.company_name}"),
                "email_body": parsed.get("email_body", raw),
            }
        return {"subject_line": f"Intent Summary for {lead.company_name}", "email_body": raw}
    except Exception as e:
        logger.warning(f"Grok summarizer failed for {lead.company_name}: {e}, falling back to Gemini")
        return None


def _generate_pitch_with_gemini(lead: LeadDetailResponse) -> dict:
    """Gemini fallback pitcher — used when Claude API key is not set or fails."""
    from google import genai
    from google.genai import types
    from backend.config import settings

    client = genai.Client(api_key=settings.GEMINI_API_KEY)
    signals_text = "\n".join(
        [f"- {s.signal_type}: {s.verbatim_quote}" for s in lead.signals]
    )
    prompt = (
        f"Generate a point-wise summary of intent signals for {lead.company_name}.\n\n"
        f"AI Verdict: {lead.ai_verdict}\n\n"
        f"Extracted Signals:\n{signals_text}\n\n"
        f"CRITICAL INSTRUCTIONS:\n"
        f"1. Do NOT write an email. Do NOT include greetings or sign-offs.\n"
        f"2. Create a perfect point-wise brief of all intent layers.\n"
        f"3. Output MUST be markdown bullet points without any conversational filler."
    )

    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.3,
                system_instruction="You are an expert SDR analyst. Generate objective summary reports.",
            ),
        )
        email_body = response.text
    except Exception:
        email_body = (
            f"### Intent Summary for {lead.company_name}\n\n"
            f"- **Verdict:** {lead.ai_verdict}\n"
            f"- **Signals:** {len(lead.signals)} intent signals processed."
        )

    return {
        "subject_line": f"Intent Summary for {lead.company_name}",
        "email_body": email_body,
    }


class IngestRequest(BaseModel):
    company_name: str


@router.post("/ingest", response_model=LeadDetailResponse)
async def ingest_new_lead(req: IngestRequest):
    """
    Manually injects a company name into the pipeline by delegating to the 
    Orchestrator to standardize the LLM engines (Gemini) and full persistence.
    """
    from backend.pipeline.orchestrator import run_pipeline_for_company
    
    res = await run_pipeline_for_company(req.company_name)
    if res.get("status") == "success":
        return res["lead"]
    elif res.get("status") == "skipped":
        raise HTTPException(status_code=400, detail="Lead was recently cached.")
    
    raise HTTPException(status_code=500, detail="Failed to ingest lead.")

