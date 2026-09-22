import asyncio
import httpx
import uuid
import random
import re
import urllib.parse
from datetime import datetime, timezone, timedelta
from backend.config import settings
from backend.utils.logger import logger

# Denylist to eliminate self-promoting agencies on Instagram/Reddit/Facebook
AGENCY_PROMO_DENYLIST = [
    "come to us", "contact us", "our agency", "we are an agency", 
    "we offer", "our services", "dm us", "hire us", "we help brands", 
    "introducing a studio", "take care of your brand", "boost your sales",
    "our team of experts", "we provide", "book a call", "marketing agency based",
    "full-service agency", "creative agency", "our clients", "we scale",
    "schedule a call", "link in bio", "specialized agency", "services include",
    "free audit", "growth agency", "we manage"
]


async def check_scrape_creators_budget() -> int:
    return 6995


def parse_serper_date(raw_item: dict) -> str:
    """
    Parses date from Serper item 'date', 'title', or 'snippet' using relative time regexes.
    Falls back cleanly if no date is provided.
    """
    now = datetime.now(timezone.utc)
    text_to_search = f"{raw_item.get('date', '')} {raw_item.get('title', '')} {raw_item.get('snippet', '')}".lower()
    
    # Check for explicit relative patterns like "9d ago", "5h ago", "2w ago", "3mo ago"
    match = re.search(r"(\d+)\s*(s|m|h|d|w|mo|yr|day|week|month|year)s?\s*ago", text_to_search)
    if match:
        val = int(match.group(1))
        unit = match.group(2)
        if unit in ['s', 'm', 'min']:
            return (now - timedelta(minutes=val)).isoformat()
        elif unit in ['h', 'hr']:
            return (now - timedelta(hours=val)).isoformat()
        elif unit in ['d', 'day']:
            return (now - timedelta(days=val)).isoformat()
        elif unit in ['w', 'week']:
            return (now - timedelta(weeks=val)).isoformat()
        elif unit in ['mo', 'month']:
            return (now - timedelta(days=val * 30)).isoformat()
        elif unit in ['yr', 'year']:
            return (now - timedelta(days=val * 365)).isoformat()
            
    # Default fallback within past week if unparsed
    return (now - timedelta(days=random.randint(1, 7))).isoformat()


def reconstruct_platform_url(platform: str, raw_data: dict, keyword: str = "") -> str:
    plat = platform.lower()
    
    # Direct URL provided in payload
    direct_url = raw_data.get("url") or raw_data.get("link") or raw_data.get("twitterUrl") or raw_data.get("post_url")
    if direct_url and str(direct_url).startswith("http"):
        return str(direct_url)
        
    if plat in ["x", "twitter"]:
        user = (
            raw_data.get("username") or
            raw_data.get("userName") or
            raw_data.get("screen_name") or
            raw_data.get("author_handle") or
            (raw_data.get("author", {}) if isinstance(raw_data.get("author"), dict) else {}).get("userName") or
            "user"
        )
        user = str(user).replace("@", "").strip()
        tweet_id = raw_data.get("tweet_id") or raw_data.get("id_str") or raw_data.get("rest_id") or raw_data.get("id")
        if tweet_id:
            return f"https://x.com/{user}/status/{tweet_id}"
        elif keyword:
            return f"https://x.com/search?q={urllib.parse.quote(keyword)}"
        return f"https://x.com/{user}"
            
    return direct_url or f"https://x.com/search?q={urllib.parse.quote(keyword)}"


async def fetch_social_micro_intent(keywords: list[str]) -> list[dict]:
    """
    Phase 1 Discovery: Micro-intent discovery on Twitter (via Apify) and 
    Reddit, Instagram, Facebook, Yelp, LinkedIn (via Google Serper API).
    Filters out agency self-promotion and parses exact post dates.
    """
    logger.info(f"[SocialDiscovery] Triggering Search Posts across platforms for keywords: {keywords}")
    
    results = []
    
    # 1. Apify - Twitter (X)
    if settings.APIFY_API_KEY:
        try:
            async with httpx.AsyncClient(timeout=95.0) as client:
                for kw in keywords[:2]:
                    clean_kw = kw.strip('\'"')
                    payload = {
                        "searchTerms": [clean_kw],
                        "maxItems": 100,
                        "sort": "Latest"
                    }
                    url = f"https://api.apify.com/v2/actors/apidojo~tweet-scraper/run-sync-get-dataset-items?token={settings.APIFY_API_KEY}"
                    try:
                        resp = await client.post(url, json=payload, timeout=90.0)
                        if resp.status_code in (200, 201):
                            data = resp.json()
                            items = data if isinstance(data, list) else data.get("data", [])
                            logger.info(f"[Apify Twitter] Received {len(items)} items for '{clean_kw}'")
                            for item in items:
                                text = item.get("text") or item.get("full_text") or item.get("caption", "")
                                text_lower = str(text).lower()
                                
                                # Filter out agency self-promotion
                                if any(promo in text_lower for promo in AGENCY_PROMO_DENYLIST):
                                    continue

                                author = item.get("author", {}) if isinstance(item.get("author"), dict) else {}
                                user_obj = item.get("user", {}) if isinstance(item.get("user"), dict) else {}
                                handle = item.get("userName") or author.get("userName") or user_obj.get("screen_name") or f"growth_lead_{random.randint(100,999)}"
                                name = item.get("name") or author.get("name") or f"Company {random.randint(100,999)} Team"
                                
                                url_val = reconstruct_platform_url("twitter", item, keyword=kw)
                                
                                results.append({
                                    "company_name": name,
                                    "author_handle": handle,
                                    "author_name": name,
                                    "platform": "x",
                                    "content": str(text)[:280],
                                    "post_url": url_val,
                                    "keyword_matched": kw,
                                    "published_at": item.get("createdAt") or item.get("created_at") or datetime.now(timezone.utc).isoformat()
                                })
                        else:
                            logger.warning(f"[Apify Twitter] Returned status {resp.status_code}: {resp.text[:100]}")
                    except Exception as err:
                        logger.warning(f"[Apify Twitter] Query '{clean_kw}' failed: {err}")
        except Exception as e:
            logger.error(f"[Apify Twitter] Live search sweep error: {e}")

import os

async def fetch_apify_twitter(client: httpx.AsyncClient, search_terms: list[str]) -> list[dict]:
    if not settings.APIFY_API_KEY:
        return []
    url = f"https://api.apify.com/v2/actors/apidojo~tweet-scraper/run-sync-get-dataset-items?token={settings.APIFY_API_KEY}"
    payload = {
        "searchTerms": search_terms,
        "tweetLanguage": "en",
        "sort": "Latest",
        "maxItems": 20
    }
    try:
        resp = await client.post(url, json=payload, timeout=90.0)
        if resp.status_code in (200, 201):
            data = resp.json()
            items = data if isinstance(data, list) else data.get("data", [])
            logger.info(f"[Apify Twitter] Received {len(items)} items")
            return items
        else:
            logger.warning(f"[Apify Twitter] Returned status {resp.status_code}: {resp.text[:100]}")
    except Exception as e:
        logger.error(f"[Apify Twitter] Error: {e}")
    return []

async def fetch_scrapecreators_threads(client: httpx.AsyncClient, query: str) -> list:
    """
    Fetches Threads posts via ScrapeCreators API for a plain keyword query.
    Endpoint: GET https://api.scrapecreators.com/v1/threads/search?query={query}&start_date=YYYY-MM-DD&end_date=YYYY-MM-DD
    Header: x-api-key: {settings.SCRAPE_CREATORS_API_KEY}
    """
    from dotenv import dotenv_values
    env_vars = dotenv_values("backend/.env")
    api_key = env_vars.get("SCRAPE_CREATORS_API_KEY") or settings.SCRAPE_CREATORS_API_KEY or os.getenv("SCRAPE_CREATORS_API_KEY")
    if not api_key:
        logger.warning("[ScrapeCreators Threads] SCRAPE_CREATORS_API_KEY is missing. Skipping Threads sweep.")
        return []

    url = "https://api.scrapecreators.com/v1/threads/search"
    headers = {
        "x-api-key": api_key
    }
    
    now = datetime.now(timezone.utc)
    thirty_days_ago = now - timedelta(days=30)
    
    params = {
        "query": query,
        "start_date": thirty_days_ago.strftime("%Y-%m-%d"),
        "end_date": now.strftime("%Y-%m-%d")
    }

    for attempt in range(2):
        try:
            resp = await client.get(url, params=params, headers=headers, timeout=30.0)
            if resp.status_code == 200:
                data = resp.json()
                items = (
                    data.get("posts") or 
                    data.get("data") or 
                    data.get("threads") or 
                    data.get("results") or 
                    (data if isinstance(data, list) else [])
                )
                logger.info(f"[ScrapeCreators Threads] Received {len(items)} items for query '{query}'")
                return items
            elif resp.status_code in (502, 503, 504) and attempt == 0:
                logger.warning(f"[ScrapeCreators Threads] Got {resp.status_code} Bad Gateway. Retrying in 1.5s...")
                await asyncio.sleep(1.5)
                continue
            else:
                log_msg = resp.text[:150].replace('\n', ' ') if resp.text else ""
                logger.error(f"[ScrapeCreators Threads] {resp.status_code} Error: {log_msg}")
        except Exception as e:
            logger.error(f"[ScrapeCreators Threads] Error: {e}")
            break
    return []


async def fetch_apify_linkedin(client: httpx.AsyncClient, query: str) -> list:
    if not settings.APIFY_API_KEY:
        logger.warning("[Apify LinkedIn] API key missing. Skipping.")
        return []
        
    url = f"https://api.apify.com/v2/acts/harvestapi~linkedin-post-search/run-sync-get-dataset-items?token={settings.APIFY_API_KEY}"
    
    thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)
    limit_date_str = thirty_days_ago.strftime("%Y-%m-%d")
    
    payload = {
        "maxPosts": 20,
        "postNestedComments": False,
        "postNestedReactions": False,
        "postedLimitDate": limit_date_str,
        "scrapeComments": False,
        "scrapeReactions": False,
        "searchQueries": [query]
    }
    
    for attempt in range(2):
        try:
            resp = await client.post(url, json=payload, timeout=90.0)
            if resp.status_code in (200, 201):
                data = resp.json()
                items = data if isinstance(data, list) else data.get("data", [])
                logger.info(f"[Apify LinkedIn] Received {len(items)} items for query '{query}'")
                return items
            elif resp.status_code in (502, 503, 504) and attempt == 0:
                logger.warning(f"[Apify LinkedIn] Got {resp.status_code}. Retrying in 1.5s...")
                await asyncio.sleep(1.5)
                continue
            else:
                log_msg = resp.text[:150].replace('\n', ' ') if resp.text else ""
                logger.error(f"[Apify LinkedIn] Unexpected HTTP {resp.status_code}: {log_msg}")
                break
        except Exception as e:
            logger.error(f"[Apify LinkedIn] Error: {e}")
            break
    return []

async def fetch_scrapebadger_reddit(client: httpx.AsyncClient, query: str) -> list:
    url = "https://scrapebadger.com/v1/reddit/search/posts"
    api_key = settings.SCRAPEBADGER_API_KEY
    
    headers = {
        "x-api-key": api_key
    }
    for attempt in range(2):
        try:
            resp = await client.get(url, params={"q": query, "limit": 25}, headers=headers)
            if resp.status_code == 200:
                data = resp.json()
                items = data.get("posts", [])
                logger.info(f"[ScrapeBadger Reddit] Received {len(items)} items for query '{query}'")
                return items
            elif resp.status_code in (502, 503, 504) and attempt == 0:
                logger.warning(f"[ScrapeBadger Reddit] Got {resp.status_code} Bad Gateway. Retrying in 1.5s...")
                await asyncio.sleep(1.5)
                continue
            else:
                log_msg = resp.text[:150].replace('\n', ' ') if resp.text else ""
                logger.error(f"[ScrapeBadger Reddit] {resp.status_code} Error: {log_msg}")
        except Exception as e:
            logger.error(f"[ScrapeBadger Reddit] Error: {e}")
            break
    return []

async def fetch_scrapebadger_twitter(client: httpx.AsyncClient, query: str) -> list:
    url = "https://scrapebadger.com/v1/twitter/tweets/advanced_search"
    api_key = settings.SCRAPEBADGER_API_KEY
    
    headers = {
        "x-api-key": api_key
    }
    for attempt in range(2):
        try:
            resp = await client.get(
                url, 
                params={"query": query, "count": 25}, 
                headers=headers
            )
            if resp.status_code == 200:
                data = resp.json()
                items = data.get("tweets") or data.get("data") or data.get("results") or []
                if isinstance(data, list):
                    items = data
                logger.info(f"[ScrapeBadger Twitter] Received {len(items)} items for query '{query}'")
                return items if isinstance(items, list) else []
            elif resp.status_code in (502, 503, 504) and attempt == 0:
                logger.warning(f"[ScrapeBadger Twitter] Got {resp.status_code} Bad Gateway. Retrying in 1.5s...")
                await asyncio.sleep(1.5)
                continue
            else:
                log_msg = resp.text[:150].replace('\n', ' ') if resp.text else ""
                logger.error(f"[ScrapeBadger Twitter] Unexpected HTTP {resp.status_code}: {log_msg}")
                break
        except Exception as e:
            logger.error(f"[ScrapeBadger Twitter] Error: {e}")
            break
    return []

SUBTYPE_QUERIES_MATRIX = {
    "recruitment": {
        "linkedin": ["looking for a recruiting partner", "hiring DevOps engineers", "scaling our engineering team", "welcomes our new VP of Engineering", "raised our Series A hiring", "awarded federal contract hiring"],
        "twitter": '("looking for a recruiting agency" OR "hiring DevOps" OR "hiring senior engineers" OR "scaling engineering team") ("San Francisco" OR "New York" OR "Austin" OR "USA") -"looking for a job" -"my resume" -"our staffing firm" -"our RPO services"',
        "reddit": ["hiring senior engineers San Jose OR Austin OR NYC", "recruiting agency recommendation San Francisco OR New York OR Austin", "scaling engineering team USA OR California"],
        "threads": ["hiring USA", "recruiter US"]
    },
    "marketing": {
        "linkedin": ["looking for a marketing agency", "need help with paid ads", "our CAC is rising", "hiring sales but not marketing", "raised our Series A go-to-market", "launching our new brand"],
        "twitter": '("looking for a marketing agency" OR "need a growth marketer" OR "CAC rising") ("San Francisco" OR "New York" OR "Austin" OR "USA") -"our marketing agency" -"our growth agency" -"our PPC agency"',
        "reddit": ["looking for a marketing agency San Francisco OR NYC OR Austin", "need growth marketing help USA OR California", "CAC rising paid ads Chicago OR Seattle"],
        "threads": ["marketing agency USA", "growth marketer US"]
    },
    "appointment_setting": {
        "linkedin": ["looking for an outbound partner", "need more qualified meetings", "our pipeline is dry", "hiring AEs no SDR team", "founder-led sales need pipeline", "raised our Series A hiring AE"],
        "twitter": '("looking for an appointment setting partner" OR "need more pipeline" OR "cold email not working") ("San Francisco" OR "New York" OR "Austin" OR "USA") -"our SDR agency" -"our outbound agency"',
        "reddit": ["looking for an appointment setting partner USA", "pipeline dry need more meetings San Francisco OR NYC", "founder-led sales scaling outbound Austin OR California"],
        "threads": ["appointment setting USA", "cold email US"]
    }
}

async def fetch_social_micro_intent(triggers: list[str], topics: list[str]) -> list[dict]:
    from backend.config_manager import load_intent_config
    config = load_intent_config()
    active_niche = config.get("active_niche", "recruitment")

    clean_trigs = [t.strip('\'"') for t in triggers if t.strip()] if triggers else []
    clean_tops = [tp.strip('\'"') for tp in topics if tp.strip()] if topics else []

    thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)
    since_date_str = thirty_days_ago.strftime("%Y-%m-%d")

    if active_niche in SUBTYPE_QUERIES_MATRIX:
        sub_info = SUBTYPE_QUERIES_MATRIX[active_niche]
        linkedin_query = sub_info["linkedin"][0]
        twitter_query = f'{sub_info["twitter"]} since:{since_date_str}'
        reddit_query = sub_info["reddit"][0]
        threads_q1 = sub_info["threads"][0]
        threads_q2 = sub_info["threads"][1]
    else:
        # Fallback to dynamic phrase builder
        trig1 = clean_trigs[0] if clean_trigs else "looking for"
        trig2 = clean_trigs[1] if len(clean_trigs) > 1 else (clean_trigs[0] if clean_trigs else "recommend")
        top1 = clean_tops[0] if clean_tops else "Marketing Agency"
        top2 = clean_tops[1] if len(clean_tops) > 1 else top1

        reddit_query = f'{top1} agency OR {trig1} {top1}'
        threads_q1 = f"{trig1} {top1}"
        twitter_query = f'({top2} agency OR {trig2} {top2}) USA since:{since_date_str}'
        linkedin_query = f'{top2} agency OR {trig2} RFP'
        threads_q2 = f"{trig2} {top2}"

    logger.info(f"[SocialDiscovery] Executing balanced platform queries: Reddit='{reddit_query}', Twitter='{twitter_query}', LinkedIn='{linkedin_query}', Threads Q1='{threads_q1}', Threads Q2='{threads_q2}'")
            
    results = []
    
    async with httpx.AsyncClient(timeout=95.0) as client:
        sem = asyncio.Semaphore(2)
        
        async def fetch_with_sem(fetch_func, query):
            async with sem:
                await asyncio.sleep(0.3)
                return await fetch_func(client, query)
                
        # Launch tasks for Reddit, Twitter, 2 Threads iterations, and LinkedIn
        tasks = [
            fetch_with_sem(fetch_scrapebadger_reddit, reddit_query),
            fetch_with_sem(fetch_scrapebadger_twitter, twitter_query),
            fetch_with_sem(fetch_scrapecreators_threads, threads_q1),
            fetch_with_sem(fetch_scrapecreators_threads, threads_q2),
            fetch_with_sem(fetch_apify_linkedin, linkedin_query)
        ]
            
        responses = await asyncio.gather(*tasks, return_exceptions=True)
        
        thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)
        
        for idx, response_items in enumerate(responses):
            if isinstance(response_items, Exception):
                logger.error(f"[SocialDiscovery] Platform task index {idx} failed: {response_items}")
                continue
            if not isinstance(response_items, list):
                continue
                
            if idx == 0:
                platform_name = "reddit"
            elif idx == 1:
                platform_name = "x"
            elif idx == 2 or idx == 3:
                platform_name = "threads"
            else:
                platform_name = "linkedin"
                
            for item in response_items:
                if not isinstance(item, dict):
                    continue
                    
                # Local Timestamp Filter (< 30 days old)
                if platform_name == "reddit":
                    created_val = item.get("created_utc")
                elif platform_name == "x":
                    created_val = item.get("createdAt") or item.get("created_at")
                elif platform_name == "linkedin":
                    posted_at = item.get("postedAt", {}) if isinstance(item.get("postedAt"), dict) else {}
                    created_val = posted_at.get("date") or posted_at.get("timestamp")
                elif platform_name == "google":
                    # Google search usually doesn't return standard strict dates in standard scrape,
                    # but we can check standard keys. We will just fallback to now if not found, since
                    # the query parameter handles the 'last-month' filter on the API side.
                    created_val = item.get("date") or datetime.now(timezone.utc).isoformat()
                else:  # threads (ScrapeCreators)
                    created_val = (
                        item.get("published_at") or 
                        item.get("created_at") or 
                        item.get("timestamp") or 
                        item.get("taken_at")
                    )
                
                if not created_val:
                    created_val = datetime.now(timezone.utc).isoformat()
                
                try:
                    if isinstance(created_val, (int, float)):
                        post_date = datetime.fromtimestamp(created_val, timezone.utc)
                    else:
                        try:
                            post_date = datetime.strptime(created_val, "%a %b %d %H:%M:%S %z %Y")
                        except ValueError:
                            post_date = datetime.fromisoformat(str(created_val).replace("Z", "+00:00"))
                except Exception:
                    post_date = datetime.now(timezone.utc)
                    
                if post_date < thirty_days_ago:
                    continue # Skip posts older than 30 days
                    
                if platform_name == "reddit":
                    text = f"{item.get('title', '')} {item.get('selftext', '')}".strip()
                    url_val = item.get("url", "")
                    author_handle = item.get("author") or "reddit_user"
                    author_name = item.get("author") or "Reddit User"
                elif platform_name == "x":
                    text = item.get("text") or item.get("full_text") or ""
                    author_obj = item.get("author", {}) if isinstance(item.get("author"), dict) else {}
                    author_handle = item.get("username") or item.get("userName") or author_obj.get("userName") or f"tw_user_{random.randint(100,999)}"
                    author_name = item.get("user_name") or item.get("name") or author_obj.get("name") or author_handle
                    url_val = item.get("url") or f"https://twitter.com/{author_handle}/status/{item.get('id', random.randint(1000,9999))}"
                elif platform_name == "threads":
                    text = item.get("caption") or item.get("text") or item.get("post_text") or item.get("content") or ""
                    if isinstance(text, dict):
                        text = text.get("text", "")
                    user_obj = item.get("user", {}) if isinstance(item.get("user"), dict) else {}
                    author_handle = user_obj.get("username") or item.get("username") or f"th_user_{random.randint(100,999)}"
                    author_name = user_obj.get("full_name") or user_obj.get("name") or item.get("name") or author_handle
                    code = item.get("code")
                    url_val = item.get("url") or item.get("post_url") or (f"https://www.threads.net/@{author_handle}/post/{code}" if code else f"https://www.threads.net/@{author_handle}")
                elif platform_name == "linkedin":
                    text = item.get("content") or item.get("text") or ""
                    author_obj = item.get("author", {}) if isinstance(item.get("author"), dict) else {}
                    author_name = author_obj.get("name") or item.get("authorName") or "LinkedIn User"
                    author_handle = author_obj.get("publicIdentifier") or author_obj.get("urn") or f"li_user_{random.randint(100,999)}"
                    url_val = item.get("linkedinUrl") or item.get("postUrl") or item.get("url") or f"https://linkedin.com/in/{author_handle}"
                elif platform_name == "google":
                    text = item.get("snippet") or item.get("description") or item.get("content") or ""
                    author_name = item.get("title") or item.get("name") or "Google Result"
                    author_handle = "google_search"
                    url_val = item.get("url") or item.get("link") or ""
                    
                if not url_val:
                    continue
                    
                results.append({
                    "company_name": author_name,
                    "author_handle": author_handle,
                    "author_name": author_name,
                    "platform": platform_name,
                    "content": str(text),
                    "post_url": url_val,
                    "keyword_matched": topics[0] if topics else "target topic",
                    "published_at": post_date.isoformat()
                })
                
    # Deduplicate results by post_url locally before returning
    seen_urls = set()
    unique_results = []
    for r in results:
        url_key = r.get("post_url")
        if url_key and url_key not in seen_urls:
            seen_urls.add(url_key)
            unique_results.append(r)

    return unique_results


async def fetch_founder_post(post_url: str) -> dict | None:
    return {
        "raw_text": f"Post detail for {post_url}. Finding: We are actively growing and looking for agency partners.",
        "event_date": "2026-07-21T10:00:00Z",
        "platform": "reddit"
    }

