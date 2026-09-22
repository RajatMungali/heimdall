import json
import os
from pathlib import Path
from backend.utils.logger import logger

CONFIG_PATH = Path(__file__).parent / "intent_config.json"

DEFAULT_CONFIG = {
    "news_queries": [
        "SaaS startup raises funding",
        "B2B seed round",
        "series A funding startup",
        "startup hiring SDR sales"
    ],
    "serper_queries": [
        "site:linkedin.com/company \"hiring SDR\" OR \"hiring BDR\""
    ],
    "jobspy_search_term": "Sales Development Representative",
    "news_signals_query_template": "\"{company_name}\" AND (startup OR funding OR expansion OR hiring)",
    "exa_query": "companies looking for a marketing agency, fractional CMO, PPC agency, or lead generation services, expanding operations or hiring growth leaders in the United States",
    "extraction_keywords": [
        "raised", "funding", "hired", "expanded", "launched", "SDR",
        "hiring", "growth", "series", "seed", "round"
    ],
    "decision_maker_titles": [
        "Head of Talent Acquisition",
        "Head of Recruiting",
        "Director of Talent Acquisition",
        "Recruiting Manager",
        "Head of People",
        "VP of People",
        "HR Director",
        "Head of HR",
        "Talent Acquisition Manager",
        "Talent Partner",
        "Talent Lead",
        "Founder",
        "Co-founder",
        "CEO",
        "VP of Engineering",
        "Head of Engineering",
        "COO",
        "Chief Executive Officer"
    ]
}

def load_intent_config() -> dict:
    if not os.path.exists(CONFIG_PATH):
        return DEFAULT_CONFIG.copy()
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Failed to load intent config: {e}")
        return DEFAULT_CONFIG.copy()

def save_intent_config(config: dict) -> bool:
    try:
        current = load_intent_config()
        # Merge top-level keys
        for k, v in config.items():
            if v is not None:
                current[k] = v
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(current, f, indent=2)
        return True
    except Exception as e:
        logger.error(f"Failed to save intent config: {e}")
        return False
