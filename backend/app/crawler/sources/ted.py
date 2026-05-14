import asyncio
import time
import httpx
from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.database import AsyncSessionLocal
from ...models import Source, CrawlLog
from ..pipeline.normalizer import NormalizedTender, extract_cpv_codes
from ..pipeline.entity_resolution import resolve

API_BASE = "https://api.ted.europa.eu/v3"
FIELDS = "noticeId,title,description,buyer,cpvCodes,estimatedTotalValue,submissionDeadlineDate,publicationDate,procedureType,lots"
PAGE_SIZE = 50
MAX_PAGES = 20
SLEEP_S = 1.0


def _prefer_lang(obj: dict | None, langs=("DEU", "ENG", "FRA")) -> str | None:
    if not obj:
        return None
    if isinstance(obj, str):
        return obj
    for lang in langs:
        if val := obj.get(lang):
            return val
    return next(iter(obj.values()), None) if obj else None


def _parse_dt(s: str | None) -> datetime | None:
    if not s:
        return None
    for fmt in ("%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
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

        async with httpx.AsyncClient(timeout=30) as client:
            for page in range(1, MAX_PAGES + 1):
                try:
                    r = await client.get(
                        f"{API_BASE}/notices/search",
                        params={"q": "cpv:[72000000 TO 72999999]", "fields": FIELDS,
                                "page": page, "limit": PAGE_SIZE, "sortBy": "publicationDate", "sortOrder": "desc"},
                    )
                    r.raise_for_status()
                    data = r.json()
                except Exception as e:
                    consecutive_errors += 1
                    if consecutive_errors >= 3:
                        break
                    await asyncio.sleep(2 ** consecutive_errors)
                    continue

                consecutive_errors = 0
                notices = data.get("notices", [])
                if not notices:
                    break

                for notice in notices:
                    norm = self._parse(notice)
                    if not norm:
                        continue
                    is_new_before = norm.source_url is None
                    tender = await resolve(norm, db)
                    processed += 1
                    if tender.created_at and (datetime.now(timezone.utc) - tender.created_at).total_seconds() < 60:
                        new += 1

                await db.commit()
                if len(notices) < PAGE_SIZE:
                    break
                await asyncio.sleep(SLEEP_S)

        elapsed = int((time.monotonic() - start) * 1000)
        log = CrawlLog(
            source_id=source.id if source else None,
            level="info",
            message=f"TED crawl: {processed} processed, {new} new",
            entries_processed=processed,
            entries_new=new,
            duration_ms=elapsed,
        )
        db.add(log)
        if source:
            source.last_run_at = datetime.now(timezone.utc)
            source.last_run_entries = new
            source.status = "ok"
        await db.commit()
        return new

    def _parse(self, notice: dict) -> NormalizedTender | None:
        title = _prefer_lang(notice.get("title"))
        if not title:
            return None

        buyer = notice.get("buyer") or {}
        authority = _prefer_lang(buyer.get("officialName")) or _prefer_lang(buyer.get("name"))
        address_parts = [
            buyer.get("addressLine1", ""), buyer.get("postalCode", ""), buyer.get("city", "")
        ]
        address = ", ".join(p for p in address_parts if p) or None

        cpvs = [c.get("code", "") for c in (notice.get("cpvCodes") or []) if c.get("code")]
        value_data = notice.get("estimatedTotalValue") or {}
        value_max = int(float(value_data.get("amount", 0)) * 100) if value_data.get("amount") else None

        lots_raw = notice.get("lots") or []
        lots = []
        for i, lot in enumerate(lots_raw[:20]):
            lots.append({
                "number": i + 1,
                "title": _prefer_lang(lot.get("title")),
                "description": _prefer_lang(lot.get("description")),
                "cpv_codes": [c.get("code") for c in (lot.get("cpvCodes") or []) if c.get("code")],
            })

        return NormalizedTender(
            title=title[:500],
            source_slug=self.slug,
            external_id=notice.get("noticeId"),
            source_url=f"https://ted.europa.eu/udl?uri=TED:NOTICE:{notice.get('noticeId')}:TEXT:DE:HTML",
            description=_prefer_lang(notice.get("description")),
            contracting_authority=authority,
            authority_address=address,
            deadline=_parse_dt(notice.get("submissionDeadlineDate")),
            publication_date=_parse_dt(notice.get("publicationDate")),
            value_max=value_max,
            cpv_codes=cpvs,
            country="EU" if buyer.get("country", "DE") != "DEU" else "DE",
            procedure_type=notice.get("procedureType"),
            lots=lots,
            platform_name="TED Europa",
            raw_data={"noticeId": notice.get("noticeId")},
        )
