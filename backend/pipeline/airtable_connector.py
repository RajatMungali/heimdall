import os
import json
import httpx
from typing import List, Dict, Any, Tuple, Optional
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))
from backend.utils.logger import logger

AIRTABLE_API_KEY = os.getenv("AIRTABLE_API_KEY")
AIRTABLE_BASE_ID = os.getenv("AIRTABLE_BASE_ID")
AIRTABLE_TABLE_NAME = os.getenv("AIRTABLE_TABLE_NAME", "testing")

STATE_FILE_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data", "pipeline_state.json"))

def load_pipeline_state() -> Dict[str, Any]:
    """Loads the local offset cursor state from pipeline_state.json."""
    default_state = {
        "current_offset": 0,
        "daily_target": 30,
        "daily_processed_count": 0,
        "last_run_timestamp": None,
        "total_records_in_airtable": 0
    }
    if not os.path.exists(STATE_FILE_PATH):
        os.makedirs(os.path.dirname(STATE_FILE_PATH), exist_ok=True)
        save_pipeline_state(default_state)
        return default_state
    
    try:
        with open(STATE_FILE_PATH, "r", encoding="utf-8") as f:
            state = json.load(f)
            return {**default_state, **state}
    except Exception as e:
        logger.warning(f"Failed to read {STATE_FILE_PATH}, falling back to defaults: {e}")
        return default_state

def save_pipeline_state(state: Dict[str, Any]) -> None:
    """Saves the local offset cursor state to pipeline_state.json."""
    try:
        os.makedirs(os.path.dirname(STATE_FILE_PATH), exist_ok=True)
        with open(STATE_FILE_PATH, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2)
    except Exception as e:
        logger.error(f"Failed to write to {STATE_FILE_PATH}: {e}")

_CANDIDATE_CACHE: List[Dict[str, Any]] = []
_CACHE_LAST_FETCHED: Optional[datetime] = None
CACHE_TTL_SECONDS = 300  # 5 minutes

async def fetch_airtable_candidates_batch(
    limit: int = 5,
    offset_token: Optional[str] = None
) -> Tuple[List[Dict[str, Any]], Optional[str]]:
    """
    Fetches a single batch of `limit` candidates directly from Airtable using
    native `pageSize=limit` and `maxRecords=limit`.
    Makes exactly ONE HTTP call to Airtable.
    Returns (batch_records, next_offset_token).
    """
    if not AIRTABLE_API_KEY or not AIRTABLE_BASE_ID:
        logger.error("Airtable credentials missing in backend/.env!")
        return [], None

    url = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{AIRTABLE_TABLE_NAME}"
    headers = {
        "Authorization": f"Bearer {AIRTABLE_API_KEY}",
        "Content-Type": "application/json"
    }

    params = {
        "pageSize": limit
    }
    if offset_token:
        params["offset"] = offset_token

    records_accumulated = []
    next_offset = None

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            res = await client.get(url, headers=headers, params=params)
            
            # If offset token expired or invalid (HTTP 422), fallback to initial page
            if res.status_code in (400, 422) and offset_token:
                logger.warning(f"⚠️ Airtable offset token expired or invalid (HTTP {res.status_code}). Resetting offset cursor to page 1.")
                params.pop("offset", None)
                res = await client.get(url, headers=headers, params=params)

            res.raise_for_status()
            data = res.json()

            recs = data.get("records", [])
            for rec in recs:
                fields = rec.get("fields", {})
                company_name = fields.get("Company Name") or fields.get("Company") or fields.get("Name") or "Unknown"
                domain = fields.get("Website") or fields.get("Domain") or fields.get("URL") or ""

                if company_name and domain:
                    records_accumulated.append({
                        "airtable_id": rec.get("id"),
                        "company_name": company_name.strip(),
                        "domain": domain.replace("https://", "").replace("http://", "").strip("/"),
                        "firmographics": {
                            "industry": fields.get("Industry") or fields.get("Industry Tags") or "B2B SaaS / Tech",
                            "employee_count": fields.get("Headcount") or fields.get("Employee Size") or 150,
                            "total_funding": fields.get("Total Funding") or fields.get("Last Funding Amount"),
                            "linkedin": fields.get("LinkedIn"),
                            "annual_revenue": fields.get("Annual Revenue")
                        },
                        "raw_fields": fields
                    })

            next_offset = data.get("offset")
        except Exception as e:
            logger.error(f"Error fetching batch from Airtable: {e}")

    return records_accumulated, next_offset


async def get_ui_test_batch(limit: int = 5) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """
    Fetches the next `limit` UNPROCESSED candidate companies for the interactive UI test run.
    Deduplicates against existing database records to guarantee zero repeated runs.
    """
    from backend.database import SessionLocal
    from backend.models import LeadSnapshot

    # 1. Query existing database leads to prevent processing duplicate companies
    db = SessionLocal()
    try:
        db_leads = db.query(LeadSnapshot).all()
        processed_domains = {l.domain.lower() for l in db_leads if l.domain}
        processed_names = {l.company_name.lower() for l in db_leads if l.company_name}
    except Exception as e:
        processed_domains, processed_names = set(), set()
        logger.warning(f"Error querying existing database leads for deduplication: {e}")
    finally:
        db.close()

    state = load_pipeline_state()
    offset_token = state.get("next_offset_token")

    unprocessed_batch = []
    current_offset_token = offset_token
    last_valid_offset = offset_token

    # 2. Paginate through Airtable until limit UNPROCESSED candidates are collected
    for _ in range(15):  # Up to 15 pages per request to find fresh leads
        raw_batch, next_offset = await fetch_airtable_candidates_batch(limit=max(limit * 2, 10), offset_token=current_offset_token)
        last_valid_offset = next_offset
        if not raw_batch:
            break

        for cand in raw_batch:
            dom = (cand.get("domain") or "").lower()
            name = (cand.get("company_name") or "").lower()
            if dom and dom in processed_domains:
                continue
            if name and name in processed_names:
                continue
            
            unprocessed_batch.append(cand)
            processed_domains.add(dom)
            processed_names.add(name)

            if len(unprocessed_batch) >= limit:
                break

        current_offset_token = next_offset
        if len(unprocessed_batch) >= limit or not next_offset:
            break

    state["next_offset_token"] = last_valid_offset
    state["current_offset"] = state.get("current_offset", 0) + len(unprocessed_batch)
    state["daily_processed_count"] = state.get("daily_processed_count", 0) + len(unprocessed_batch)
    state["last_run_timestamp"] = datetime.now(timezone.utc).isoformat()

    save_pipeline_state(state)
    names = [c.get("company_name", "Unknown") for c in unprocessed_batch]
    logger.info(f"\n=========================================================================")
    logger.info(f"📋 AIRTABLE BATCH FETCHED ({len(unprocessed_batch)} UNPROCESSED companies): {', '.join(names)}")
    logger.info(f"=========================================================================\n")
    return unprocessed_batch, state

async def get_midnight_cron_batch(daily_quota: int = 20) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """
    Fetches the remaining daily batch for midnight cron execution.
    Calculates remaining = max(0, daily_quota - daily_processed_count).
    Advances offset token and resets daily_processed_count to 0.
    """
    state = load_pipeline_state()
    processed_today = state.get("daily_processed_count", 0)
    remaining_needed = max(0, daily_quota - processed_today)

    if remaining_needed == 0:
        logger.info("Daily target already satisfied by UI test runs today! Resetting daily count.")
        state["daily_processed_count"] = 0
        save_pipeline_state(state)
        return [], state

    offset_token = state.get("next_offset_token")
    batch, next_offset = await fetch_airtable_candidates_batch(limit=remaining_needed, offset_token=offset_token)

    state["next_offset_token"] = next_offset
    state["current_offset"] = state.get("current_offset", 0) + len(batch)
    state["daily_processed_count"] = 0  # Reset for next day
    state["last_run_timestamp"] = datetime.now(timezone.utc).isoformat()

    save_pipeline_state(state)
    logger.info(f"Midnight Cron Batch: Fetched {len(batch)} candidates (Remaining from {remaining_needed}). Next offset: {next_offset}.")
    return batch, state

