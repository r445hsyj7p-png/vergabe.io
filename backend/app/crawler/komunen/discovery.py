import asyncio
import re
from datetime import datetime, timezone
from urllib.parse import urljoin, urlparse
import httpx
from bs4 import BeautifulSoup
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from ...models import KomunenSource

VERGABE_KEYWORDS = ["vergabe", "ausschreibung", "beschaffung", "einkauf", "submission"]
CONCURRENCY = 10


def _score_url(url: str, text: str) -> float:
    url_lower = url.lower()
    if "/vergabe/" in url_lower or "/ausschreibung/" in url_lower:
        return 1.0
    if "/vergabe" in url_lower or "/ausschreibung" in url_lower:
        return 0.9
    if any(kw in text.lower() for kw in VERGABE_KEYWORDS):
        return 0.8
    if any(kw in url_lower for kw in VERGABE_KEYWORDS):
        return 0.6
    return 0.0


async def _discover_vergabe_url(main_url: str, client: httpx.AsyncClient) -> tuple[str | None, float]:
    try:
        r = await client.get(main_url, timeout=10, follow_redirects=True)
        soup = BeautifulSoup(r.text, "lxml")
        best_url, best_score = None, 0.0
        for a in soup.find_all("a", href=True):
            href = a["href"]
            full = urljoin(main_url, href)
            if not full.startswith("http"):
                continue
            score = _score_url(full, a.get_text())
            if score > best_score:
                best_score = score
                best_url = full
        return best_url, best_score
    except Exception:
        return None, 0.0


async def run_discovery_pipeline(db: AsyncSession) -> dict:
    # Verify existing main_urls
    to_verify = (await db.execute(
        select(KomunenSource).where(KomunenSource.main_url.isnot(None), KomunenSource.vergabe_url.is_(None))
        .limit(200)
    )).scalars().all()

    discovered = 0
    sem = asyncio.Semaphore(CONCURRENCY)

    async def process(k: KomunenSource, client: httpx.AsyncClient):
        async with sem:
            url, score = await _discover_vergabe_url(k.main_url, client)
            if url and score >= 0.6:
                k.vergabe_url = url
                k.discovery_confidence = score
                k.status = "verified" if score >= 0.9 else "pending_review"
                k.last_verified_at = datetime.now(timezone.utc)
                return 1
            return 0

    async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
        tasks = [process(k, client) for k in to_verify]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        discovered = sum(r for r in results if isinstance(r, int))

    await db.commit()
    return {"discovered": discovered, "checked": len(to_verify)}
