from datetime import datetime, timezone
from fastapi import APIRouter, Request, BackgroundTasks
from sqlalchemy.orm.attributes import flag_modified
from backend.utils.logger import logger
from backend.kafka_service import produce_kafka_event, TOPIC_ENRICHMENT_COMPLETED
from backend.database import SessionLocal
from backend.models import LeadSnapshot, ATSJobSnapshot
from backend.routers.fullenrich import (
    broadcast_enrichment_event,
    add_job_contacts,
    get_next_candidate_for_job,
    clear_job_candidates,
    trigger_reserve_candidate_enrichment,
    is_enrichment_processed,
    mark_enrichment_processed,
    get_job_state,
)

router = APIRouter(prefix="/api/webhooks", tags=["Webhooks & Event Stream"])


def process_webhook_and_save(payload: dict):
    """
    Parses FullEnrich webhook payload, applies email quality filtering,
    checks if target (3 acceptable emails with >= 1 DELIVERABLE) is met,
    falls through to reserve candidates if needed, and broadcasts verified contacts over SSE.
    """
    enrichment_id = payload.get("id") or payload.get("enrichment_id") or ""
    data_list = payload.get("data") or []
    if not data_list:
        return

    # Extract job_id early for deduplication check
    job_id = None
    for item in data_list:
        c_data = item.get("custom") or {}
        if c_data.get("job_id"):
            job_id = c_data["job_id"]
            break

    # Prevent concurrent duplicate processing between Webhook callback and Background Poller
    if job_id and enrichment_id:
        if is_enrichment_processed(job_id, enrichment_id):
            logger.info(f"⚡ [Webhook] Enrichment {enrichment_id} already processed for job {job_id}, skipping duplicate.")
            return
        mark_enrichment_processed(job_id, enrichment_id)

    db = SessionLocal()
    try:
        batch_contacts = []
        company_domain = None
        company_name = None

        for item in data_list:
            custom_data = item.get("custom") or {}
            input_data = item.get("input") or {}

            if not job_id:
                job_id = custom_data.get("job_id")

            if not company_domain:
                company_domain = (
                    input_data.get("company_domain")
                    or input_data.get("domain")
                    or item.get("domain")
                )

            if not company_name:
                company_name = input_data.get("company_name")

            contact_info = item.get("contact_info") or {}
            profile = item.get("profile") or {}

            most_prob_email = contact_info.get("most_probable_work_email") or {}
            work_email = most_prob_email.get("email")
            email_status = (most_prob_email.get("status") or "DELIVERABLE").upper()

            # Spec:
            # - DELIVERABLE — acceptable (best, ~2% bounce rate)
            # - HIGH_PROBABILITY — acceptable (~9% bounce rate)
            # - CATCH_ALL — not acceptable, doesn't count
            # - INVALID — not acceptable, doesn't count
            if not work_email or email_status in ("CATCH_ALL", "INVALID"):
                logger.info(f"⚠️ [Quality Filter] Discarded '{work_email or 'none'}' with status {email_status}")
                continue

            phone_info = contact_info.get("most_probable_phone") or {}
            phone = phone_info.get("number") or ""

            social_profiles = profile.get("social_profiles") or {}
            prof_network = social_profiles.get("professional_network") or {}
            linkedin_url = prof_network.get("url") or ""

            first_name = input_data.get("first_name", "")
            last_name = input_data.get("last_name", "")
            full_name = profile.get("full_name") or f"{first_name} {last_name}".strip()

            employment = profile.get("employment") or {}
            current_emp = employment.get("current") or {}
            headline = profile.get("headline") or current_emp.get("title") or "Decision Maker"

            clean_contact = {
                "name": full_name or "Verified Contact",
                "title": headline,
                "email": work_email,
                "phone": phone,
                "status": email_status,
                "linkedin_url": linkedin_url
            }
            batch_contacts.append(clean_contact)

        
        # Fallback for domain/name from job state if not present in webhook item
        if job_id and (not company_domain or not company_name):
            state = get_job_state(job_id)
            if state:
                if not company_domain:
                    company_domain = state.get("company_domain")
                if not company_name:
                    company_name = state.get("company_name")

        # Accumulate contacts in job state if job_id exists
        if job_id:
            accumulated = add_job_contacts(job_id, batch_contacts)
        else:
            accumulated = batch_contacts

        # Quality check:
        # Target: up to 3 acceptable emails, and at least 1 must be DELIVERABLE
        count_acceptable = len(accumulated)
        count_deliverable = sum(1 for c in accumulated if c.get("status") == "DELIVERABLE")
        target_met = (count_acceptable >= 3 and count_deliverable >= 1)

        # If target not met, try pulling the next candidate in reserve
        if not target_met and job_id:
            next_candidate = get_next_candidate_for_job(job_id)
            if next_candidate:
                logger.info(
                    f"⚡ [Quality Gate] Target not met ({count_acceptable} acceptable, {count_deliverable} deliverable). "
                    f"Fetching reserve candidate: {next_candidate.get('first_name')} {next_candidate.get('last_name')}"
                )
                reserve_id = trigger_reserve_candidate_enrichment(job_id, next_candidate)
                if reserve_id:
                    # Successfully queued reserve candidate; wait for next webhook/poller
                    return

        # Target is met OR reserve candidates ran out (ship-as-is fallback)
        # Prioritize DELIVERABLE first, then HIGH_PROBABILITY, capped at top 3 per spec
        final_contacts = sorted(
            accumulated,
            key=lambda c: 0 if c.get("status") == "DELIVERABLE" else 1
        )[:3]

        logger.info(
            f"🎯 [Enrichment Finalized] Shipping {len(final_contacts)} decision maker(s) for job {job_id} "
            f"({sum(1 for c in final_contacts if c.get('status') == 'DELIVERABLE')} deliverable, target_met={target_met})"
        )

        # 1. Update ATSJobSnapshot in Database (Track Jobs persistent record)
        if job_id and final_contacts:
            ats_job = db.query(ATSJobSnapshot).filter(ATSJobSnapshot.id == job_id).first()
            if not ats_job and company_name:
                ats_job = db.query(ATSJobSnapshot).filter(
                    ATSJobSnapshot.company_name.ilike(company_name.strip())
                ).first()
            if ats_job:
                ats_job.verified_contacts = final_contacts
                ats_job.contacts_enriched_at = datetime.now(timezone.utc)
                flag_modified(ats_job, "verified_contacts")
                logger.info(f"💾 [ATS DB Saved] Saved {len(final_contacts)} verified decision makers to ATS Job: {ats_job.company_name} ({job_id})")

        # 2. Update LeadSnapshot in Database (if lead exists in discovery)
        if company_domain and final_contacts:
            lead = db.query(LeadSnapshot).filter(LeadSnapshot.domain == company_domain).first()
            if lead:
                payload_dict = dict(lead.full_payload or {})
                existing_contacts = payload_dict.get("contacts", [])
                existing_emails = {c.get("email") for c in existing_contacts if c.get("email")}
                new_contacts = [c for c in final_contacts if c.get("email") not in existing_emails]
                payload_dict["contacts"] = new_contacts + existing_contacts
                lead.full_payload = payload_dict
                flag_modified(lead, "full_payload")
                logger.info(f"💾 [DB Saved] Saved {len(new_contacts)} verified decision makers to Lead: {lead.company_name}")

        # 3. Push event over SSE Stream
        if job_id:
            broadcast_enrichment_event(job_id, {
                "status": "FINISHED",
                "job_id": job_id,
                "contacts": final_contacts,
                "contact": final_contacts[0] if final_contacts else None,
                "enriched_at": datetime.now(timezone.utc).isoformat()
            })
            clear_job_candidates(job_id)

        db.commit()
    except Exception as e:
        logger.error(f"❌ Error in webhook handler: {e}")
        db.rollback()
    finally:
        db.close()


@router.post("/fullenrich")
@router.post("/fullenrich/contact")
async def fullenrich_webhook_handler(request: Request, background_tasks: BackgroundTasks):
    try:
        payload = await request.json()
    except Exception:
        payload = {}

    enrichment_id = payload.get("id") or payload.get("enrichment_id") or "unknown_id"
    status = payload.get("status", "FINISHED")

    logger.info(f"⚡ [FullEnrich Webhook] Received webhook callback for ID: {enrichment_id} (Status: {status})")

    # 1. Publish to Kafka
    background_tasks.add_task(produce_kafka_event, TOPIC_ENRICHMENT_COMPLETED, payload)

    # 2. Save to DB & broadcast via SSE to React
    background_tasks.add_task(process_webhook_and_save, payload)

    return {
        "status": "acknowledged",
        "enrichment_id": enrichment_id,
        "message": "Enrichment received."
    }
