"""
Crawler für die Hessische Ausschreibungsdatenbank (HAD) — had.de

HAD ist ein kostenloses öffentliches Portal seit 2007.
Enthält Ausschreibungen hessischer Behörden und Kommunen (Unter- + Oberschwelle).
Scraping der öffentlichen Ergebnisseite, da kein RSS-Feed dokumentiert.
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

_HEADERS = {"User-Agent": "vergabe.io/1.0 (opendata@vergabe.io)"}
_BASE = "https://www.had.de"

# Suchparameter: IT-relevante CPV-Kategorien + Stichwort-Suche
_SEARCH_URLS = [
    f"{_BASE}/onlinesuche/ausschreibungen-online.html?cpvcode=72",
    f"{_BASE}/onlinesuche/ausschreibungen-online.html?cpvcode=48",
    f"{_BASE}/onlinesuche/ausschreibungen-online.html?stichwort=software",
    f"{_BASE}/onlinesuche/ausschreibungen-online.html?stichwort=it+dienstleistungen",
    f"{_BASE}/onlinesuche/ausschreibungen-online.html",  # Alle (Fallback)
]


def _scrape_had(html: str) -> list[dict]:
    """Parst HAD-Suchergebnisseite."""
    soup = BeautifulSoup(html, "lxml")
    items = []

    rows = (
        soup.find_all("tr", class_=re.compile(r"result|ausschreib|tender", re.I)) or
        soup.find_all("div", class_=re.compile(r"result|ausschreib|tender|item", re.I)) or
        soup.find_all("article")
    )

    # Fallback: Links die auf Detailseiten zeigen
    if not rows:
        for a in soup.find_all("a", href=re.compile(r"(detail|ausschreibung|bekanntmachung|id=)", re.I)):
            title = a.get_text(strip=True)
            if len(title) < 10:
                continue
            href = a.get("href", "")
            url = href if href.startswith("http") else _BASE + href
            items.append({"title": title, "url": url, "text": title})
        return items

    for row in rows[:100]:
        link = row.find("a")
        title = link.get_text(strip=True) if link else row.get_text(strip=True)[:150]
        if not title or len(title) < 5:
            continue
        href = link.get("href", "") if link else ""
        url = href if href.startswith("http") else (_BASE + href if href else None)
        text = row.get_text(separator=" ").strip()
        items.append({"title": title, "url": url, "text": text})

    return items


class HadCrawler:
    slug = "had"

    async def run(self) -> int:
        async with AsyncSessionLocal() as db:
            return await self._crawl(db)

    async def _crawl(self, db: AsyncSession) -> int:
        source = (await db.execute(select(Source).where(Source.slug == self.slug))).scalar_one_or_none()
        start = time.monotonic()
        processed = new = 0
        seen_titles: set[str] = set()
        found = False

        requests_log: list[dict] = []
        total_scraped = 0
        filtered = 0

        ip_blocked = False
        async with httpx.AsyncClient(timeout=20, headers=_HEADERS, follow_redirects=True) as client:
            for url in _SEARCH_URLS:
                t0 = time.monotonic()
                try:
                    r = await client.get(url)
                    ms = int((time.monotonic() - t0) * 1000)
                    entry: dict = {"url": url, "http_status": r.status_code, "ms": ms}
                    requests_log.append(entry)

                    if r.status_code == 403:
                        ip_blocked = True
                        if source:
                            source.status = "warn"
                            db.add(CrawlLog(
                                source_id=source.id, level="warn",
                                message="HAD: Zugriff verweigert (403) — Server-IP blockiert",
                                details={"requests": requests_log},
                            ))
                            await db.commit()
                        break
                    if r.status_code != 200 or len(r.text) < 500:
                        entry["note"] = f"übersprungen (len={len(r.text)})"
                        continue

                    items = _scrape_had(r.text)
                    entry["items_scraped"] = len(items)
                    if not items:
                        continue

                    found = True
                    total_scraped += len(items)
                    for item in items:
                        combined = f"{item['title']} {item.get('text', '')}"
                        if not is_it_relevant(combined):
                            filtered += 1
                            continue
                        key = item["title"][:100]
                        if key in seen_titles:
                            continue
                        seen_titles.add(key)

                        cpv = extract_cpv_codes(combined)
                        deadline_m = re.search(r"(\d{2}\.\d{2}\.\d{4})", item.get("text", ""))
                        deadline = parse_dt(deadline_m.group(1) if deadline_m else None)
                        auth_m = re.search(r"(?:Auftraggeber|Vergabestelle)[:\s]+([^\n]+)", item.get("text", ""))
                        authority = auth_m.group(1).strip()[:300] if auth_m else None

                        norm = NormalizedTender(
                            title=item["title"][:500],
                            source_slug=self.slug,
                            source_url=item.get("url"),
                            description=item.get("text", "")[:2000] or None,
                            contracting_authority=authority,
                            deadline=deadline,
                            cpv_codes=cpv,
                            region="Hessen",
                            country="DE",
                            platform_name="HAD Hessen",
                        )
                        _, is_new = await resolve(norm, db)
                        processed += 1
                        if is_new:
                            new += 1

                    await db.commit()

                except Exception as exc:
                    ms = int((time.monotonic() - t0) * 1000)
                    requests_log.append({"url": url, "ms": ms, "error": type(exc).__name__})
                    continue

        if not found and not ip_blocked:
            if source:
                source.status = "warn"
                db.add(CrawlLog(
                    source_id=source.id, level="warn",
                    message="HAD: Kein erreichbarer Endpunkt — bitte https://www.had.de manuell prüfen",
                    details={"requests": requests_log},
                ))
                await db.commit()

        elapsed = int((time.monotonic() - start) * 1000)
        if source:
            source.last_run_at = datetime.now(timezone.utc)
            source.last_run_entries = new
            if found:
                source.status = "ok"
        db.add(CrawlLog(
            source_id=source.id if source else None,
            level="info",
            message=f"HAD Hessen: {processed} processed, {new} new",
            entries_processed=processed,
            entries_new=new,
            duration_ms=elapsed,
            details={
                "scraped": total_scraped,
                "filtered": filtered,
                "requests": requests_log,
            },
        ))
        await db.commit()
        return new
