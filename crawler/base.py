"""Base scraper — all platform scrapers inherit from this."""
import asyncio
import random
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import List, Optional
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

USER_AGENTS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
]


class BaseScraper(ABC):
    def __init__(self, source_id, source_name: str):
        self.source_id = source_id
        self.source_name = source_name
        self.user_agent = random.choice(USER_AGENTS)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=20))
    async def _get(self, client: httpx.AsyncClient, url: str, **kwargs) -> httpx.Response:
        await asyncio.sleep(random.uniform(0.5, 2.0))
        headers = {"User-Agent": self.user_agent, **kwargs.pop("headers", {})}
        return await client.get(url, headers=headers, timeout=30, **kwargs)

    @abstractmethod
    async def run(self, since: Optional[datetime] = None) -> int:
        """Run the scraper. Returns count of new entries."""
        ...
