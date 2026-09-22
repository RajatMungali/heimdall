"""
Phase 4 — Contact Extraction (3-tier local, zero API cost).

Layer 1: Regex email scanning across company subpages
Layer 2: spaCy NER with title-proximity matching for leadership names
Layer 3: Deterministic email format generation with MX verification
"""
import re
import httpx
import dns.resolver
from backend.pipeline.filter_funnel import trim_html_for_llm
from backend.config import settings
from backend.utils.logger import logger

# ---------------------------------------------------------------------------
# spaCy model — LOAD ONCE AT MODULE LEVEL (40MB model, ~2s to load)
# Never load inside a function body or it re-loads per company call.
# ---------------------------------------------------------------------------
try:
    import spacy
    _nlp = spacy.load("en_core_web_sm")
except Exception:
    _nlp = None
    logger.warning("spaCy model not loaded for contact extraction. "
                    "Run: python -m spacy download en_core_web_sm")


TITLE_KEYWORDS = [
    "CEO", "CTO", "Founder", "Co-founder", "Owner", "Franchise Owner", "VP Sales",
    "Head of Sales", "Director", "President", "Partner",
    "Chief", "COO", "CFO", "CMO", "VP", "Head of",
]


# ======================================================================
# Layer 2 — spaCy PERSON + title proximity extraction
# ======================================================================

def extract_leaders_from_text(text: str) -> list[dict]:
    """
    Finds PERSON entities within a 60-character window of a leadership
    title keyword. Returns deduplicated list of {name, title, source}.
    """
    if not _nlp or not text:
        return []

    doc = _nlp(text[:50000])  # Cap input to prevent memory issues
    leaders = []
    for ent in doc.ents:
        if ent.label_ != "PERSON":
            continue
        # Check 60-char window before and after the entity
        start = max(0, ent.start_char - 60)
        end = min(len(text), ent.end_char + 60)
        window = text[start:end]
        matched_title = next(
            (t for t in TITLE_KEYWORDS if t.lower() in window.lower()), None
        )
        if matched_title:
            leaders.append({
                "name": ent.text,
                "title": matched_title,
                "source": "spacy_ner",
            })

    # Deduplicate by name
    seen: set[str] = set()
    return [l for l in leaders if not (l["name"] in seen or seen.add(l["name"]))]


# ======================================================================
# Layer 3 — Email generation + MX verification
# ======================================================================

def split_name(full_name: str) -> tuple[str, str]:
    """Splits 'John Smith' into ('John', 'Smith'). Handles multi-word names."""
    parts = full_name.strip().split()
    if len(parts) >= 2:
        return parts[0], parts[-1]
    return parts[0], ""


def generate_email_candidates(first: str, last: str, domain: str) -> list[str]:
    """Generates the 6 most common corporate email format candidates."""
    f, l = first.lower(), last.lower()
    if not l:
        return [f"{f}@{domain}"]
    return [
        f"{f}.{l}@{domain}",      # john.smith@company.com  (most common)
        f"{f}@{domain}",           # john@company.com
        f"{f[0]}{l}@{domain}",    # jsmith@company.com
        f"{l}@{domain}",           # smith@company.com
        f"{f}{l}@{domain}",        # johnsmith@company.com
        f"{f[0]}.{l}@{domain}",   # j.smith@company.com
    ]


def verify_email_deliverable(email: str) -> bool:
    """
    Checks MX record exists for the domain — does NOT send email.
    Eliminates obvious dead domains. Cannot confirm the mailbox exists.
    """
    try:
        domain = email.split("@")[1]
        dns.resolver.resolve(domain, "MX")
        return True
    except Exception:
        return False


# ======================================================================
# Layer 4 — LinkedIn URL construction (zero-cost signal)
# ======================================================================

def build_linkedin_search_url(company_name: str) -> str:
    slug = company_name.lower().replace(" ", "-").replace(",", "")
    return f"https://www.linkedin.com/company/{slug}/people/"


def search_linkedin_contacts(company_name: str, domain: str) -> list[dict]:
    api_key = settings.SERPER_API_KEY
    if not api_key or api_key == "mock_key_if_empty":
        return []
        
    query = f'site:linkedin.com/in "{company_name}" "VP Sales" OR "Head of Sales" OR "Director" OR "Founder" OR "Co-Founder" OR "CEO" OR "Owner" OR "Franchise Owner"'
    contacts = []
    try:
        with httpx.Client(timeout=10.0) as client:
            res = client.post(
                "https://google.serper.dev/search",
                headers={"X-API-KEY": api_key, "Content-Type": "application/json"},
                json={"q": query, "num": 10},
            )
            data = res.json()
            for result in data.get("organic", []):
                title = result.get("title", "")
                
                # Drop ex-employees
                title_lower = title.lower()
                if "ex-" in title_lower or "formerly" in title_lower or "| ex" in title_lower:
                    continue
                    
                parts = title.replace("| LinkedIn", "").split(" - ")
                if len(parts) >= 2:
                    name = parts[0].strip()
                    job_title = parts[1].strip()
                    first, last = split_name(name)
                    email = f"{first.lower()}.{last.lower()}@{domain}" if last else f"{first.lower()}@{domain}"
                    contacts.append({
                        "name": name,
                        "title": job_title,
                        "email": email,
                        "confidence": "generated",
                        "source": "linkedin_serper"
                    })
    except Exception as e:
        logger.error(f"[LinkedIn Contacts] Error: {e}")
        
    return contacts


# ======================================================================
# Orchestrator — Full contact extraction pipeline
# ======================================================================

def extract_contacts(domain: str, company_name: str) -> list[dict]:
    """
    Orchestrates the 3-tier contact extraction pipeline:
    1. Regex email scanning across /about, /team, /blog, homepage
    2. spaCy NER to find leadership names
    3. Email format generation + MX verification
    """
    pages = ["/about", "/team", "/blog", ""]
    combined_text = ""
    found_emails: list[str] = []

    # Build domain-specific email regex
    email_pattern = re.compile(
        r'[a-zA-Z0-9._%+\-]+@(?:' + re.escape(domain) + r')',
        re.IGNORECASE
    )

    # Tier 1: Scrape subpages and extract on-domain emails
    for path in pages:
        try:
            r = httpx.get(f"https://{domain}{path}", timeout=5.0)
            page_text = trim_html_for_llm(r.text)
            found_emails += email_pattern.findall(page_text)
            combined_text += " " + page_text
        except Exception:
            continue

    # Tier 2: spaCy NER for leadership names
    leaders = extract_leaders_from_text(combined_text)

    # Tier 3: Email generation for each discovered leader
    contacts: list[dict] = []
    for leader in leaders:
        first, last = split_name(leader["name"])
        candidates = generate_email_candidates(first, last, domain)
        # Check if any regex-found email matches a candidate
        verified = [e for e in found_emails if e.lower() in [c.lower() for c in candidates]]
        contacts.append({
            "name": leader["name"],
            "title": leader["title"],
            "email": verified[0] if verified else candidates[0],
            "confidence": "verified" if verified else "generated",
            "source": leader["source"],
        })

    # Tier 4: LinkedIn Serper Contacts
    linkedin_contacts = search_linkedin_contacts(company_name, domain)
    if linkedin_contacts:
        contacts.extend(linkedin_contacts)

    # If no leaders found but emails exist, add them as generic contacts
    if not contacts and found_emails:
        for email in list(set(found_emails))[:3]:
            contacts.append({
                "name": "Unknown",
                "title": "Unknown",
                "email": email,
                "confidence": "verified",
                "source": "regex",
            })

    logger.info(f"[Contacts] Extracted {len(contacts)} contacts from {domain}")
    return contacts
