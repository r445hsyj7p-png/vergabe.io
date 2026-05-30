"""
Crawler für den Vergabemarktplatz NRW (vergabe.NRW)

REST API: https://daten.vergabe.nrw.de/rest/evergabe
Doku:     https://open.nrw/sites/default/files/opendatafiles/daten-vergabe-nrw-de-Dokumentation-v1.pdf
Auth:     Keine (Open Data)

Deckt Ausschreibungen aller Schwellenwerte in NRW ab (Unter- und Oberschwelle).
"""

import asyncio
import time
import httpx
from datetime import datetime, timezone, timedelta
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.database import AsyncSessionLocal
from ...models import Source, CrawlLog
from ..pipeline.normalizer import NormalizedTender, extract_cpv_codes, parse_dt, is_it_relevant
from ..pipeline.entity_resolution import resolve

API_BASE = "https://daten.vergabe.nrw.de/rest/evergabe"
PAGE_SIZE = 50
MAX_PAGES = 40
SLEEP_S = 1.0

_HEADERS = {
    "User-Agent": "vergabe.io/1.0 (opendata@vergabe.io)",
    "Accept": "application/json",
}

# IT-relevante CPV-Präfixe
# Mögliche Feldnamen in der API-Antwort (NRW-Datenbank nutzt deutsche Feldnamen)
_FIELD_TITLE = ("titel", "bezeichnung", "betreff", "title", "beschreibung_kurz")
_FIELD_AUTHORITY = ("auftraggeber", "vergabestelle", "auftraggeber_name", "contracting_authority")
_FIELD_DEADLINE = ("angebotsfrist", "einreichungsfrist", "frist", "deadline", "submission_deadline")
_FIELD_PUBDATE = ("veroeffentlichungsdatum", "bekanntmachungsdatum", "datum", "publication_date", "published_at")
_FIELD_CPV = ("cpv_code", "cpv", "cpvCode", "cpv_codes", "klassifikation")
_FIELD_VALUE = ("auftragswert", "auftragswert_von", "value", "estimated_value", "schätzwert")
_FIELD_ID = ("id", "notice_id", "vergabe_id", "ausschreibungs_id", "noticeId")
_FIELD_URL = ("url", "link", "detail_url", "bekanntmachungs_url")


def _get(d: dict, *keys) -> str | None:
    for k in keys:
        v = d.get(k)
        if v is not None:
            return str(v) if not isinstance(v, str) else v
    return None


def _parse_item(item: dict) -> NormalizedTender | None:
    title = _get(item, *_FIELD_TITLE)
    if not title:
        return None

    raw_cpv = _get(item, *_FIELD_CPV) or ""
    cpv_codes = extract_cpv_codes(raw_cpv) if raw_cpv else []
    # Fallback: CPV aus gesamtem Item-JSON
    if not cpv_codes:
        cpv_codes = extract_cpv_codes(str(item))

    if not is_it_relevant(cpv_codes):
        return None

    notice_id = _get(item, *_FIELD_ID)
    url_raw = _get(item, *_FIELD_URL)
    source_url = url_raw or (f"https://www.vergabe.nrw.de/ausschreibung/{notice_id}" if notice_id else None)

    desc = _get(item, "beschreibung", "leistungsbeschreibung", "description", "text")

    authority = _get(item, *_FIELD_AUTHORITY)
    deadline = parse_dt(_get(item, *_FIELD_DEADLINE))
    pub_date = parse_dt(_get(item, *_FIELD_PUBDATE))

    value_raw = _get(item, *_FIELD_VALUE)
    value_max = None
    if value_raw:
        try:
            value_max = int(float(str(value_raw).replace(",", ".")) * 100)
        except (ValueError, TypeError):
            pass

    region = _get(item, "ort", "stadt", "region", "bundesland") or "Nordrhein-Westfalen"

    return NormalizedTender(
        title=title[:500],
        source_slug="nrw",
        external_id=notice_id,
        source_url=source_url,
        description=str(desc)[:2000] if desc else None,
        contracting_authority=str(authority)[:300] if authority else None,
        deadline=deadline,
        publication_date=pub_date,
        value_max=value_max,
        cpv_codes=cpv_codes,
        region=region[:100] if region else None,
        country="DE",
        platform_name="vergabe.NRW",
        raw_data={"id": notice_id},
    )


class NrwCrawler:
    slug = "nrw"

    async def run(self) -> int:
        async with AsyncSessionLocal() as db:
            return await self._crawl(db)

    async def _crawl(self, db: AsyncSession) -> int:
        source = (await db.execute(select(Source).where(Source.slug == self.slug))).scalar_one_or_none()
        start = time.monotonic()
        processed = new = 0

        # Letzte 3 Tage — NRW aktualisiert täglich
        date_from = (datetime.now(timezone.utc) - timedelta(days=3)).strftime("%Y-%m-%d")

        async with httpx.AsyncClient(timeout=30, headers=_HEADERS) as client:
            for page in range(0, MAX_PAGES):  # Spring Data beginnt bei page=0
                try:
                    r = await client.get(
                        API_BASE,
                        params={
                            "page": page,
                            "size": PAGE_SIZE,
                            "sort": "veroeffentlichungsdatum,desc",
                            "filter[veroeffentlichungsdatum][$gte]": date_from,
                        },
                    )
                    if r.status_code == 403:
                        msg = "NRW API: Zugriff verweigert (403) — Server-IP blockiert"
                        if source:
                            source.status = "warn"
                            db.add(CrawlLog(source_id=source.id, level="warn", message=msg))
                            await db.commit()
                        break
                    r.raise_for_status()
                    data = r.json()
                except httpx.HTTPStatusError as e:
                    if source:
                        db.add(CrawlLog(source_id=source.id, level="warn",
                                        message=f"NRW API HTTP {e.response.status_code} auf Seite {page}"))
                        await db.commit()
                    break
                except Exception as e:
                    if source:
                        db.add(CrawlLog(source_id=source.id, level="error",
                                        message=f"NRW API Fehler: {e}"))
                        await db.commit()
                    break

                # Spring Data REST Paginierung: _embedded.* oder content oder items
                items: list = []
                if "_embedded" in data:
                    for v in data["_embedded"].values():
                        if isinstance(v, list):
                            items = v
                            break
                elif "content" in data:
                    items = data["content"]
                elif isinstance(data, list):
                    items = data
                else:
                    items = data.get("items") or data.get("results") or data.get("data") or []

                if not items:
                    break

                for item in items:
                    norm = _parse_item(item)
                    if not norm:
                        continue
                    _, is_new = await resolve(norm, db)
                    processed += 1
                    if is_new:
                        new += 1

                await db.commit()

                # Pagination: Spring Data Page-Objekt
                page_meta = data.get("page") or {}
                total_pages = page_meta.get("totalPages") or data.get("totalPages")
                if total_pages and page >= int(total_pages) - 1:
                    break
                if len(items) < PAGE_SIZE:
                    break

                await asyncio.sleep(SLEEP_S)

        elapsed = int((time.monotonic() - start) * 1000)
        if source:
            source.last_run_at = datetime.now(timezone.utc)
            source.last_run_entries = new
            source.status = "ok" if processed > 0 else source.status
        db.add(CrawlLog(
            source_id=source.id if source else None,
            level="info",
            message=f"NRW: {processed} processed, {new} new",
            entries_processed=processed,
            entries_new=new,
            duration_ms=elapsed,
        ))
        await db.commit()
        return new
