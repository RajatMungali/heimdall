import sys
import os
import json

# Add project root to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.database import SessionLocal
from backend.models import LeadSnapshot

def backfill():
    db = SessionLocal()
    try:
        leads = db.query(LeadSnapshot).filter(LeadSnapshot.full_payload == None).all()
        for lead in leads:
            payload = {
                "id": lead.id,
                "company_name": lead.company_name or "Unknown",
                "domain": lead.domain,
                "industry": lead.industry or "Technology",
                "employee_count": lead.employee_count,
                "funding_stage": lead.funding_stage,
                "intent_score": lead.intent_score or 0,
                "signal_freshness": lead.signal_freshness or 100,
                "tier": lead.tier or "Low",
                "icp_fit": lead.icp_fit or "Partial",
                "why_now": lead.why_now or "Mock why now data.",
                "badge": lead.badge,
                "ai_verdict": lead.ai_verdict or "No verdict available.",
                "last_updated": lead.last_updated.isoformat() if lead.last_updated else "",
                "confidence": {
                    "label": "Medium",
                    "color": "yellow",
                    "verified": 1,
                    "total": 1
                },
                "dns_audit": {
                    "spf": "PASS",
                    "dkim": "PASS",
                    "dmarc": "PASS",
                    "issues": []
                },
                "signals": []
            }
            lead.full_payload = payload
        db.commit()
        print(f"Backfilled {len(leads)} leads.")
    finally:
        db.close()

if __name__ == "__main__":
    backfill()
