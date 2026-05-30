"""
Crawler für die Vergabeplattform Berlin

RSS-Feed: https://www.berlin.de/vergabeplattform/veroeffentlichungen/bekanntmachungen/
Auth:     Keine (öffentlich)

Deckt Ausschreibungen des Landes Berlin und der Berliner Bezirke ab.
"""

import re
import time
import httpx
from datetime import datetime, timezone
from bs4 import BeautifulSoup
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.database import AsyncSessionLocal
from ...models import Source, CrawlLog
from ..pipeline.normalizer import NormalizedTender, extract_cpv_codes, parse_dt, is_it_relevant
from ..pipeline.entity_resolution import resolve

_BASE = "https://www.berlin.de"
_BEKANNTMACHUNGEN_URL = f"{_BASE}/vergabeplattform/veroeffentlichungen/bekanntmachungen/"

# Mögliche RSS-Feed-URLs für Berlin.de
_RSS_CANDIDATES = [
    f"{_BEKANNTMACHUNGEN_URL}?feed=rss",
    f"{_BEKANNTMACHUNGEN_URL}?rss=1",
    f"{_BASE}/vergabeplattform/rss.xml",
    f"{_BASE}/vergabeplattform/feed/rss/",
    f"{_BASE}/rss/vergabeplattform/bekanntmachungen.rss",
    f"{_BEKANNTMACHUNGEN_URL}feed/rss/",
]

_HEADERS = {"User-Agent": "vergabe.io/1.0 (opendata@vergabe.io)"}


def _parse_item(item) -> NormalizedTender | None:
    title_tag = item.find("title")
    title = title_tag.get_text(strip=True) if title_tag else None
    if not title:
        return None

    link_tag = item.find("link")
    # RSS: text content; Atom: href attribute
    link = (link_tag.get_text(strip=True) or link_tag.get("href")) if link_tag else None

    desc_tag = item.find("description") or item.find("summary")
    raw_desc = desc_tag.get_text() if desc_tag else ""

    try:
        soup = BeautifulSoup(raw_desc, "lxml")
        description = soup.get_text(separator="\n").strip()[:2000]
    except Exception:
        description = re.sub(r"<[^>]+>", " ", raw_desc).strip()[:2000]

    combined = f"{title} {description}"
    if not is_it_relevant(combined):
        return None

    cpv_codes = extract_cpv_codes(combined)

    # Deadline aus Beschreibungstext
    deadline = None
    for pattern in [r"Angebotsfrist[:\s]+([^\n<]+)", r"Einreichungsfrist[:\s]+([^\n<]+)",
                    r"Frist[:\s]+([^\n<]+)"]:
        m = re.search(pattern, raw_desc, re.IGNORECASE)
        if m:
            deadline = parse_dt(m.group(1).strip())
            if deadline:
                break

    # Auftraggeber
    authority = None
    for pattern in [r"Auftraggeber[:\s]+(.+?)(?:\n|<)", r"Vergabestelle[:\s]+(.+?)(?:\n|<)"]:
        m = re.search(pattern, raw_desc)
        if m:
            authority = m.group(1).strip()[:300]
            break

    pub_tag = item.find("pubDate") or item.find("published") or item.find("dc:date")
    pub_date = parse_dt(pub_tag.get_text(strip=True) if pub_tag else None)

    guid_tag = item.find("guid") or item.find("id")
    external_id = guid_tag.get_text(strip=True) if guid_tag else None

    return NormalizedTender(
        title=title[:500],
        source_slug="berlin",
        external_id=external_id,
        source_url=link,
        description=description or None,
        contracting_authority=authority,
        deadline=deadline,
        publication_date=pub_date,
        cpv_codes=cpv_codes,
        region="Berlin",
        country="DE",
        platform_name="Vergabeplattform Berlin",
    )


class BerlinCrawler:
    slug = "berlin"

    async def run(self) -> int:
        async with AsyncSessionLocal() as db:
            return await self._crawl(db)

    async def _crawl(self, db: AsyncSession) -> int:
        source = (await db.execute(select(Source).where(Source.slug == self.slug))).scalar_one_or_none()
        start = time.monotonic()
        processed = new = 0

        feed_xml = await self._fetch_feed(client_headers=_HEADERS, source=source, db=db)
        if feed_xml is None:
            elapsed = int((time.monotonic() - start) * 1000)
            db.add(CrawlLog(source_id=source.id if source else None, level="warn",
                            message="Berlin: Feed nicht erreichbar — 0 processed, 0 new",
                            entries_processed=0, entries_new=0, duration_ms=elapsed))
            await db.commit()
            return 0

        feed = BeautifulSoup(feed_xml, "xml")
        for item in feed.find_all("item") + feed.find_all("entry"):
            norm = _parse_item(item)
            if not norm:
                continue
            _, is_new = await resolve(norm, db)
            processed += 1
            if is_new:
                new += 1

        await db.commit()
        elapsed = int((time.monotonic() - start) * 1000)
        if source:
            source.last_run_at = datetime.now(timezone.utc)
            source.last_run_entries = new
            source.status = "ok" if processed > 0 else source.status
        db.add(CrawlLog(
            source_id=source.id if source else None,
            level="info",
            message=f"Berlin: {processed} processed, {new} new",
            entries_processed=processed,
            entries_new=new,
            duration_ms=elapsed,
        ))
        await db.commit()
        return new

    async def _fetch_feed(self, client_headers: dict, source, db: AsyncSession) -> str | None:
        async with httpx.AsyncClient(timeout=20, headers=client_headers) as client:
            # Zuerst Haupt-Seite parsen und RSS-Link suchen
            try:
                r = await client.get(_BEKANNTMACHUNGEN_URL)
                if r.status_code == 200:
                    soup = BeautifulSoup(r.text, "lxml")
                    for tag in soup.find_all(["a", "link"]):
                        href = tag.get("href", "") or tag.get("href", "")
                        if href and ("rss" in href.lower() or "feed" in href.lower() or href.endswith(".xml")):
                            rss_url = href if href.startswith("http") else _BASE + href
                            rss_r = await client.get(rss_url)
                            if rss_r.status_code == 200 and ("<rss" in rss_r.text or "<feed" in rss_r.text):
                                return rss_r.text
            except Exception:
                pass

            # Candidate-URLs durchprobieren
            for url in _RSS_CANDIDATES:
                try:
                    r = await client.get(url)
                    if r.status_code == 200 and ("<rss" in r.text or "<feed" in r.text or "<item" in r.text):
                        return r.text
                    if r.status_code == 403:
                        break  # IP-Block, nicht weiterversuchen
                except Exception:
                    continue

        msg = (
            "Berlin RSS: Kein Feed gefunden. Geprüft: Haupt-Seite + Kandidaten-URLs. "
            "Bitte Feed-URL manuell prüfen: https://www.berlin.de/vergabeplattform/veroeffentlichungen/bekanntmachungen/"
        )
        if source:
            source.status = "warn"
            db.add(CrawlLog(source_id=source.id, level="warn", message=msg))
            await db.commit()
        return None
