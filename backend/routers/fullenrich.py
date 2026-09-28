import os
import re
import time
import json
import asyncio
import httpx
import threading
from typing import Optional, Dict, List
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, HTTPException, Request, BackgroundTasks
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from backend.config import settings
from backend.utils.logger import logger
from backend.kafka_service import produce_kafka_event, TOPIC_ENRICHMENT_REQUESTED, TOPIC_ENRICHMENT_COMPLETED

router = APIRouter(prefix="/api/fullenrich", tags=["FullEnrich Contact Intelligence"])

# In-memory real-time SSE event queues keyed by job_id
sse_connections: Dict[str, asyncio.Queue] = {}

# Thread-safe lock and in-memory store for tracking active job enrichment state
_job_state_lock = threading.RLock()
_job_state: Dict[str, dict] = {}


def broadcast_enrichment_event(job_id: str, payload: dict):
    """Pushes enrichment data with verification status to the active SSE client in real-time."""
    if job_id and job_id in sse_connections:
        logger.info(f"⚡ [SSE Broadcast] Pushing verified contacts to client for Job: {job_id}")
        sse_connections[job_id].put_nowait(payload)


def cleanup_stale_job_states(max_age_seconds: int = 900):
    """Evicts job states older than max_age_seconds (15 mins) to prevent memory growth in long-running processes."""
    with _job_state_lock:
        now = time.time()
        stale_keys = [k for k, v in _job_state.items() if now - v.get("created_at", now) > max_age_seconds]
        for k in stale_keys:
            _job_state.pop(k, None)


def store_ranked_candidates_for_job(
    job_id: str,
    candidates: List[dict],
    initial_batch_size: int = 3,
    company_name: str = "",
    company_domain: str = "",
    webhook_target: str = "",
    headers: dict = None
):
    """Stores the full ranked candidate list and context so webhook handler can fall through if needed."""
    if not job_id:
        return
    with _job_state_lock:
        cleanup_stale_job_states()
        _job_state[job_id] = {
            "candidates": candidates,
            "cursor": initial_batch_size,
            "company_name": company_name,
            "company_domain": company_domain,
            "webhook_target": webhook_target,
            "headers": headers or {},
            "accumulated_contacts": [],
            "processed_enrichment_ids": set(),
            "created_at": time.time(),
        }


def get_job_state(job_id: str) -> Optional[dict]:
    with _job_state_lock:
        return _job_state.get(job_id)


def is_enrichment_processed(job_id: str, enrichment_id: str) -> bool:
    """Checks if an enrichment_id was already processed for this job to prevent webhook/poller duplicate processing."""
    if not job_id or not enrichment_id:
        return False
    with _job_state_lock:
        state = _job_state.get(job_id)
        if not state:
            return False
        return enrichment_id in state.get("processed_enrichment_ids", set())


def mark_enrichment_processed(job_id: str, enrichment_id: str):
    """Marks an enrichment_id as processed for this job."""
    if not job_id or not enrichment_id:
        return
    with _job_state_lock:
        state = _job_state.get(job_id)
        if state:
            state.setdefault("processed_enrichment_ids", set()).add(enrichment_id)


def add_job_contacts(job_id: str, new_contacts: List[dict]) -> List[dict]:
    """Accumulates verified contacts for a job_id without duplicate emails/names."""
    with _job_state_lock:
        state = _job_state.get(job_id)
        if not state:
            return new_contacts
        existing: List[dict] = state["accumulated_contacts"]
        seen_emails = {c.get("email") for c in existing if c.get("email")}
        seen_names = {c.get("name", "").lower() for c in existing if c.get("name")}
        for c in new_contacts:
            email = c.get("email")
            name = c.get("name", "").lower()
            if (email and email not in seen_emails) or (not email and name not in seen_names):
                if email:
                    seen_emails.add(email)
                if name:
                    seen_names.add(name)
                existing.append(c)
        return existing


def get_next_candidate_for_job(job_id: str) -> Optional[dict]:
    """Returns the next unused candidate from the ranked list, or None if exhausted."""
    with _job_state_lock:
        state = _job_state.get(job_id)
        if not state:
            return None
        candidates = state.get("candidates", [])
        cursor = state.get("cursor", 3)
        if cursor < len(candidates):
            state["cursor"] = cursor + 1
            return candidates[cursor]
        return None


def clear_job_candidates(job_id: str):
    """Cleans up stored candidates after enrichment is complete."""
    with _job_state_lock:
        _job_state.pop(job_id, None)


def trigger_reserve_candidate_enrichment(job_id: str, candidate: dict) -> Optional[str]:
    """
    Submits 1 reserve candidate to FullEnrich Bulk Enrich when quality target is not met.
    Starts a background poller thread as backup.
    Returns enrichment_id if successful, None otherwise.
    """
    with _job_state_lock:
        state = _job_state.get(job_id)
        if not state:
            return None

        headers = state.get("headers", {})
        webhook_target = state.get("webhook_target", "")
        domain = state.get("company_domain", "")
        company_name = state.get("company_name", "")

    person_data = {
        "first_name": candidate.get("first_name", ""),
        "last_name": candidate.get("last_name", ""),
        "domain": domain,
        "company_name": company_name,
        "enrich_fields": ["contact.work_emails"],
        "custom": {"job_id": job_id}
    }
    if candidate.get("linkedin_url"):
        person_data["linkedin_url"] = candidate["linkedin_url"]

    payload = {
        "name": f"Heimdall - {company_name} (Reserve)",
        "webhook_url": webhook_target,
        "webhook_events": {"contact_finished": webhook_target},
        "data": [person_data]
    }

    try:
        with httpx.Client(timeout=30.0) as client:
            res = client.post(
                "https://app.fullenrich.com/api/v2/contact/enrich/bulk",
                headers=headers,
                json=payload
            )
            if res.status_code in [200, 201]:
                resp_data = res.json()
                enrichment_id = resp_data.get("enrichment_id") or resp_data.get("id")
                logger.info(
                    f"⚡ [Reserve Enrichment] Queued candidate {candidate.get('first_name')} "
                    f"{candidate.get('last_name')} (ID: {enrichment_id})"
                )

                def run_poller():
                    asyncio.run(background_poll_fullenrich_result(enrichment_id, job_id, domain, headers))
                threading.Thread(target=run_poller, daemon=True).start()
                return enrichment_id
            else:
                logger.error(f"❌ [Reserve Enrichment] Error ({res.status_code}): {res.text}")
    except Exception as e:
        logger.error(f"❌ [Reserve Enrichment] Exception: {e}")
    return None


class ContactEnrichRequest(BaseModel):
    job_id: Optional[str] = None
    company_name: str
    company_domain: Optional[str] = None
    first_name: Optional[str] = "Hiring"
    last_name: Optional[str] = "Manager"
    linkedin_url: Optional[str] = None
    webhook_url: Optional[str] = None
    force_refresh: Optional[bool] = False


async def search_people_by_client_titles(
    client: httpx.AsyncClient,
    headers: dict,
    company_name: str,
    company_domain: str,
    title_list: List[str],
) -> List[dict]:
    """
    ONE FullEnrich People Search with the client's full title list as OR filters.
    Capped at limit=15 to control API credit spend (FullEnrich bills per result).
    Returns raw list of person dicts from FullEnrich.
    """
    if not title_list:
        logger.warning("[FullEnrich Search] No title list configured — using generic fallback titles")
        title_list = ["Head of Talent", "CEO", "Founder", "HR Director"]

    search_payload = {
        "limit": 15,
        "current_company_domains": [
            {"value": company_domain, "exact_match": True, "exclude": False}
        ] if company_domain else [],
        "current_company_names": [
            {"value": company_name, "exact_match": False, "exclude": False}
        ],
        "current_position_titles": [
            {"value": t, "exact_match": False, "exclude": False}
            for t in title_list
        ]
    }

    try:
        logger.info(
            f"🔍 [FullEnrich Search] Querying {len(title_list)} configured titles at "
            f"{company_name} ({company_domain}), limit=15..."
        )
        res = await client.post(
            "https://app.fullenrich.com/api/v2/people/search",
            headers=headers,
            json=search_payload,
            timeout=15.0
        )
        if res.status_code == 200:
            people = res.json().get("people", [])
            logger.info(f"✅ [FullEnrich Search] Returned {len(people)} raw candidates for {company_name}")
            return people
        else:
            logger.warning(f"[FullEnrich Search] Status {res.status_code}: {res.text[:200]}")
    except Exception as e:
        logger.warning(f"[FullEnrich Search] Failed: {e}")

    return []


async def rank_candidates_with_llm(
    raw_people: List[dict],
    priority_title_list: List[str],
    company_name: str,
) -> List[dict]:
    """
    Uses Gemini structured output to:
    1. Rank raw_people against priority_title_list using semantic (not string) matching.
    2. Drop anyone whose title doesn't reasonably map to any entry in the list.
    3. Deduplicate by person (same human matching two titles appears only once).
    4. Return ALL valid candidates in ranked order so the webhook handler can fall through
       to 4th/5th if the quality target (>=1 DELIVERABLE) is not met.

    Falls back to raw_people[:3] if Gemini fails.
    """
    if not raw_people:
        return []

    people_summary = []
    for i, p in enumerate(raw_people):
        people_summary.append({
            "index": i,
            "name": f"{p.get('first_name', '')} {p.get('last_name', '')}".strip(),
            "headline": p.get("headline", ""),
        })

    system_prompt = (
        "You are a B2B contact ranker for a sales intelligence platform.\n\n"
        "Given a list of people from a professional database and a client's ordered priority title list,\n"
        "your job is to:\n"
        "1. Match each person's job title/headline SEMANTICALLY against the priority list (not string match).\n"
        "   Examples: 'Head of Talent' -> 'Head of Talent Acquisition', 'CEO' <-> 'Chief Executive Officer'.\n"
        "2. Assign each person a rank_position = the 1-based index of the best matching entry in the priority list.\n"
        "3. DROP anyone whose title has no reasonable semantic match to any entry in the priority list.\n"
        "4. DEDUPLICATE: if the same person appears twice, keep only their highest-priority match.\n"
        "5. Return ALL valid, deduplicated candidates in ascending rank_position order.\n\n"
        "Important: Rank ONLY against the client's list. Do not use your own judgment about\n"
        "which titles are appropriate — the client already decided that."
    )

    user_prompt = (
        f"Company: {company_name}\n\n"
        f"Client's priority title list (1 = most wanted):\n"
        + "\n".join(f"{i+1}. {t}" for i, t in enumerate(priority_title_list))
        + f"\n\nPeople returned from search:\n{json.dumps(people_summary, indent=2)}\n\n"
        "Return a JSON array of valid candidates in ranked order. Each item:\n"
        '{"index": <original index>, "name": "<full name>", '
        '"rank_position": <1-based position in priority list>, '
        '"matched_title": "<title from the priority list they best match>"}\n\n'
        "Only include people whose titles meaningfully match the client's list. "
        "Order ascending by rank_position (lowest = highest priority)."
    )

    try:
        from google import genai
        from google.genai import types as genai_types

        gemini_key = os.getenv("GEMINI_API_KEY") or getattr(settings, "GEMINI_API_KEY", "")
        if not gemini_key:
            raise ValueError("GEMINI_API_KEY not configured")

        gemini_client = genai.Client(api_key=gemini_key)
        response = gemini_client.models.generate_content(
            model="gemini-2.0-flash",
            contents=user_prompt,
            config=genai_types.GenerateContentConfig(
                system_instruction=system_prompt,
                response_mime_type="application/json",
                temperature=0.1,
            )
        )

        raw_text = (response.text or "").strip()
        # Clean markdown code block if present
        raw_text = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw_text, flags=re.MULTILINE).strip()
        parsed = json.loads(raw_text)

        # Handle parsed response whether list or dict
        if isinstance(parsed, dict):
            ranked_indices = parsed.get("candidates") or parsed.get("people") or list(parsed.values())
        elif isinstance(parsed, list):
            ranked_indices = parsed
        else:
            ranked_indices = []

        logger.info(
            f"🧠 [LLM Ranking] Ranked {len(ranked_indices)} valid candidates "
            f"from {len(raw_people)} raw results for {company_name}"
        )

        result = []
        seen_names = set()
        for item in ranked_indices:
            if not isinstance(item, dict):
                continue
            idx = item.get("index")
            if idx is None or not isinstance(idx, int) or idx >= len(raw_people):
                continue
            person = raw_people[idx]
            name_key = f"{person.get('first_name', '')}_{person.get('last_name', '')}".lower()
            if name_key in seen_names:
                continue
            seen_names.add(name_key)
            social = person.get("social_profiles") or {}
            result.append({
                "first_name": person.get("first_name", ""),
                "last_name": person.get("last_name", ""),
                "headline": person.get("headline") or item.get("matched_title", ""),
                "linkedin_url": (social.get("professional_network") or {}).get("url"),
                "rank_position": item.get("rank_position", 99),
                "matched_title": item.get("matched_title", ""),
            })
        return result

    except Exception as e:
        logger.warning(f"[LLM Ranking] Gemini ranking failed ({e}) — falling back to raw top-3")
        fallback = []
        seen = set()
        for p in raw_people:
            if len(fallback) >= 3:
                break
            key = f"{p.get('first_name', '')}_{p.get('last_name', '')}".lower()
            if key not in seen and p.get("first_name") and p.get("last_name"):
                seen.add(key)
                social = p.get("social_profiles") or {}
                fallback.append({
                    "first_name": p["first_name"],
                    "last_name": p.get("last_name", ""),
                    "headline": p.get("headline", ""),
                    "linkedin_url": (social.get("professional_network") or {}).get("url"),
                    "rank_position": len(fallback) + 1,
                    "matched_title": "",
                })
        return fallback


async def background_poll_fullenrich_result(enrichment_id: str, job_id: str, company_domain: str, headers: dict):
    """Backup Poller: Polls FullEnrich every 4s to ensure deliverability status is returned."""
    logger.info(f"⏳ [Background Poller] Monitoring Enrichment ID: {enrichment_id} (Job: {job_id})...")
    from backend.routers.webhooks import process_webhook_and_save

    resolved = False
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            for attempt in range(45):  # 12 attempts * 4s = 48s max
                await asyncio.sleep(4)
                res = await client.get(
                    f"https://app.fullenrich.com/api/v2/contact/enrich/bulk/{enrichment_id}",
                    headers=headers
                )
                if res.status_code == 200:
                    payload = res.json()
                    status = payload.get("status")
                    if status == "FINISHED":
                        logger.info(f"🎉 [Poller Finished] Contacts resolved for ID: {enrichment_id}")
                        process_webhook_and_save(payload)
                        await produce_kafka_event(TOPIC_ENRICHMENT_COMPLETED, payload)
                        resolved = True
                        break
                    elif status in ("FAILED", "CREDITS_INSUFFICIENT", "CANCELED"):
                        logger.warning(f"⚠️ [Poller Ended] Enrichment {enrichment_id} finished with status: {status}")
                        broadcast_enrichment_event(job_id, {
                            "status": status,
                            "job_id": job_id,
                            "contacts": [],
                            "contact": None,
                            "error": f"Enrichment terminated: {status}"
                        })
                        clear_job_candidates(job_id)
                        resolved = True
                        break
    except Exception as e:
        logger.error(f"❌ Background Poller error: {e}")

    if not resolved and job_id:
        # Poller timed out after 48s — check if any contacts were accumulated, otherwise finalize
        state = get_job_state(job_id)
        contacts = state.get("accumulated_contacts", []) if state else []
        logger.info(f"⏱️ [Poller Timeout] Finalizing job {job_id} with {len(contacts)} accumulated contact(s)")
        now_utc = datetime.now(timezone.utc)
        if contacts:
            from backend.database import SessionLocal
            from backend.models import ATSJobSnapshot
            from sqlalchemy.orm.attributes import flag_modified
            db_poll = SessionLocal()
            try:
                ats_j = db_poll.query(ATSJobSnapshot).filter(ATSJobSnapshot.id == job_id).first()
                if ats_j:
                    ats_j.verified_contacts = contacts
                    ats_j.contacts_enriched_at = now_utc
                    flag_modified(ats_j, "verified_contacts")
                    db_poll.commit()
            except Exception as e:
                logger.error(f"Error saving timeout contacts to DB: {e}")
                db_poll.rollback()
            finally:
                db_poll.close()

        broadcast_enrichment_event(job_id, {
            "status": "FINISHED",
            "job_id": job_id,
            "contacts": contacts,
            "contact": contacts[0] if contacts else None,
            "enriched_at": now_utc.isoformat()
        })
        clear_job_candidates(job_id)


@router.get("/stream/{job_id}")
async def stream_enrichment_events(job_id: str, request: Request):
    """Server-Sent Events (SSE) stream endpoint."""
    queue = asyncio.Queue()
    sse_connections[job_id] = queue

    async def event_generator():
        try:
            yield f"data: {json.dumps({'status': 'CONNECTED', 'job_id': job_id})}\n\n"
            while True:
                if await request.is_disconnected():
                    break
                try:
                    data = await asyncio.wait_for(queue.get(), timeout=45.0)
                    yield f"data: {json.dumps(data)}\n\n"
                    if data.get("status") in ("FINISHED", "FAILED", "CREDITS_INSUFFICIENT", "CANCELED"):
                        break
                except asyncio.TimeoutError:
                    yield ": keep-alive\n\n"
        finally:
            sse_connections.pop(job_id, None)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.post("/enrich")
async def trigger_fullenrich_contact(req: ContactEnrichRequest, background_tasks: BackgroundTasks):
    """
    New enrichment pipeline:
    1. Load client's configured decision_maker_titles from intent_config.json
    2. ONE FullEnrich People Search with all titles (limit=10)
    3. Gemini LLM ranking pass - fuzzy match, dedupe, rank by client priority
    4. Submit top 3 in a single FullEnrich Bulk Enrich call
    5. Store full ranked list so webhook handler can fall through to 4th/5th if quality not met
    """
    # 🛡️ Step 0: Check Database for existing Fresh Contacts (< 30 days) to prevent credit burn
    if not req.force_refresh and req.job_id:
        from backend.database import SessionLocal
        from backend.models import ATSJobSnapshot
        from datetime import datetime, timezone, timedelta

        db = SessionLocal()
        try:
            ats_job = db.query(ATSJobSnapshot).filter(ATSJobSnapshot.id == req.job_id).first()
            if not ats_job and req.company_name:
                ats_job = db.query(ATSJobSnapshot).filter(
                    ATSJobSnapshot.company_name.ilike(req.company_name.strip())
                ).first()

            if ats_job and ats_job.verified_contacts and len(ats_job.verified_contacts) > 0:
                enriched_at = ats_job.contacts_enriched_at
                is_fresh = True
                if enriched_at:
                    if enriched_at.tzinfo is None:
                        enriched_at = enriched_at.replace(tzinfo=timezone.utc)
                    age = datetime.now(timezone.utc) - enriched_at
                    if age > timedelta(days=30):
                        is_fresh = False

                if is_fresh:
                    logger.info(f"⚡ [Credit Protection] Returning {len(ats_job.verified_contacts)} fresh decision makers from DB for {req.company_name} (0 API credits burned).")
                    broadcast_enrichment_event(req.job_id, {
                        "status": "FINISHED",
                        "job_id": req.job_id,
                        "contacts": ats_job.verified_contacts,
                        "contact": ats_job.verified_contacts[0] if ats_job.verified_contacts else None,
                        "cached": True,
                        "enriched_at": ats_job.contacts_enriched_at.isoformat() if ats_job.contacts_enriched_at else None
                    })
                    return {
                        "status": "cached",
                        "job_id": req.job_id,
                        "contacts": ats_job.verified_contacts,
                        "enriched_at": ats_job.contacts_enriched_at.isoformat() if ats_job.contacts_enriched_at else None,
                        "message": "Fresh decision makers loaded from database."
                    }
        finally:
            db.close()

    api_key = os.getenv("FULLENRICH_API_KEY") or getattr(settings, "FULLENRICH_API_KEY", "")
    if not api_key:
        raise HTTPException(status_code=500, detail="FULLENRICH_API_KEY is missing in backend/.env")

    headers = {
        "Authorization": f"Bearer {api_key.strip()}",
        "Content-Type": "application/json"
    }

    public_base = os.getenv("PUBLIC_WEBHOOK_URL") or getattr(settings, "PUBLIC_WEBHOOK_URL", None)
    webhook_target = req.webhook_url or (
        f"{public_base}/api/webhooks/fullenrich" if public_base else "https://app.fullenrich.com/webhook-sink"
    )

    domain = req.company_domain
    if domain:
        domain = domain.replace("https://", "").replace("http://", "").replace("www.", "").strip("/").split("/")[0]
    elif req.company_name:
        clean_name = req.company_name.lower().replace(" ", "").replace(",", "").replace(".", "")
        domain = f"{clean_name}.com"

    async with httpx.AsyncClient(timeout=30.0) as client:

        # Step 1: Load client's configured title list
        from backend.config_manager import load_intent_config
        config = load_intent_config()
        title_list: List[str] = config.get("decision_maker_titles", [])

        # Step 2: ONE FullEnrich People Search with all configured titles
        raw_people = await search_people_by_client_titles(
            client, headers, req.company_name, domain, title_list
        )

        # Step 2b: LLM ranking - fuzzy match, dedupe, sort by client priority
        ranked_candidates = await rank_candidates_with_llm(
            raw_people, title_list, req.company_name
        )

        if not ranked_candidates:
            logger.warning(f"[Enrich] No candidates found for {req.company_name} - using placeholder")
            ranked_candidates = [{
                "first_name": "Hiring",
                "last_name": "Manager",
                "headline": "",
                "linkedin_url": None,
                "rank_position": 1,
                "matched_title": "",
            }]

        # Step 3: Submit top 3 in one bulk enrich call
        initial_batch = ranked_candidates[:3]
        data_items = []
        for person in initial_batch:
            item = {
                "first_name": person["first_name"],
                "last_name": person["last_name"],
                "domain": domain,
                "company_name": req.company_name,
                "enrich_fields": ["contact.work_emails"],
                "custom": {"job_id": req.job_id or ""}
            }
            if person.get("linkedin_url"):
                item["linkedin_url"] = person["linkedin_url"]
            data_items.append(item)

        payload = {
            "name": f"Heimdall - {req.company_name}",
            "webhook_url": webhook_target,
            "webhook_events": {"contact_finished": webhook_target},
            "data": data_items
        }

        logger.info(
            f"\n{'='*60}\n"
            f"📦 [FullEnrich Bulk Enrich] {len(data_items)} decision maker(s) for {req.company_name}:\n"
            f"{json.dumps(payload, indent=2)}\n"
            f"{'='*60}\n"
        )

        res = await client.post(
            "https://app.fullenrich.com/api/v2/contact/enrich/bulk",
            headers=headers,
            json=payload
        )
        if res.status_code not in [200, 201]:
            logger.error(f"❌ FullEnrich Error ({res.status_code}): {res.text}")
            raise HTTPException(status_code=res.status_code, detail=res.text)

        resp_data = res.json()
        enrichment_id = resp_data.get("enrichment_id") or resp_data.get("id")

        # Store the FULL ranked list and context so webhook handler can fall through when needed
        if req.job_id:
            store_ranked_candidates_for_job(
                job_id=req.job_id,
                candidates=ranked_candidates,
                initial_batch_size=len(initial_batch),
                company_name=req.company_name,
                company_domain=domain,
                webhook_target=webhook_target,
                headers=headers
            )

        await produce_kafka_event(TOPIC_ENRICHMENT_REQUESTED, {
            "enrichment_id": enrichment_id,
            "company_name": req.company_name,
            "domain": domain,
            "candidates": len(data_items),
            "job_id": req.job_id,
            "webhook_url": webhook_target
        })

        background_tasks.add_task(
            background_poll_fullenrich_result,
            enrichment_id,
            req.job_id or "",
            domain,
            headers
        )

        return {
            "status": "queued",
            "enrichment_id": enrichment_id,
            "candidates_submitted": len(data_items),
            "total_ranked": len(ranked_candidates),
            "message": (
                f"Enrichment queued for {len(data_items)} decision maker(s). "
                f"{len(ranked_candidates) - len(data_items)} more candidate(s) in reserve."
            )
        }
