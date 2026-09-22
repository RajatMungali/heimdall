from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional
import os
import json
import httpx
from dotenv import dotenv_values, load_dotenv

from backend.config_manager import load_intent_config, save_intent_config
from backend.config import settings
from backend.utils.logger import logger

router = APIRouter(prefix="/api/settings", tags=["Settings"])

class IntentConfigModel(BaseModel):
    active_niche: Optional[str] = "recruitment"
    news_queries: Optional[List[str]] = []
    serper_queries: Optional[List[str]] = []
    jobspy_search_term: Optional[str] = "Fractional CMO, Growth Marketing Manager"
    news_signals_query_template: Optional[str] = ""
    exa_query: Optional[str] = "companies looking for a marketing agency, fractional CMO, PPC agency, or lead generation services, expanding operations or hiring growth leaders in the United States"
    extraction_keywords: Optional[List[str]] = []
    social_triggers: Optional[List[str]] = []
    social_topics: Optional[List[str]] = []
    icp_service_categories: Optional[List[str]] = ["Fractional CMO", "Marketing Agency", "Growth Marketing Agency"]
    icp_description: Optional[str] = "Companies seeking external marketing leadership, fractional CMOs, or agency partners"
    icp_seller_keywords: Optional[List[str]] = ["book a call", "our agency", "we offer", "taking on clients", "DM us", "case study"]
    min_employees: Optional[int] = 10
    max_employees: Optional[int] = 2000
    target_industries: Optional[List[str]] = []
    decision_maker_titles: Optional[List[str]] = []  # Per-client ordered priority list set at onboarding

class AIICPRequest(BaseModel):
    prompt: str

class AIICPResponse(BaseModel):
    min_employees: int
    max_employees: int
    target_industries: List[str]
    jobspy_search_term: str
    exa_query: str
    extraction_keywords: List[str]
    social_triggers: List[str]
    social_topics: List[str]
    icp_service_categories: Optional[List[str]] = ["Fractional CMO", "Marketing Agency"]
    icp_description: Optional[str] = "Companies seeking external marketing leadership or agency partners"
    icp_seller_keywords: Optional[List[str]] = ["book a call", "our agency", "we offer"]
    news_queries: List[str]
    serper_queries: List[str]
    summary_explanation: str

@router.get("/intents", response_model=IntentConfigModel)
def get_intents():
    config = load_intent_config()
    return config

@router.post("/intents", response_model=IntentConfigModel)
def update_intents(payload: IntentConfigModel):
    save_intent_config(payload.model_dump())
    return payload

@router.post("/ai-icp-assistant", response_model=AIICPResponse)
async def generate_ai_icp(payload: AIICPRequest):
    """
    Evaluates natural language ICP instructions and outputs structured settings fields.
    """
    user_prompt = payload.prompt.strip()
    if not user_prompt:
        raise HTTPException(status_code=400, detail="Prompt cannot be empty")

    load_dotenv("backend/.env")
    env_vars = dotenv_values("backend/.env")
    openrouter_key = env_vars.get("OPENROUTER_API_KEY") or os.getenv("OPENROUTER_API_KEY") or getattr(settings, "OPENROUTER_API_KEY", "")
    claude_key = env_vars.get("CLAUDE_API_KEY") or os.getenv("CLAUDE_API_KEY") or getattr(settings, "CLAUDE_API_KEY", "")

    system_instruction = """
You are an expert B2B Sales Intelligence System Architect and ICP Specialist.
Analyze the user's natural language Ideal Customer Profile (ICP) description and generate exact settings parameters for our pipeline.

Return ONLY a raw valid JSON object (no markdown code blocks, no preambles, no conversational commentary) matching this exact schema:
{
  "min_employees": <integer, e.g. 50>,
  "max_employees": <integer, e.g. 2000>,
  "min_arr": "<string or null, e.g. '$5M'>",
  "max_arr": "<string or null, e.g. '$50M'>",
  "target_industries": ["<Industry 1>", "<Industry 2>"],
  "jobspy_search_term": "<Comma separated list of 3-6 job titles e.g. Chief Marketing Officer, VP of Marketing, Head of Growth>",
  "exa_query": "<A 1-sentence Exa AI neural search prompt describing the PROSPECT'S own business situation, operational gap, or growth trigger — NEVER the service category the client sells. Describe what the prospect looks like: their industry, growth stage, and situation (e.g. 'multi-location franchise or home services businesses in the US that recently opened an additional location or scaled revenue to $5M-$20M without a listed in-house marketing director')>",
  "extraction_keywords": ["<Keyword 1>", "<Keyword 2>", "<Keyword 3>", "<Keyword 4>", "<Keyword 5>"],
  "social_triggers": ["looking for", "recommend", "need an agency"],
  "social_topics": ["<Specific Target Service 1>", "<Specific Target Service 2>"],
  "news_queries": [
    "<Boolean news query string 1>",
    "<Boolean news query string 2>"
  ],
  "serper_queries": [
    "site:linkedin.com/posts (\"<Query 1>\" OR \"<Query 2>\") -clutch -portfolio",
    "site:linkedin.com/posts (\"<Query 3>\")"
  ],
  "summary_explanation": "<A concise 1-sentence summary of what ICP parameters were configured>"
}

CRITICAL RULES:
1. 'social_triggers' MUST ALWAYS be high-converting buyer action verbs (e.g. ["looking for", "recommend", "need an agency"]).
2. 'social_topics' MUST be specific target service terms (e.g. ["Fractional CMO", "Marketing Agency", "Growth Marketing"]).
3. NEVER add negative operators like - "I run a" or - "we are hiring" into search queries. Keep all search queries natural plain text.
"""

    prompt = f"User ICP Requirement: \"{user_prompt}\"\n\nGenerate the structured JSON settings."

    if openrouter_key:
        url = "https://openrouter.ai/api/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {openrouter_key}",
            "HTTP-Referer": "https://heimdall.app",
            "X-Title": "Heimdall Lead Intel",
            "Content-Type": "application/json"
        }
        # Try active OpenRouter models
        models_to_try = [
            "meta-llama/llama-3.3-70b-instruct",
            "deepseek/deepseek-chat",
            "openai/gpt-4o-mini"
        ]
        
        for m in models_to_try:
            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    resp = await client.post(url, headers=headers, json={
                        "model": m,
                        "messages": [
                            {"role": "system", "content": system_instruction},
                            {"role": "user", "content": prompt}
                        ],
                        "temperature": 0.2
                    })
                    if resp.status_code == 200:
                        content = resp.json()["choices"][0]["message"]["content"]
                        cleaned = content.replace("```json", "").replace("```", "").strip()
                        parsed = json.loads(cleaned)
                        return parsed
            except Exception as e:
                logger.warning(f"OpenRouter model {m} failed: {e}")
                continue

    # Fallback to rule-based parser if API keys missing/failed
    return {
        "min_employees": 50,
        "max_employees": 2000,
        "target_industries": ["Technology", "Recruitment", "Staffing"],
        "jobspy_search_term": "Chief Marketing Officer, VP of Marketing, Head of Growth",
        "exa_query": "companies looking for a marketing agency, fractional CMO, PPC agency, or lead generation services, expanding operations or hiring growth leaders in the United States",
        "extraction_keywords": ["fractional CMO", "PPC agency", "lead generation", "marketing agency", "growth partner"],
        "social_triggers": ["hiring", "looking for", "need a", "recommend"],
        "social_topics": ["marketing agency", "fractional CMO"],
        "news_queries": [
            "(\"expanding marketing team\" OR \"hiring CMO\" OR \"scaling growth\") AND (\"USA\")",
            "(\"raised funding\" OR \"Series A\" OR \"Seed\") AND (\"marketing agency\")"
        ],
        "serper_queries": [
            "site:linkedin.com/posts (\"looking for a marketing agency\" OR \"recommend a PPC agency\") -clutch",
            "site:linkedin.com/posts (\"hiring CMO\" OR \"need marketing agency\")"
        ],
        "summary_explanation": "Configured ICP targeting US Tech & B2B companies looking for marketing agencies, fractional CMOs, and lead generation."
    }

