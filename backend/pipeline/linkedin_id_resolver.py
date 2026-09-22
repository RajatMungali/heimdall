"""
Module: linkedin_id_resolver.py
Purpose: Fast, zero-cost resolution of a LinkedIn company slug (e.g. 'modal-labs', 'panopto')
to its numeric LinkedIn Company ID (e.g. '79045818', '956754') using lightweight HTTP requests
with search crawler User-Agents (Googlebot/Bingbot) to extract embedded SSR URN tags.
"""
import re
import httpx
from backend.utils.logger import logger

DEFAULT_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)",
    "Mozilla/5.0 (compatible; bingbot/2.0; +http://www.bing.com/bingbot.htm)"
]

URN_PATTERNS = [
    r"urn:li:fs_normalized_company:(\d+)",
    r"urn:li:fs_miniCompany:(\d+)",
    r"urn:li:company:(\d+)",
    r"urn:li:organization:(\d+)",
    r'"objectUrn"\s*:\s*"urn:li:[^"]+:(\d+)"',
    r'companyId["\s:=]+(\d+)',
    r'organizationId["\s:=]+(\d+)',
    r'data-company-id=["\'](\d+)["\']',
    r'com\.linkedin\.voyager\.organization\.Company/(\d+)',
    r'linkedin\.com/company/(\d+)'
]


async def resolve_linkedin_company_id(company_slug_or_url: str) -> str | None:
    """
    Resolves a LinkedIn company slug or URL to its numeric Company ID.
    Bypasses authwalls by leveraging search crawler User-Agents to fetch SSR HTML.
    
    Returns numeric ID string (e.g. '79045818') or None if unresolvable.
    """
    if not company_slug_or_url:
        return None

    # Clean slug from full URL or path
    company_slug = company_slug_or_url.rstrip("/").split("/")[-1].lower()
    target_url = f"https://www.linkedin.com/company/{company_slug}/"

    async with httpx.AsyncClient(follow_redirects=True, timeout=12.0) as client:
        for ua in DEFAULT_USER_AGENTS:
            headers = {
                "User-Agent": ua,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9"
            }
            try:
                resp = await client.get(target_url, headers=headers)
                
                # Check redirect location headers if any
                if resp.history:
                    for h_resp in resp.history:
                        loc = h_resp.headers.get("location", "")
                        match = re.search(r"/company/(\d+)", loc)
                        if match:
                            comp_id = match.group(1)
                            logger.info(f"Resolved LinkedIn ID for '{company_slug}' via redirect: {comp_id}")
                            return comp_id

                if resp.status_code == 200:
                    for pattern in URN_PATTERNS:
                        matches = re.findall(pattern, resp.text)
                        for match in matches:
                            # Basic validation: numeric string 6-10 digits long, not standard system IDs
                            if match and 6 <= len(match) <= 10 and match != "120000":
                                logger.info(f"Resolved LinkedIn ID for '{company_slug}': {match}")
                                return match

            except Exception as e:
                logger.debug(f"Failed resolving LinkedIn ID with UA '{ua}': {e}")

    logger.warning(f"Could not resolve numeric LinkedIn Company ID for '{company_slug}'")
    return None
