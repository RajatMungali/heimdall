import os
import json
import asyncio
from typing import Dict, Any, Optional
from aiokafka import AIOKafkaProducer, AIOKafkaConsumer
from backend.utils.logger import logger
from backend.database import SessionLocal
from backend.models import LeadSnapshot

KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "")
KAFKA_SECURITY_PROTOCOL = os.getenv("KAFKA_SECURITY_PROTOCOL", "PLAINTEXT")
KAFKA_SASL_MECHANISM = os.getenv("KAFKA_SASL_MECHANISM", "PLAIN")
KAFKA_SASL_USER = os.getenv("KAFKA_SASL_USER", "")
KAFKA_SASL_PASSWORD = os.getenv("KAFKA_SASL_PASSWORD", "")

TOPIC_ENRICHMENT_REQUESTED = "enrichment.requested"
TOPIC_ENRICHMENT_COMPLETED = "enrichment.completed"
TOPIC_LEAD_CONTACTS_UPDATED = "lead.contacts.updated"

_producer: Optional[AIOKafkaProducer] = None

import ssl

def get_kafka_auth_kwargs() -> Dict[str, Any]:
    """Helper to construct SASL/SSL kwargs for aiokafka if connecting to Aiven / Cloud Kafka."""
    kwargs = {}
    sec_protocol = KAFKA_SECURITY_PROTOCOL.upper()
    if sec_protocol in ["SASL_SSL", "SASL_PLAINTEXT", "SSL"]:
        kwargs["security_protocol"] = sec_protocol
        if sec_protocol.startswith("SASL"):
            kwargs["sasl_mechanism"] = KAFKA_SASL_MECHANISM.upper()
            kwargs["sasl_plain_username"] = KAFKA_SASL_USER
            kwargs["sasl_plain_password"] = KAFKA_SASL_PASSWORD
        if "SSL" in sec_protocol:
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE
            kwargs["ssl_context"] = ssl_context
    return kwargs

async def get_kafka_producer() -> AIOKafkaProducer:
    global _producer
    if not KAFKA_BOOTSTRAP_SERVERS:
        return None
    if _producer is None:
        try:
            auth_kwargs = get_kafka_auth_kwargs()
            _producer = AIOKafkaProducer(
                bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
                value_serializer=lambda v: json.dumps(v).encode("utf-8"),
                **auth_kwargs
            )
            await _producer.start()
            logger.info(f"✅ Kafka Producer connected to {KAFKA_BOOTSTRAP_SERVERS}")
        except Exception as e:
            logger.warning(f"⚠️ Kafka Producer connection warning: {e}")
            _producer = None
    return _producer


async def produce_kafka_event(topic: str, message: Dict[str, Any]):
    """Publishes a structured event message to a Kafka topic."""
    try:
        producer = await get_kafka_producer()
        if producer:
            await producer.send_and_wait(topic, message)
            logger.info(f"📤 [Kafka] Published event to '{topic}'")
        else:
            logger.warning(f"⚠️ Kafka Producer not connected. Skipping message to '{topic}'")
    except Exception as e:
        logger.warning(f"⚠️ Failed to publish Kafka event to '{topic}': {e}")


async def consume_enrichment_events():
    """Background Kafka consumer listening to enrichment.completed with auto-retry for missing topics."""
    from backend.routers.fullenrich import broadcast_enrichment_event

    if not KAFKA_BOOTSTRAP_SERVERS:
        logger.info("ℹ️ KAFKA_BOOTSTRAP_SERVERS not configured — Kafka consumer disabled. Enrichment events will be handled via webhooks only.")
        return

    auth_kwargs = get_kafka_auth_kwargs()
    consumer = None

    while True:
        try:
            consumer = AIOKafkaConsumer(
                TOPIC_ENRICHMENT_COMPLETED,
                bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
                value_deserializer=lambda v: json.loads(v.decode("utf-8")),
                group_id="heimdall-enrichment-consumer",
                auto_offset_reset="latest",
                **auth_kwargs
            )
            await consumer.start()
            logger.info(f"🎧 [Kafka Consumer] Connected and listening to topic '{TOPIC_ENRICHMENT_COMPLETED}'...")

            async for msg in consumer:
                payload = msg.value
                enrichment_id = payload.get("id") or payload.get("enrichment_id")
                logger.info(f"📥 [Kafka] Received enrichment.completed for: {enrichment_id}")

                data_list = payload.get("data", [])
                for item in data_list:
                    contact_info = item.get("contact_info", {})
                    profile = item.get("profile", {})
                    custom_data = item.get("custom", {})
                    job_id = custom_data.get("job_id")

                    work_email = contact_info.get("most_probable_work_email", {}).get("email")
                    phone = contact_info.get("most_probable_phone", {}).get("number")
                    full_name = profile.get("full_name") or f"{item.get('input', {}).get('first_name', '')} {item.get('input', {}).get('last_name', '')}".strip()

                    contact_data = {
                        "name": full_name or "Verified Talent Lead",
                        "email": work_email or "",
                        "phone": phone or "",
                        "status": "DELIVERABLE" if work_email else "NOT_FOUND"
                    }

                    logger.info(f"👤 Contact resolved: {full_name} | Email: {work_email} | Phone: {phone}")

                    # Push directly over SSE Stream
                    if job_id:
                        broadcast_enrichment_event(job_id, {
                            "status": "FINISHED",
                            "job_id": job_id,
                            "contact": contact_data
                        })
                        logger.info(f"⚡ [SSE Notified] Pushed {full_name} to frontend for job: {job_id}")

                    # Publish lead contacts updated event
                    await produce_kafka_event(TOPIC_LEAD_CONTACTS_UPDATED, {
                        "job_id": job_id,
                        "contact": contact_data
                    })
            break
        except Exception as e:
            if consumer:
                try:
                    await consumer.stop()
                except Exception:
                    pass
            logger.warning(f"⚠️ Kafka consumer waiting for topic '{TOPIC_ENRICHMENT_COMPLETED}' ({e}). Retrying in 10s...")
            await asyncio.sleep(10)