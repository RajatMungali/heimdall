from bs4 import BeautifulSoup
import html2text

ANCHOR_KEYWORDS = [
    'funding', 'raised', 'series a', 'series b',
    'sdr', 'bdr', 'sales development', 'business development',
    'hiring', 'expand', 'growth', 'outbound', 'pipeline'
]


def trim_html_for_llm(raw_html: str) -> str:
    """
    Strips raw code strings, stylesheets, script markers, and layout menus
    to optimize context structure before calling AI engines. (Stage 2)
    """
    soup = BeautifulSoup(raw_html, 'html.parser')

    # Prune non-content structural tags
    for tag in soup(['script', 'style', 'nav', 'footer', 'header', 'aside']):
        tag.decompose()

    # Convert standard DOM syntax to clean markdown text format
    text = html2text.html2text(str(soup))

    # Enforce strict ceiling limit to cap upstream context sizes
    return text[:8000]


def passes_keyword_gate(text: str) -> bool:
    """
    Executes a microsecond-level plain string match check.
    Drops non-matching leads immediately at zero compute cost.
    """
    lower = text.lower()
    return any(kw in lower for kw in ANCHOR_KEYWORDS)


def check_recent_cache(domain: str) -> bool:
    """
    Checks if the domain was enriched within the last 7 days.
    If cached, bypasses LLM parsing to save compute costs.
    """
    from backend.database import SessionLocal
    from sqlalchemy import text
    from datetime import datetime, timedelta, timezone

    db = SessionLocal()
    try:
        row = db.execute(
            text(
                "SELECT last_updated FROM lead_snapshots "
                "WHERE domain=:d ORDER BY last_updated DESC LIMIT 1"
            ),
            {"d": domain}
        ).fetchone()

        if row and row[0]:
            last_updated = row[0]
            # Handle both datetime objects and ISO strings
            if isinstance(last_updated, str):
                last_updated = datetime.fromisoformat(
                    last_updated.replace("Z", "+00:00")
                )
            if datetime.now(timezone.utc) - last_updated < timedelta(days=7):
                return True
    except Exception:
        pass
    finally:
        db.close()
    return False
