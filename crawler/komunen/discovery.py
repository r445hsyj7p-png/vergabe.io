"""
Kommunen-Discovery (Option B)
- Loads seed list from DB (imported from Destatis)
- Verifies URLs via HTTP HEAD
- Discovers vergabe URLs via sitemap + link crawling
- Stores results in komunen_sources
"""
import asyncio
import re
from datetime import datetime, timezone
from typing import Optional, List
import httpx
from bs4 import BeautifulSoup

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

from database import AsyncSessionLocal
from models import KomunenSource, CrawlLog
from sqlalchemy import select, and_

VERGABE_KEYWORDS = ['vergabe', 'ausschreibung', 'bekanntmachung', 'submission', 'tender', 'auftrag', 'beschaffung']
MAX_DEPTH = 2
MAX_LINKS = 150
CONCURRENCY = 30


def _has_vergabe_keyword(url: str, text: str) -> bool:
    combined = (url + ' ' + text).lower()
    return any(kw in combined for kw in VERGABE_KEYWORDS)


def _score_url(url: str, link_text: str) -> float:
    url_l = url.lower()
    text_l = link_text.lower()
    score = 0.0
    if '/vergabe/' in url_l or '/ausschreibung/' in url_l:
        score = 1.0
    elif '/vergabe' in url_l or '/ausschreibung' in url_l:
        score = 0.9
    elif 'ausschreibung' in text_l or 'vergabe' in text_l:
        score = 0.8
    elif any(kw in url_l for kw in VERGABE_KEYWORDS):
        score = 0.6
    return score


async def verify_url(client: httpx.AsyncClient, url: str) -> bool:
    try:
        r = await client.head(url, timeout=10, follow_redirects=True)
        return r.status_code < 400
    except Exception:
        return False


async def discover_vergabe_url(client: httpx.AsyncClient, base_url: str) -> tuple[Optional[str], float]:
    """Returns (vergabe_url, confidence_score)"""
    # Try sitemap first
    try:
        r = await client.get(f"{base_url.rstrip('/')}/sitemap.xml", timeout=10, follow_redirects=True)
        if r.status_code == 200:
            soup = BeautifulSoup(r.text, 'lxml-xml')
            for loc in soup.find_all('loc'):
                url = loc.text.strip()
                score = _score_url(url, '')
                if score >= 0.8:
                    return url, score
    except Exception:
        pass

    # Crawl homepage links (depth 1)
    try:
        r = await client.get(base_url, timeout=10, follow_redirects=True)
        if r.status_code != 200:
            return None, 0.0
        soup = BeautifulSoup(r.text, 'html.parser')
        best_url, best_score = None, 0.0
        for a in soup.find_all('a', href=True)[:MAX_LINKS]:
            href = a.get('href', '').strip()
            if not href or href.startswith('mailto:') or href.startswith('#'):
                continue
            if href.startswith('/'):
                href = base_url.rstrip('/') + href
            elif not href.startswith('http'):
                continue
            text = a.get_text(strip=True)
            score = _score_url(href, text)
            if score > best_score:
                best_score = score
                best_url = href
        return best_url, best_score
    except Exception:
        return None, 0.0


async def run_url_verify_job():
    """Verify all unverified komunen sources."""
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(KomunenSource).where(
                and_(KomunenSource.main_url.isnot(None), KomunenSource.last_verified_at.is_(None))
            ).limit(200)
        )
        sources = result.scalars().all()

    sem = asyncio.Semaphore(CONCURRENCY)
    async def verify_one(k: KomunenSource):
        async with sem:
            async with httpx.AsyncClient(follow_redirects=True, timeout=10) as client:
                ok = await verify_url(client, k.main_url)
                async with AsyncSessionLocal() as db:
                    result = await db.execute(select(KomunenSource).where(KomunenSource.id == k.id))
                    source = result.scalar_one_or_none()
                    if source:
                        source.last_verified_at = datetime.now(timezone.utc)
                        if not ok:
                            source.status = 'pending_review'
                        await db.commit()

    await asyncio.gather(*[verify_one(k) for k in sources])
    print(f"[KomunenVerify] {len(sources)} URLs verified")


async def run_discovery_job():
    """Discover vergabe URLs for verified komunen sources."""
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(KomunenSource).where(
                and_(
                    KomunenSource.main_url.isnot(None),
                    KomunenSource.vergabe_url.is_(None),
                    KomunenSource.status != 'excluded',
                )
            ).limit(100)
        )
        sources = result.scalars().all()

    sem = asyncio.Semaphore(10)
    discovered = 0

    async def discover_one(k: KomunenSource):
        nonlocal discovered
        async with sem:
            async with httpx.AsyncClient(follow_redirects=True, timeout=15) as client:
                url, score = await discover_vergabe_url(client, k.main_url)
                async with AsyncSessionLocal() as db:
                    result = await db.execute(select(KomunenSource).where(KomunenSource.id == k.id))
                    source = result.scalar_one_or_none()
                    if source and url:
                        source.vergabe_url = url
                        source.discovery_confidence = score
                        source.status = 'pending_review' if score < 0.7 else 'auto'
                        await db.commit()
                        discovered += 1

    await asyncio.gather(*[discover_one(k) for k in sources])

    async with AsyncSessionLocal() as db:
        log = CrawlLog(level='info', message=f'Komunen discovery: {discovered}/{len(sources)} vergabe URLs found')
        db.add(log)
        await db.commit()

    print(f"[KomunenDiscovery] {discovered}/{len(sources)} URLs discovered")


async def run_maintenance_job():
    """Re-verify URLs that returned 404 recently."""
    from datetime import timedelta
    cutoff = datetime.now(timezone.utc) - timedelta(days=7)
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(KomunenSource).where(
                and_(KomunenSource.status == 'pending_review', KomunenSource.last_verified_at < cutoff)
            ).limit(50)
        )
        sources = result.scalars().all()

    for k in sources:
        async with httpx.AsyncClient(follow_redirects=True, timeout=10) as client:
            ok = await verify_url(client, k.main_url or '')
        async with AsyncSessionLocal() as db:
            result = await db.execute(select(KomunenSource).where(KomunenSource.id == k.id))
            source = result.scalar_one_or_none()
            if source:
                source.last_verified_at = datetime.now(timezone.utc)
                if ok:
                    source.status = 'auto'
                    source.vergabe_url = None  # re-discover
                await db.commit()

    print(f"[KomunenMaintenance] {len(sources)} sources re-checked")


if __name__ == "__main__":
    asyncio.run(run_discovery_job())
