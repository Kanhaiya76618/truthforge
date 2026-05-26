"""
Bright Data API Client — shared module for all engines.
Handles SERP API, Web Unlocker, and Scraper API calls.
"""

import os
import httpx
from typing import Optional
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_exponential


class BrightDataClient:
    """Unified client for all Bright Data services."""

    def __init__(self):
        self.api_key = os.getenv("BRIGHT_DATA_API_KEY")
        self.serp_url = os.getenv("BRIGHT_DATA_SERP_URL", "https://api.brightdata.com/request")
        self.unlocker_url = os.getenv("BRIGHT_DATA_UNLOCKER_URL", "https://api.brightdata.com/request")
        self.zone_serp = os.getenv("BRIGHT_DATA_ZONE_SERP", "serp_api1")
        self.zone_unlocker = os.getenv("BRIGHT_DATA_ZONE_UNLOCKER", "web_unlocker1")

        if not self.api_key:
            raise ValueError("BRIGHT_DATA_API_KEY not found in environment")

    @retry(stop=stop_after_attempt(2), wait=wait_exponential(multiplier=1, min=2, max=6))
    async def search_serp(self, query: str, engine: str = "google") -> str:
        """
        Search Google/Bing via Bright Data SERP API.
        Returns raw HTML results.
        """
        search_url = f"https://www.google.com/search?q={query.replace(' ', '+')}"

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "zone": self.zone_serp,
            "url": search_url,
            "format": "raw",
        }

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.post(self.serp_url, headers=headers, json=payload)
                response.raise_for_status()
                logger.info(f"SERP search complete: '{query}' ({len(response.text)} chars)")
                return response.text
        except Exception as e:
            logger.error(f"SERP API error for '{query}': {e}")
            raise

    @retry(stop=stop_after_attempt(1), wait=wait_exponential(multiplier=1, min=2, max=4))
    async def unlock_url(self, url: str) -> str:
        """
        Fetch any URL via Bright Data Web Unlocker.
        Bypasses bot detection, CAPTCHAs, and geo-blocks.
        """
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "zone": self.zone_unlocker,
            "url": url,
            "format": "raw",
        }

        try:
            async with httpx.AsyncClient(timeout=8.0) as client:
                response = await client.post(self.unlocker_url, headers=headers, json=payload)
                response.raise_for_status()
                logger.info(f"Web Unlocker fetched: {url} ({len(response.text)} chars)")
                return response.text
        except Exception as e:
            logger.error(f"Web Unlocker error for {url}: {e}")
            raise

    async def search_news(self, company_name: str, keywords: Optional[str] = None) -> str:
        """Search for company news."""
        query = f"{company_name} news"
        if keywords:
            query += f" {keywords}"
        return await self.search_serp(query)

    async def search_funding(self, company_name: str) -> str:
        """Search for funding/fundraising signals."""
        query = f"{company_name} funding round investment Series"
        return await self.search_serp(query)

    async def search_hiring(self, company_name: str) -> str:
        """Search for hiring/job signals."""
        query = f"{company_name} hiring jobs careers"
        return await self.search_serp(query)

    async def search_executive(self, company_name: str) -> str:
        """Search for executive changes."""
        query = f"{company_name} CEO CFO appointed new hire"
        return await self.search_serp(query)

    async def search_esg(self, company_name: str) -> str:
        """Search for ESG/sustainability claims."""
        query = f"{company_name} ESG sustainability carbon neutral report"
        return await self.search_serp(query)


bright_data = BrightDataClient()