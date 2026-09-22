import asyncio
import json
import httpx
import urllib.parse
import re
from datetime import datetime, timezone, timedelta
from backend.config import settings
from dotenv import dotenv_values
from backend.config_manager import load_intent_config
from backend.utils.logger import logger

def sanitize_url(url: str, platform: str) -> str | None:
    if not url:
        return None
        
    if platform == "X":
        match = re.search(r"(x\.com|twitter\.com)/[^/]+/status/\d+", url)
        return f"https://{match.group(0)}" if match else None
        
    elif platform == "LinkedIn":
        if "/posts/" in url or "/activity-" in url or "/feed/update/" in url:
            return url
        return None

    elif platform == "NewsAPI":
        return url if url.startswith("http") else None
        
    elif platform == "Reddit":
        return url if "/comments/" in url else None

    return url

config = load_intent_config()
target_topics = config.get("social_topics", ["B2B services"])
topics_str = "/".join(target_topics)

SYSTEM_INSTRUCTION_TEMPLATE = """
You are an execution agent responsible for populating a B2B Lead Intelligence Dashboard.
You will be provided with an array of 5 target company objects at runtime, each containing { "company_name": "...", "domain": "..." } and their raw extracted signals.

Your task is to synthesize these signals into intent scores and construct a structured JSON output for each company.

### EXECUTION STEPS PER COMPANY

STEP 1: MULTI-SOCIAL SIGNAL SCRAPING (ScrapeBadger API)
From the provided signals, extract ONLY the TOP 2 MOST INTENT-DRIVEN posts per platform (LinkedIn, X, Reddit).
- MANDATORY URL FORMAT: `source_link` MUST be the full absolute URL starting with https:// (e.g., https://x.com/user/status/123, https://reddit.com/r/...). Do NOT use relative paths.

STEP 2: MEDIA & PRESS EXTRACTION (NewsAPI)
- Select up to 2 top news mentions from the provided news signals.
- MANDATORY URL FORMAT: `source_link` MUST be the direct canonical article URL.
- FALLBACK RULE: If no funding articles exist, set "funding_stage": "Bootstrapped / Undisclosed".

STEP 3: EXECUTIVE DISCOVERY (Serper API)
- Extract up to 3 executive names, titles, and LinkedIn profile links from the provided exec signals.

STEP 4: DUMMY DATA INJECTION (FOR APOLLO & PROSPEO EXCLUSIVE FIELDS)
Inject placeholders with explicit status tags for fields reserved for paid enrichment:
1. Executive Emails:
   - Generate pattern email: first.last@{company_domain}
   - Tag explicitly: email_status: "GENERATED"
2. Hiring & Revenue Velocity:
   - Set status: "High Velocity Growth" (if active posts/news exist) or "Steady Growth".
   - Tag explicitly: velocity_status: "MOCK_ESTIMATE"

STEP 5: INTENT SYNTHESIS & AI VERDICT
Synthesize all collected social posts and news articles into the final JSON output:
1. composite_intent_score: Numeric score (0–100) based on signal recency, density, and growth indicators.
2. ai_verdict: A concise 2-sentence pitch strategy. The first sentence MUST reference exact numbers from the data (e.g., "$187M funding", "$1B volume", "50 locations"). The second sentence must pitch a specific service related to {topics_str} to support that exact metric.
3. Populate detected_signals (max 8 signals total per company across LinkedIn, X, Reddit, and Serper News) to feed directly into the EXTRACTION EVIDENCE LOG UI.

### CRITICAL SCHEMA RULES
1. 'funding_stage' MUST strictly be one of: ["Pre-Seed", "Seed", "Series A", "Series B", "Series C+", "Growth", "Private Equity", "Bootstrapped", "UNKNOWN"]. Do NOT put dollar amounts into 'funding_stage'.
2. If 'hiring_velocity' cannot be verified from live social/job signals, set 'hiring_velocity_tag' to "MOCK_ESTIMATE".

### LLM GROUNDING & GUARDRAILS
You are a strict data synthesizer. Base all fields EXCLUSIVELY on the provided raw JSON signals. 
- If no news or funding articles exist in the input, set 'funding_stage' to 'UNKNOWN'.
- Do NOT guess or assume 'Bootstrapped' if funding data is missing.
- Only mark verification_status as 'Verified' if supported by a direct quote or link.

---

### REQUIRED OUTPUT JSON SCHEMA

Return ONLY a valid JSON array of objects for the 5 target companies. Do not include prose explanations outside the JSON block.

[
  {
    "company_name": "String",
    "domain": "String",
    "contact_reliability_score": "80%",
    "trust_tier": "High Trust",
    "infographics": {
      "employee_count": "String (e.g., '51-200 employees (Est.)')",
      "funding_stage": "String (e.g., 'Series B / Seed')",
      "hiring_velocity": "String (e.g., 'High Velocity Growth')",
      "hiring_velocity_tag": "MOCK_ESTIMATE"
    },
    "composite_intent": {
      "score": 88,
      "freshness": "90% Fresh",
      "detected_signals": [
        {
          "platform": "LinkedIn | X | Reddit | Serper News",
          "category": "PARTNERSHIP INTEREST | PRODUCT LAUNCH | HIRING | MEDIA MENTION",
          "quote": "Verbatim quote or headline snippet",
          "source_link": "Direct post permalink URL",
          "recency": "UNKNOWN | RECENT | 2 days ago",
          "impact_score": "+12.5 pts",
          "verification_status": "Verified (100%)"
        }
      ]
    },
    "ai_verdict": "String summary of agency pitch strategy.",
    "key_contacts": [
      {
        "name": "String",
        "title": "String",
        "email": "string@domain.com",
        "email_status": "GENERATED",
        "linkedin_url": "URL if available"
      }
    ]
  }
]
"""

SYSTEM_INSTRUCTION = SYSTEM_INSTRUCTION_TEMPLATE.replace("{topics_str}", topics_str)


async def fetch_linkedin_slug(client: httpx.AsyncClient, company_name: str) -> str:
    clean_name = company_name.replace(" World", "").replace(" Inc", "").replace(" LLC", "").replace(" Inc.", "").strip()
    if not settings.SERPER_API_KEY: return clean_name.lower().replace(" ", "-")
    
    query = f'site:linkedin.com/company/ "{company_name}"'
    try:
        res = await client.post("https://google.serper.dev/search", headers={"X-API-KEY": settings.SERPER_API_KEY}, json={"q": query, "num": 3})
        for r in res.json().get("organic", []):
            link = r.get("link", "")
            if "linkedin.com/company/" in link:
                slug = link.split("linkedin.com/company/")[1].strip("/").split("/")[0]
                if clean_name.lower() in slug.lower() or company_name.lower() in link.lower():
                    return slug
    except Exception: pass
    
    # Fallback to a broader query if the first one failed
    query_2 = f'site:linkedin.com/company/ "{clean_name}"'
    try:
        res = await client.post("https://google.serper.dev/search", headers={"X-API-KEY": settings.SERPER_API_KEY}, json={"q": query_2, "num": 3})
        for r in res.json().get("organic", []):
            link = r.get("link", "")
            if "linkedin.com/company/" in link:
                slug = link.split("linkedin.com/company/")[1].strip("/").split("/")[0]
                return slug
    except Exception: pass

    return clean_name.lower().replace(" ", "-")

async def scrapebadger_get(client: httpx.AsyncClient, url: str, params: dict = None) -> httpx.Response | None:
    if not settings.SCRAPEBADGER_API_KEY: return None
    headers = {"x-api-key": settings.SCRAPEBADGER_API_KEY}
    for attempt in range(3):
        try:
            # Small pre-request delay to space out concurrent calls
            if attempt > 0:
                wait_time = 5 * (2 ** attempt)  # 10s, 20s
            else:
                await asyncio.sleep(0.5)  # 0.5s breathing room on first try
                wait_time = 0
            if wait_time:
                logger.info(f"ScrapeBadger rate-limit backoff: waiting {wait_time}s (attempt {attempt + 1}/3)")
                await asyncio.sleep(wait_time)
            res = await client.get(url, params=params, headers=headers)
            if res.status_code == 200:
                return res
            elif res.status_code in (429, 502, 503):
                continue
            else:
                break
        except Exception as e:
            if attempt == 2:
                logger.warning(f"ScrapeBadger request failed: {e}")
    return None



async def fetch_twitter_posts(client: httpx.AsyncClient, company_name: str, domain: str) -> list:
    if not settings.SCRAPEBADGER_API_KEY: return []
    
    clean_name = re.sub(r'\b(Inc|LLC|Corp|Corporation|Co|World|Inc\.|LLC\.)\b\.?', '', company_name, flags=re.IGNORECASE).strip()
    
    if domain:
        query = f'"{domain}" OR ("{clean_name}")'
    else:
        query = f'"{clean_name}"'
    
    try:
        res = await scrapebadger_get(
            client,
            "https://scrapebadger.com/v1/twitter/tweets/advanced_search",
            params={"query": query, "count": 20}
        )
        if res and res.status_code == 200:
            posts = []
            json_res = res.json()
            raw_posts = json_res.get("tweets") or json_res.get("data") or json_res.get("results") or []
            if isinstance(json_res, list):
                raw_posts = json_res
                
            for t in raw_posts[:5]:
                url = t.get("url") or t.get("link", "")
                if not url and t.get("id"):
                    url = f"https://x.com/user/status/{t.get('id')}"
                safe_url = sanitize_url(url, "X") or url
                t["url"] = safe_url
                posts.append(t)
            return posts
    except Exception as e:
        logger.warning(f"Failed to fetch Twitter posts for {company_name}: {e}")
    return []

async def fetch_reddit_posts(client: httpx.AsyncClient, company_name: str, domain: str = "") -> list:
    if not settings.SCRAPEBADGER_API_KEY: 
        return []
    
    # 1. Clean corporate suffixes using regex word boundaries
    clean_name = re.sub(r'\b(Inc|LLC|Corp|Corporation|Co|World)\b\.?', '', company_name, flags=re.IGNORECASE).strip()
    c_name_no_spaces = clean_name.replace(" ", "")
    
    # 2. Build a flexible query matching domain OR brand variants
    name_variants = [f'"{clean_name}"']
    if c_name_no_spaces != clean_name:
        name_variants.append(f'"{c_name_no_spaces}"')
        
    name_query = " OR ".join(name_variants)
    
    if domain:
        query = f'"{domain}" OR ({name_query})'
    else:
        query = name_query

    try:
        # 3. Query ScrapeBadger Reddit Search
        res = await scrapebadger_get(
            client, 
            "https://scrapebadger.com/v1/reddit/search/posts", 
            params={"q": query, "sort": "relevance"}
        )
        
        if res and res.status_code == 200:
            posts = []
            json_res = res.json()
            
            # FIX: Support both 'posts' (Reddit standard) and 'data' (fallback) keys
            raw_posts = json_res.get("posts") or json_res.get("data") or []
            
            import datetime
            for p in raw_posts[:5]:
                url = sanitize_url(p.get("url", ""), "Reddit") or p.get("url", "")
                if url:
                    p["url"] = url
                    if "created_utc" in p:
                        try:
                            p["date"] = datetime.datetime.fromtimestamp(p["created_utc"], datetime.timezone.utc).isoformat()
                        except Exception:
                            pass
                    posts.append(p)
            return posts

    except Exception as e:
        logger.error(f"Error extracting metadata for domain {domain}: {e}")
        
    return []

async def fetch_news_mentions(client: httpx.AsyncClient, company_name: str, domain: str) -> list:
    if not settings.SERPER_API_KEY: return []
    # Serper (Google) uses space for AND, so we format accordingly
    query = f'("{company_name}" OR "{domain}") ("funding" OR "raised" OR "Series")'
    try:
        res = await client.post(
            "https://google.serper.dev/news",
            headers={"X-API-KEY": settings.SERPER_API_KEY, "Content-Type": "application/json"},
            json={"q": query, "num": 5}
        )
        if res.status_code == 200:
            articles = []
            for a in res.json().get("news", []):
                url = sanitize_url(a.get("link", ""), "NewsAPI")
                if url:
                    a["url"] = url
                    articles.append(a)
            return articles
    except Exception: pass
    return []

async def fetch_executives(client: httpx.AsyncClient, company_name: str, domain: str) -> list:
    if not settings.SERPER_API_KEY: return []
    query = f'site:linkedin.com/in "{company_name}" ("CEO" OR "Founder" OR "VP Marketing" OR "CMO" OR "Director")'
    c_lower = company_name.lower()
    try:
        res = await client.post("https://google.serper.dev/search", headers={"X-API-KEY": settings.SERPER_API_KEY}, json={"q": query, "num": 10})
        execs = []
        for r in res.json().get("organic", []):
            text = (r.get("title", "") + " " + r.get("snippet", "")).lower()
            # Strict boundary checking prevents "Project Read AI" from matching "Read AI"
            if domain in text or f"at {c_lower}" in text or f"- {c_lower}" in text or f"| {c_lower}" in text or f" {c_lower} " in text:
                execs.append(r)
            if len(execs) == 3:
                break
        
        # Fallback if strict filtering drops everyone
        if not execs:
            return res.json().get("organic", [])[:3]
        return execs
    except Exception: pass
    return []

async def gather_company_signals(companies: list[dict]) -> list[dict]:
    logger.info(f"Gathering Multi-Platform Signals for {len(companies)} companies...")
    
    import dns.resolver
    
    enriched_data = []
    async with httpx.AsyncClient(timeout=15.0) as client:
        for comp in companies:
            c_name = comp["company_name"]
            domain = comp.get("domain", "")
            
            # Discovery: if no domain provided, use Serper to find official site
            if not domain:
                if settings.SERPER_API_KEY:
                    query = f'"{c_name}" official site'
                    try:
                        res = await client.post("https://google.serper.dev/search", headers={"X-API-KEY": settings.SERPER_API_KEY}, json={"q": query, "num": 3})
                        for r in res.json().get("organic", []):
                            link = r.get("link", "")
                            if "linkedin.com" not in link and "wikipedia.org" not in link and "bloomberg.com" not in link:
                                domain = urllib.parse.urlparse(link).netloc.replace("www.", "")
                                break
                    except Exception: pass
                if not domain:
                    domain = f"{c_name.lower().replace(' ', '')}.com"
                    
            # Validation: MX Record Check
            def check_mx():
                try:
                    return bool(dns.resolver.resolve(domain, 'MX'))
                except Exception:
                    return False
            is_valid = await asyncio.to_thread(check_mx)
            if not is_valid:
                logger.warning(f"Domain {domain} failed MX validation. Proceeding with caution.")
            
            slug = await fetch_linkedin_slug(client, c_name)
            tw_posts = await fetch_twitter_posts(client, c_name, domain)
            rd_posts = await fetch_reddit_posts(client, c_name, domain)
            news = await fetch_news_mentions(client, c_name, domain)
            execs = await fetch_executives(client, c_name, domain)
            
            enriched_data.append({
                "company_name": c_name,
                "domain": domain,
                "mx_valid": is_valid,
                "signals": {
                    "linkedin_profile": {}, # Deprecated ScrapeBadger integration
                    "linkedin_posts": [],   # Deprecated ScrapeBadger integration
                    "twitter_posts": tw_posts,
                    "reddit_posts": rd_posts,
                    "news_articles": news,
                    "executives": execs
                }
            })
    return enriched_data

async def synthesize_intent(enriched_data: list[dict]) -> list[dict]:
    env_vars = dotenv_values("backend/.env")
    openrouter_key = env_vars.get("OPENROUTER_API_KEY") or getattr(settings, "OPENROUTER_API_KEY", "")

    if not openrouter_key:
        logger.error("OPENROUTER_API_KEY is missing. Cannot run synthesis.")
        return []

    prompt = f"Here is the raw scraped data for the {len(enriched_data)} companies. Analyze it strictly according to the system instructions and output the JSON array.\n\n"
    prompt += json.dumps(enriched_data, indent=2)

    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {openrouter_key}",
        "HTTP-Referer": "https://heimdall.app",
        "X-Title": "Heimdall Lead Intel",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": "meta-llama/llama-3.3-70b-instruct",
        "messages": [
            {"role": "system", "content": SYSTEM_INSTRUCTION},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.2
    }

    try:
        async with httpx.AsyncClient(timeout=45.0) as client:
            resp = await client.post(url, headers=headers, json=payload)
            if resp.status_code != 200:
                logger.warning(f"[Enrichment OpenRouter] Primary model failed with HTTP {resp.status_code}. Retrying with deepseek/deepseek-chat")
                payload["model"] = "deepseek/deepseek-chat"
                resp = await client.post(url, headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()
            content = data["choices"][0]["message"]["content"]
            
            cleaned_content = content.replace("```json", "").replace("```", "").strip()
            return json.loads(cleaned_content)
    except Exception as e:
        logger.error(f"Failed to generate composite intent with OpenRouter LLM: {e}")
        return []

async def execute_enrichment_pipeline(companies: list[dict]) -> list[dict]:
    enriched_data = await gather_company_signals(companies)
    return await synthesize_intent(enriched_data)

# Domains to ignore when looking for the company's canonical website
EXCLUDED_DOMAINS = {
    "linkedin.com", "facebook.com", "twitter.com", "x.com", "wikipedia.org",
    "crunchbase.com", "youtube.com", "instagram.com", "pitchbook.com",
    "g2.com", "capterra.com", "glassdoor.com", "bloomberg.com", "ycombinator.com"
}

async def fetch_harvestapi_linkedin_company(linkedin_url: str, apify_api_key: str) -> dict:
    """
    Calls riceman~linkedin-company-data-insights-scraper actor on Apify asynchronously to retrieve complete company infographics & insights.
    """
    if not apify_api_key or apify_api_key == "mock_key_if_empty":
        return {}

    url = f"https://api.apify.com/v2/acts/riceman~linkedin-company-data-insights-scraper/run-sync-get-dataset-items?token={apify_api_key}"
    payload = {
        "company_linkedin_urls": [linkedin_url],
        "get_company_insights": True,
        "get_total_job_openings": True
    }

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            res = await client.post(url, json=payload)
            if res.status_code in (200, 201):
                items = res.json()
                if items and isinstance(items, list) and len(items) > 0:
                    return items[0]
                elif isinstance(items, dict):
                    return items
    except Exception as e:
        logger.error(f"[Riceman LinkedIn] Error fetching details for {linkedin_url}: {e}")

    return {}


async def fetch_harvestapi_linkedin_posts(linkedin_url: str, apify_api_key: str) -> list[dict]:
    """
    Calls harvestapi~linkedin-company-posts actor on Apify asynchronously to retrieve latest official company posts.
    """
    if not apify_api_key or apify_api_key == "mock_key_if_empty" or not linkedin_url:
        return []

    actor_id = "harvestapi~linkedin-company-posts"
    url = f"https://api.apify.com/v2/acts/{actor_id}/runs?token={apify_api_key}"
    payload = {
        "includeQuotePosts": True,
        "includeReposts": True,
        "maxComments": 5,
        "maxPosts": 5,
        "maxReactions": 5,
        "postNestedComments": False,
        "postNestedReactions": False,
        "scrapeComments": False,
        "scrapeReactions": False,
        "targetUrls": [linkedin_url]
    }

    try:
        async with httpx.AsyncClient(timeout=25.0) as client:
            res = await client.post(url, json=payload)
            if res.status_code not in (200, 201):
                return []
            
            run_data = res.json().get("data", {})
            run_id = run_data.get("id")
            dataset_id = run_data.get("defaultDatasetId")
            if not run_id or not dataset_id:
                return []

            status_url = f"https://api.apify.com/v2/actor-runs/{run_id}?token={apify_api_key}"
            for _ in range(12):
                await asyncio.sleep(2)
                st_res = await client.get(status_url)
                if st_res.status_code == 200:
                    status = st_res.json().get("data", {}).get("status")
                    if status == "SUCCEEDED":
                        items_url = f"https://api.apify.com/v2/datasets/{dataset_id}/items?token={apify_api_key}"
                        items_res = await client.get(items_url)
                        if items_res.status_code == 200:
                            items = items_res.json()
                            if isinstance(items, list):
                                logger.info(f"[HarvestAPI LinkedIn Posts] Fetched {len(items)} posts for {linkedin_url}")
                                return items
                        break
                    elif status in ["FAILED", "ABORTED", "TIMED-OUT"]:
                        break
    except Exception as e:
        logger.error(f"[HarvestAPI LinkedIn Posts] Error fetching posts for {linkedin_url}: {e}")

    return []


async def fetch_serper_company_fallback(company_name: str, serper_api_key: str) -> tuple[str | None, dict]:
    """
    Fallback when Apify HarvestAPI actor fails or returns an error.
    Queries Serper Google Search to extract domain, description, industry, and knowledge graph attributes.
    """
    if not serper_api_key or serper_api_key == "mock_key_if_empty":
        return None, {}

    url = "https://google.serper.dev/search"
    headers = {"X-API-KEY": serper_api_key, "Content-Type": "application/json"}
    payload = {"q": f'"{company_name}" official website software company', "num": 5}
    
    resolved_domain = None
    firmographics = {}

    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            res = await client.post(url, headers=headers, json=payload)
            if res.status_code == 200:
                data = res.json()
                kg = data.get("knowledgeGraph", {})
                
                # Domain extraction
                kg_site = kg.get("website") or kg.get("attributes", {}).get("Website")
                if kg_site:
                    import urllib.parse
                    resolved_domain = urllib.parse.urlparse(kg_site if kg_site.startswith("http") else f"https://{kg_site}").netloc.replace("www.", "").lower()

                if not resolved_domain:
                    for item in data.get("organic", []):
                        link = item.get("link", "")
                        import urllib.parse
                        dom = urllib.parse.urlparse(link).netloc.replace("www.", "").lower()
                        if dom and not any(excluded in dom for excluded in EXCLUDED_DOMAINS):
                            resolved_domain = dom
                            break

                # Extract rich fallback firmographics
                snippet = kg.get("description") or (data.get("organic", [{}])[0].get("snippet") if data.get("organic") else None)
                industry = kg.get("type") or kg.get("category") or "B2B Software & Services"
                
                firmographics = {
                    "description": snippet,
                    "industry": industry,
                    "employee_count": None,
                    "source": "serper_fallback"
                }
                logger.info(f"[Serper Fallback] Extracted domain & info for {company_name}: Domain={resolved_domain}, Industry={industry}")
    except Exception as e:
        logger.error(f"[Serper Fallback] Failed for {company_name}: {e}")

    return resolved_domain, firmographics


async def resolve_domain_via_serper(
    company_name: str, serper_api_key: str, phase1_estimated_domain: str = ""
) -> tuple[str, dict]:
    """
    Resolves official company domain & full infographics.
    1. Uses Serper Google Search to find company's official LinkedIn page.
    2. Feeds LinkedIn URL to HarvestAPI Apify actors ('harvestapi~linkedin-company' and 'harvestapi~linkedin-company-posts').
    3. Extracts verified website domain, headcount, industry name, description, specialities, and latest official posts.
    4. FALLBACK TO SERPER: If Apify actor encounters an error or returns empty data, falls back to Serper Knowledge Graph & Search.
    """
    from backend.config import settings
    apify_key = getattr(settings, "APIFY_API_KEY", "")
    
    resolved_domain = None
    firmographics = {}

    # Step 1: Serper Google Search for Company's official LinkedIn Page
    if serper_api_key and serper_api_key != "mock_key_if_empty":
        try:
            url = "https://google.serper.dev/search"
            headers = {"X-API-KEY": serper_api_key, "Content-Type": "application/json"}
            query = f'site:linkedin.com/company "{company_name}"'
            payload = {"q": query, "num": 5}
            
            async with httpx.AsyncClient(timeout=8.0) as client:
                res = await client.post(url, headers=headers, json=payload)
                if res.status_code == 200:
                    data = res.json()
                    linkedin_url = None
                    import re
                    for item in data.get("organic", []):
                        link = item.get("link", "")
                        # Normalize to root company URL e.g. linkedin.com/company/triomics
                        match = re.search(r"(https?://(?:www\.)?linkedin\.com/company/[^/\?\s]+)", link)
                        if match:
                            linkedin_url = match.group(1)
                            break
                            
                    if linkedin_url and apify_key:
                        logger.info(f"[Entity Resolution] Found LinkedIn URL for {company_name}: {linkedin_url}")
                        # Step 2: Feed LinkedIn URL to HarvestAPI Apify actors concurrently
                        details, posts = {}, []
                        try:
                            details, posts = await asyncio.gather(
                                fetch_harvestapi_linkedin_company(linkedin_url, apify_key),
                                fetch_harvestapi_linkedin_posts(linkedin_url, apify_key)
                            )
                        except Exception as actor_err:
                            logger.error(f"[HarvestAPI Actor Error] {actor_err}. Falling back to Serper for {company_name}.")

                        if details:
                            # Extract domain from company website URL
                            site = details.get("website") or details.get("domain") or details.get("callToActionUrl")
                            if site:
                                import urllib.parse
                                resolved_domain = urllib.parse.urlparse(site if site.startswith("http") else f"https://{site}").netloc.replace("www.", "").lower()

                            # Extract headcount
                            emp_count = details.get("employee_count")
                            if not emp_count and details.get("employee_range"):
                                emp_count = details.get("employee_range")

                            # Safely extract industry name
                            industries = details.get("industries", [])
                            industry_name = "B2B Software & Services"
                            if isinstance(industries, list) and len(industries) > 0:
                                first_ind = industries[0]
                                if isinstance(first_ind, dict):
                                    industry_name = first_ind.get("name") or first_ind.get("title") or industry_name
                                elif isinstance(first_ind, str):
                                    industry_name = first_ind

                                firmographics = {
                                    "employee_count": emp_count,
                                    "industry": industry_name,
                                    "description": details.get("description"),
                                    "specialities": details.get("specialities", []),
                                    "company_type": details.get("companyType"),
                                    "logo": details.get("logo"),
                                    "linkedin_url": linkedin_url,
                                    "locations": details.get("locations", []),
                                    "hq_country": details.get("hq_country"),
                                    "linkedin_posts": posts
                                }
                            logger.info(f"[Entity Resolution] HarvestAPI infographics fetched for {company_name}: Domain={resolved_domain}, Headcount={emp_count}, Industry={industry_name}")
                        else:
                            logger.warning(f"[Entity Resolution] Apify HarvestAPI returned empty/error for {company_name}. Executing Serper fallback...")
                            serper_dom, serper_firmos = await fetch_serper_company_fallback(company_name, serper_api_key)
                            if serper_dom:
                                resolved_domain = serper_dom
                            if serper_firmos:
                                firmographics = serper_firmos
                                if linkedin_url:
                                    firmographics["linkedin_url"] = linkedin_url
        except Exception as e:
            logger.error(f"[Entity Resolution] Serper/HarvestAPI resolution failed for {company_name}: {e}")

    # Fallback to Phase 1 estimated domain if website still missing
    if not resolved_domain and phase1_estimated_domain:
        clean_est = phase1_estimated_domain.lower().replace("https://", "").replace("http://", "").replace("www.", "").strip("/")
        if "." in clean_est and not any(ext in clean_est for ext in EXCLUDED_DOMAINS):
            resolved_domain = clean_est

    # Organic Serper fallback if still unresolved
    if not resolved_domain and serper_api_key and serper_api_key != "mock_key_if_empty":
        serper_dom, serper_firmos = await fetch_serper_company_fallback(company_name, serper_api_key)
        if serper_dom:
            resolved_domain = serper_dom
        if serper_firmos and not firmographics:
            firmographics = serper_firmos

    if not resolved_domain:
        resolved_domain = f"{company_name.lower().replace(' ', '')}.com"

    return resolved_domain, firmographics
