"""
Crawler für TED (Tenders Electronic Daily) — EU-Vergabebekanntmachungen

API: POST https://api.ted.europa.eu/v3/notices/search
Doku: https://docs.ted.europa.eu/api/latest/search.html
Auth: Keine (kein API-Key erforderlich für Basisabfragen)

TED v3 nutzt eine POST-basierte Expert-Search-Abfrage.
Die Feldbezeichnung für CPV-Codes ist "classification-cpv".
"""

import asyncio
import time
import httpx
from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.database import AsyncSessionLocal
from ...models import Source, CrawlLog
from ..pipeline.normalizer import NormalizedTender, parse_dt
from ..pipeline.entity_resolution import resolve

API_BASE = "https://api.ted.europa.eu/v3"
PAGE_SIZE = 50
MAX_PAGES = 20
SLEEP_S = 1.0

# TED v3 Expert-Search-Syntax mit Lucene-Range für IT-CPV-Divisionen.
# TED speichert CPV als 8-stellige Ganzzahl; IN(72) = kein Match, Range erforderlich.
# 72xxxxxxx = IT-Dienstleistungen, 48xxxxxxx = Software, 73xxxxxxx = F&E
_SEARCH_QUERY = (
    "classification-cpv:[72000000 TO 72999999]"
    " OR classification-cpv:[48000000 TO 48999999]"
    " OR classification-cpv:[73000000 TO 73999999]"
)

# Fallback-Feldnamen für verschiedene TED-API-Versionen (v2 vs v3)
_FIELD_ID = ("publication-number", "noticeId", "notice-id", "id")
_FIELD_TITLE = ("title",)
_FIELD_DESC = ("description",)
_FIELD_BUYER = ("buyer",)
_FIELD_CPV = ("cpv", "cpvCodes", "cpv-codes")
_FIELD_VALUE = ("estimated-value", "estimatedTotalValue", "estimated-total-value")
_FIELD_DEADLINE = ("submission-deadline-date", "submissionDeadlineDate")
_FIELD_PUBDATE = ("publication-date", "publicationDate")
_FIELD_PROC = ("procedure-type", "procedureType")
_FIELD_LOTS = ("lots",)


def _prefer_lang(obj: dict | None, langs=("DEU", "ENG", "FRA")) -> str | None:
    if not obj:
        return None
    if isinstance(obj, str):
        return obj
    for lang in langs:
        if val := obj.get(lang):
            return val
    return next(iter(obj.values()), None) if obj else None


def _get(d: dict, *keys):
    for k in keys:
        v = d.get(k)
        if v is not None:
            return v
    return None


class TedCrawler:
    slug = "ted"

    async def run(self) -> int:
        async with AsyncSessionLocal() as db:
            return await self._crawl(db)

    async def _crawl(self, db: AsyncSession) -> int:
        source = (await db.execute(select(Source).where(Source.slug == self.slug))).scalar_one_or_none()
        start = time.monotonic()
        processed = new = 0
        consecutive_errors = 0

        requests_log: list[dict] = []
        total_fetched = 0
        total_parse_errors = 0
        pages_done = 0

        async with httpx.AsyncClient(timeout=30) as client:
            for page in range(1, MAX_PAGES + 1):
                req_t0 = time.monotonic()
                try:
                    r = await client.post(
                        f"{API_BASE}/notices/search",
                        json={
                            "query": _SEARCH_QUERY,
                            "page": page,
                            "limit": PAGE_SIZE,
                        },
                        headers={"Content-Type": "application/json", "Accept": "application/json"},
                    )
                    req_ms = int((time.monotonic() - req_t0) * 1000)
                    r.raise_for_status()
                    data = r.json()
                    notices = data.get("notices") or data.get("items") or data.get("results") or []
                    requests_log.append({
                        "page": page, "status": r.status_code, "ms": req_ms,
                        "notices_in_response": len(notices),
                        "api_total": data.get("total", data.get("totalNotices", data.get("totalElements"))),
                    })
                except Exception as e:
                    req_ms = int((time.monotonic() - req_t0) * 1000)
                    requests_log.append({
                        "page": page, "status": getattr(getattr(e, "response", None), "status_code", None),
                        "ms": req_ms, "error": type(e).__name__,
                    })
                    consecutive_errors += 1
                    if consecutive_errors >= 3:
                        if source:
                            source.status = "error"
                        break
                    await asyncio.sleep(2 ** consecutive_errors)
                    continue

                consecutive_errors = 0
                pages_done += 1

                if page == 1 and not notices:
                    api_total = data.get("total", data.get("totalNotices", data.get("totalElements", "unbekannt")))
                    if source:
                        source.status = "warn"
                        db.add(CrawlLog(
                            source_id=source.id, level="warn",
                            message=f"TED: Seite 1 leer (API meldet {api_total} Treffer) — Query prüfen: {_SEARCH_QUERY}",
                            details={"requests": requests_log, "api_total": api_total},
                        ))
                        await db.commit()
                    break

                total_fetched += len(notices)
                page_parsed = 0
                for notice in notices:
                    norm = self._parse(notice)
                    if not norm:
                        total_parse_errors += 1
                        continue
                    _, is_new = await resolve(norm, db)
                    processed += 1
                    page_parsed += 1
                    if is_new:
                        new += 1

                # Wenn alle Notices auf Seite 1 nicht parsbar: Strukturfehler loggen
                if notices and page_parsed == 0 and page == 1:
                    sample_keys = list(notices[0].keys())[:15] if notices else []
                    if source:
                        source.status = "warn"
                        db.add(CrawlLog(
                            source_id=source.id, level="warn",
                            message=f"TED: {len(notices)} Notices erhalten, keines parsbar — Antwortstruktur prüfen",
                            details={"requests": requests_log, "sample_keys": sample_keys,
                                     "sample_title_field": notices[0].get("title") if notices else None},
                        ))
                        await db.commit()
                    break

                await db.commit()
                if len(notices) < PAGE_SIZE:
                    break
                await asyncio.sleep(SLEEP_S)

        elapsed = int((time.monotonic() - start) * 1000)
        level = "warn" if (source and source.status == "warn") else "info"
        db.add(CrawlLog(
            source_id=source.id if source else None,
            level=level,
            message=f"TED crawl: {processed} processed, {new} new",
            entries_processed=processed,
            entries_new=new,
            duration_ms=elapsed,
            details={
                "pages": pages_done,
                "fetched": total_fetched,
                "parse_errors": total_parse_errors,
                "requests": requests_log,
            },
        ))
        if source:
            source.last_run_at = datetime.now(timezone.utc)
            source.last_run_entries = new
            if source.status != "warn":
                source.status = "ok"
        await db.commit()
        return new

    def _parse(self, notice: dict) -> NormalizedTender | None:
        title_raw = _get(notice, *_FIELD_TITLE)
        title = _prefer_lang(title_raw)
        if not title:
            return None

        buyer = _get(notice, *_FIELD_BUYER) or {}
        if isinstance(buyer, list):
            buyer = buyer[0] if buyer else {}
        authority = _prefer_lang(buyer.get("officialName")) or _prefer_lang(buyer.get("name"))
        address_parts = [
            buyer.get("addressLine1", ""), buyer.get("postalCode", ""), buyer.get("city", "")
        ]
        address = ", ".join(p for p in address_parts if p) or None

        # CPV-Codes: verschiedene Formate (Objekt-Array oder String-Array)
        cpv_raw = _get(notice, *_FIELD_CPV) or []
        cpvs: list[str] = []
        for c in cpv_raw:
            if isinstance(c, dict):
                code = c.get("code") or c.get("id") or c.get("value")
                if code:
                    cpvs.append(str(code))
            elif isinstance(c, str):
                cpvs.append(c)

        value_data = _get(notice, *_FIELD_VALUE) or {}
        if isinstance(value_data, (int, float)):
            value_max = int(float(value_data) * 100)
        elif isinstance(value_data, dict):
            value_max = int(float(value_data["amount"]) * 100) if value_data.get("amount") is not None else None
        else:
            value_max = None

        lots_raw = _get(notice, *_FIELD_LOTS) or []
        lots = []
        for i, lot in enumerate(lots_raw[:20]):
            lots.append({
                "number": i + 1,
                "title": _prefer_lang(lot.get("title")),
                "description": _prefer_lang(lot.get("description")),
                "cpv_codes": [c.get("code") for c in (lot.get("cpvCodes") or lot.get("cpv") or []) if isinstance(c, dict) and c.get("code")],
            })

        notice_id = _get(notice, *_FIELD_ID)
        country_raw = buyer.get("country", "DEU")
        country = "DE" if country_raw in ("DEU", "DE", "Germany") else "EU"

        return NormalizedTender(
            title=title[:500],
            source_slug=self.slug,
            external_id=str(notice_id) if notice_id else None,
            source_url=f"https://ted.europa.eu/udl?uri=TED:NOTICE:{notice_id}:TEXT:DE:HTML" if notice_id else None,
            description=_prefer_lang(_get(notice, *_FIELD_DESC)),
            contracting_authority=authority,
            authority_address=address,
            deadline=parse_dt(_get(notice, *_FIELD_DEADLINE)),
            publication_date=parse_dt(_get(notice, *_FIELD_PUBDATE)),
            value_max=value_max,
            cpv_codes=cpvs,
            country=country,
            procedure_type=_get(notice, *_FIELD_PROC),
            lots=lots,
            platform_name="TED Europa",
            raw_data={"noticeId": notice_id},
        )
