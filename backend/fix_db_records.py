import asyncio
import json
from backend.database import SessionLocal
from backend.models import LeadSnapshot

def fix_corrupted_records():
    db = SessionLocal()
    try:
        leads = db.query(LeadSnapshot).all()
        fixed = 0
        for lead in leads:
            # Check ai_verdict
            if lead.ai_verdict:
                try:
                    # It might be stored as a stringified list like '["...", "..."]' 
                    # or it might actually be a JSON type depending on the column.
                    # Since it's a Text column, let's see if it starts with '['
                    if isinstance(lead.ai_verdict, str) and lead.ai_verdict.strip().startswith('['):
                        parsed = json.loads(lead.ai_verdict)
                        if isinstance(parsed, list):
                            lead.ai_verdict = " ".join([str(x) for x in parsed])
                            fixed += 1
                except Exception as e:
                    print(f"Error parsing {lead.company_name}: {e}")
                    
            # Also fix full_payload which might contain the bad ai_verdict
            if lead.full_payload:
                try:
                    payload = lead.full_payload
                    if isinstance(payload, str):
                        payload = json.loads(payload)
                    
                    if isinstance(payload, dict) and isinstance(payload.get("ai_verdict"), list):
                        payload["ai_verdict"] = " ".join([str(x) for x in payload["ai_verdict"]])
                        # In SQLAlchemy, you must re-assign or flag JSON columns as modified
                        lead.full_payload = dict(payload)
                        from sqlalchemy.orm.attributes import flag_modified
                        flag_modified(lead, "full_payload")
                        fixed += 1
                except Exception as e:
                    pass

        if fixed > 0:
            db.commit()
            print(f"Successfully fixed {fixed} corrupted fields in the database!")
        else:
            print("No corrupted records found.")
    finally:
        db.close()

if __name__ == "__main__":
    fix_corrupted_records()
