"""service.bund.de RSS fetcher"""
import asyncio
from datetime import datetime, timezone, timedelta
from typing import Optional
import feedparser
import httpx
from bs4 import BeautifulSoup
import uuid

from pipeline.normalizer import NormalizedTender, parse_date, extract_cpv_from_text
from pipeline.entity_resolution import resolve
from database import AsyncSessionLocal
from models import Source, CrawlLog
from sqlalchemy import select

BUND_RSS = "https://www.service.bund.de/IMPORTE/Ausschreibungen/aaa-bund-gesamt.feed"


def _normalize_entry(entry: dict) -> NormalizedTender:
    n = NormalizedTender()
    n.platform_name = "service.bund.de"
    n.country = "DE"

    n.title = entry.get("title", "Unbekannt")
    n.source_url = entry.get("link")
    n.external_id = entry.get("id") or n.source_url

    # Description
    raw_desc = entry.get("summary", "") or entry.get("description", "")
    soup = BeautifulSoup(raw_desc, "html.parser")
    n.description = soup.get_text(separator="\n").strip()

    # Extract authority from description
    for line in (n.description or "").split("\n"):
        if "auftraggeber" in line.lower() or "vergabestelle" in line.lower():
            n.contracting_authority = line.split(":")[-1].strip()[:200]
            break

    # CPV from text
    n.cpv_codes = extract_cpv_from_text(n.description or "")

    # Deadline from description text
    import re
    deadline_match = re.search(r"(\d{2}\.\d{2}\.\d{4})", n.description or "")
    if deadline_match:
        n.deadline = parse_date(deadline_match.group(1))

    n.publication_date = parse_date(entry.get("published"))
    n.region = "Deutschland"

    n.raw_data = {"source": "bund", "entry_id": n.external_id}
    n.finalize()
    return n


async def run_bund_rss_fetcher(source_id: uuid.UUID, since: Optional[datetime] = None):
    if not since:
        since = datetime.now(timezone.utc) - timedelta(hours=4)

    start = datetime.now(timezone.utc)
    new_count = 0
    total = 0

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(BUND_RSS)
            resp.raise_for_status()
            feed = feedparser.parse(resp.text)
    except Exception as e:
        await _log(source_id, "error", f"bund.de RSS fetch error: {e}")
        return 0

    async with AsyncSessionLocal() as db:
        for entry in feed.entries:
            try:
                normalized = _normalize_entry(entry)
                tender, is_new = await resolve(db, normalized, source_id)
                if is_new:
                    new_count += 1
                total += 1
            except Exception as e:
                await _log(source_id, "warn", f"bund.de entry error: {e}")
        await db.commit()

    duration = int((datetime.now(timezone.utc) - start).total_seconds() * 1000)
    await _log(source_id, "info", f"bund.de RSS: {total} processed, {new_count} new", total, new_count, duration)
    await _update_source(source_id, new_count)
    return new_count


async def _log(source_id, level, message, processed=0, new=0, duration=None):
    async with AsyncSessionLocal() as db:
        log = CrawlLog(source_id=source_id, level=level, message=message, entries_processed=processed, entries_new=new, duration_ms=duration)
        db.add(log)
        await db.commit()


async def _update_source(source_id: uuid.UUID, entries: int):
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Source).where(Source.id == source_id))
        source = result.scalar_one_or_none()
        if source:
            source.last_run_at = datetime.now(timezone.utc)
            source.last_run_entries = entries
            source.status = "ok"
            await db.commit()
