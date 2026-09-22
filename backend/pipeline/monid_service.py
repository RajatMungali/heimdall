import os
import json
from typing import Dict, Any, List, Optional
import httpx
from dotenv import load_dotenv

load_dotenv()
load_dotenv("backend/.env")
from backend.utils.logger import logger

MONID_API_BASE_URL = os.getenv("MONID_API_BASE_URL", "https://api.monid.ai/v1")

class MonidAIService:
    """
    Monid AI REST Client for keyword discovery and social media signal scraping.
    """
    def __init__(self, api_key: Optional[str] = None):
        self._api_key = api_key
        self.base_url = MONID_API_BASE_URL

    @property
    def api_key(self) -> str:
        return self._api_key or os.getenv("MONID_API_KEY", "").strip()

    @property
    def headers(self) -> Dict[str, str]:
        key = self.api_key
        return {
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json"
        }

    async def discover_tools(self, query: str, limit: int = 10, min_score: float = 0.0) -> List[Dict[str, Any]]:
        """
        Discover verified data scrapers/tools using natural language queries.
        """
        key = self.api_key
        if not key:
            logger.warning("MONID_API_KEY is not configured in environment.")
            return []

        url = f"{self.base_url}/discover"
        params = {"q": query, "l": limit}
        if min_score > 0:
            params["s"] = min_score

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.get(url, params=params, headers=self.headers)
                response.raise_for_status()
                return response.json()
        except Exception as e:
            logger.error(f"Monid discover_tools error for query '{query}': {e}")
            return []


    async def run_endpoint(
        self,
        provider: str,
        endpoint: str,
        input_data: Dict[str, Any],
        query_params: Optional[Dict[str, Any]] = None,
        path_params: Optional[Dict[str, Any]] = None,
        wait: bool = True
    ) -> Dict[str, Any]:
        """
        Execute a specific provider endpoint via Monid AI.
        """
        key = self.api_key
        if not key:
            logger.warning("MONID_API_KEY is not configured in environment.")
            return {"error": "MONID_API_KEY missing"}

        url = f"{self.base_url}/run"
        payload: Dict[str, Any] = {
            "provider": provider,
            "endpoint": endpoint,
            "input": input_data
        }
        if query_params:
            payload["queryParams"] = query_params
        if path_params:
            payload["pathParams"] = path_params

        params = {}
        if wait:
            params["wait"] = "true"

        try:
            async with httpx.AsyncClient(timeout=90.0) as client:
                response = await client.post(url, json=payload, params=params, headers=self.headers)
                if response.status_code >= 400:
                    logger.error(f"[Monid API {response.status_code}] Payload: {json.dumps(payload)} | Error Body: {response.text}")
                response.raise_for_status()
                return response.json()
        except Exception as e:
            logger.error(f"Monid run_endpoint error for '{provider}{endpoint}': {e}")
            return {"error": str(e)}





    async def fetch_social_posts(self, search_term: str, max_items: int = 15) -> List[Dict[str, Any]]:
        """
        Convenience method to search social media posts for keyword/sentence signals.
        """
        res = await self.run_endpoint(
            provider="apify",
            endpoint="/apidojo/tweet-scraper",
            input_data={
                "searchTerms": [search_term],
                "maxItems": max_items
            },
            wait=True
        )
        if isinstance(res, dict) and "output" in res:
            return res["output"]
        elif isinstance(res, list):
            return res
        return []

monid_client = MonidAIService()
