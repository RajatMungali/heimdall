import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from backend.database import SessionLocal
from backend.models import LeadSnapshot

def check_specific_lead():
    db = SessionLocal()
    target_id = "477aaba2-ef30-40ab-b37b-d86c50e0b3e0"
    try:
        lead = db.query(LeadSnapshot).filter(LeadSnapshot.id == target_id).first()
        if lead:
            print(f"✅ Lead ID {target_id} EXISTS in DB.")
            print(f"   Company: {lead.company_name} ({lead.domain})")
            print(f"   has full_payload: {bool(lead.full_payload)}")
        else:
            print(f"❌ Lead ID {target_id} DOES NOT EXIST in current DB table.")
            all_ids = [l.id for l in db.query(LeadSnapshot).limit(5).all()]
            print(f"   Sample valid IDs currently in DB: {all_ids}")
    finally:
        db.close()

if __name__ == "__main__":
    check_specific_lead()
