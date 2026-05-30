"""
Crawler für eVergabe Sachsen (evergabe.sachsen.de / sachsen-vergabe.de)

Nutzt das öffentliche Bekanntmachungsverzeichnis der NetServer-Plattform.
NetServer ist eine weitverbreitete eVergabe-Software (cosinex), deren
öffentliche Bekanntmachungslisten ohne Auth zugänglich sind.
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
from ..pipeline.normalizer import NormalizedTender, extract_cpv_codes
from ..pipeline.entity_resolution import resolve

_HEADERS = {"User-Agent": "vergabe.io/1.0 (opendata@vergabe.io)"}

# NetServer-Instanzen für Sachsen (absteigende Priorität)
_NETSERVER_BASES = [
    "https://www.evergabe.sachsen.de",
    "https://sachsen-vergabe.de",
    "https://vergabe.sachsen.de",
]

# Öffentliche Bekanntmachungs-Pfade auf NetServer-Plattformen
_PUB_PATHS = [
    "/NetServer/publicationOverview.html",
    "/NetServer/TenderingProcedureService",
    "/bekanntmachungen",
    "/ausschreibungen",
]

_IT_CPV = ("72", "48", "73", "64", "79")
_IT_KW = ["software", "it-", " it ", "edv", "digital", "cloud", "cyber",
           "sicherheit", "infrastruktur", "entwicklung", "netzwerk", "server", "hosting"]


def _is_it(text: str) -> bool:
    cpv = extract_cpv_codes(text)
    if any(c.startswith(p) for c in cpv for p in _IT_CPV):
        return True
    low = text.lower()
    return any(k in low for k in _IT_KW)


def _parse_dt(s: str | None) -> datetime | None:
    if not s:
        return None
    for fmt in ("%Y-%m-%dT%H:%M:%SZ", "%d.%m.%Y %H:%M", "%d.%m.%Y", "%Y-%m-%d"):
        try:
            dt = datetime.strptime(s.strip(), fmt)
            return dt.replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def _scrape_netserver_html(html: str, base_url: str) -> list[NormalizedTender]:
    """Parst eine NetServer-Bekanntmachungsübersicht."""
    soup = BeautifulSoup(html, "lxml")
    results = []

    # NetServer listet Ausschreibungen in Tabellen oder <article>/<li> Elementen
    rows = (
        soup.find_all("tr", class_=re.compile(r"tender|ausschreib|result", re.I)) or
        soup.find_all("article") or
        soup.find_all("li", class_=re.compile(r"tender|ausschreib|vergabe", re.I))
    )

    # Fallback: alle Links die wie Tender-Detail-URLs aussehen
    if not rows:
        links = soup.find_all("a", href=re.compile(r"(detail|tender|vergabe|bekanntmachung)", re.I))
        for link in links[:50]:
            title = link.get_text(strip=True)
            href = link.get("href", "")
            if not title or len(title) < 10:
                continue
            url = href if href.startswith("http") else base_url + href
            combined = title
            if not _is_it(combined):
                continue
            results.append(NormalizedTender(
                title=title[:500],
                source_slug="sachsen",
                source_url=url,
                cpv_codes=extract_cpv_codes(title),
                region="Sachsen",
                country="DE",
                platform_name="eVergabe Sachsen",
            ))
        return results

    for row in rows[:50]:
        cells = row.find_all(["td", "dd", "span"])
        text = " ".join(c.get_text(strip=True) for c in cells)
        title_tag = row.find(["a", "h3", "h4", "strong"])
        title = title_tag.get_text(strip=True) if title_tag else text[:100]
        if not title or len(title) < 5:
            continue
        combined = f"{title} {text}"
        if not _is_it(combined):
            continue
        link = title_tag.get("href", "") if title_tag and title_tag.name == "a" else ""
        url = link if link.startswith("http") else (base_url + link if link else None)
        cpv = extract_cpv_codes(combined)
        deadline_m = re.search(r"(\d{2}\.\d{2}\.\d{4})", text)
        deadline = _parse_dt(deadline_m.group(1) if deadline_m else None)
        results.append(NormalizedTender(
            title=title[:500],
            source_slug="sachsen",
            source_url=url,
            description=text[:2000],
            deadline=deadline,
            cpv_codes=cpv,
            region="Sachsen",
            country="DE",
            platform_name="eVergabe Sachsen",
        ))
    return results


class SachsenCrawler:
    slug = "sachsen"

    async def run(self) -> int:
        async with AsyncSessionLocal() as db:
            return await self._crawl(db)

    async def _crawl(self, db: AsyncSession) -> int:
        source = (await db.execute(select(Source).where(Source.slug == self.slug))).scalar_one_or_none()
        start = time.monotonic()
        processed = new = 0
        found = False

        async with httpx.AsyncClient(timeout=20, headers=_HEADERS, follow_redirects=True) as client:
            for base in _NETSERVER_BASES:
                for path in _PUB_PATHS:
                    try:
                        r = await client.get(f"{base}{path}")
                        if r.status_code == 403:
                            msg = f"Sachsen: Zugriff verweigert (403) auf {base}{path}"
                            if source:
                                source.status = "warn"
                                db.add(CrawlLog(source_id=source.id, level="warn", message=msg))
                                await db.commit()
                            break
                        if r.status_code != 200:
                            continue
                        if len(r.text) < 500:
                            continue

                        tenders = _scrape_netserver_html(r.text, base)
                        if not tenders:
                            continue

                        found = True
                        for norm in tenders:
                            _, is_new = await resolve(norm, db)
                            processed += 1
                            if is_new:
                                new += 1
                        await db.commit()
                        break
                    except Exception:
                        continue
                if found:
                    break

        if not found and not source:
            pass
        elif not found:
            msg = "Sachsen: Kein erreichbarer NetServer-Endpunkt — IP evtl. blockiert"
            if source:
                source.status = "warn"
                db.add(CrawlLog(source_id=source.id, level="warn", message=msg))
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
            message=f"Sachsen: {processed} processed, {new} new",
            entries_processed=processed,
            entries_new=new,
            duration_ms=elapsed,
        ))
        await db.commit()
        return new
