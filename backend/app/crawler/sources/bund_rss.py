import re
import time
import asyncio
import httpx
from datetime import datetime, timezone
from bs4 import BeautifulSoup
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.database import AsyncSessionLocal
from ...models import Source, CrawlLog
from ..pipeline.normalizer import NormalizedTender, extract_cpv_codes
from ..pipeline.entity_resolution import resolve

RSS_URL = "https://www.service.bund.de/IMPORTE/Ausschreibungen/aaa-bund-gesamt.feed"

_DE_MONTHS = {
    "januar": 1, "februar": 2, "märz": 3, "april": 4, "mai": 5, "juni": 6,
    "juli": 7, "august": 8, "september": 9, "oktober": 10, "november": 11, "dezember": 12,
}


def _parse_de_date(text: str) -> datetime | None:
    for fmt in ("%d.%m.%Y", "%d. %B %Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(text.strip(), fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    match = re.search(r"(\d{1,2})\.\s*([A-Za-zä]+)\s*(\d{4})", text)
    if match:
        month = _DE_MONTHS.get(match.group(2).lower())
        if month:
            try:
                return datetime(int(match.group(3)), month, int(match.group(1)), tzinfo=timezone.utc)
            except ValueError:
                pass
    return None


class BundRssCrawler:
    slug = "bund"

    async def run(self) -> int:
        async with AsyncSessionLocal() as db:
            return await self._crawl(db)

    async def _crawl(self, db: AsyncSession) -> int:
        source = (await db.execute(select(Source).where(Source.slug == self.slug))).scalar_one_or_none()
        start = time.monotonic()
        processed = new = 0

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                r = await client.get(RSS_URL, headers={"User-Agent": "vergabe.io/1.0"})
                r.raise_for_status()
                feed = BeautifulSoup(r.text, "xml")
        except Exception as e:
            if source:
                source.status = "error"
                db.add(CrawlLog(source_id=source.id, level="error", message=f"Bund RSS fetch failed: {e}"))
                await db.commit()
            return 0

        for item in feed.find_all("item"):
            norm = self._parse_item(item)
            if not norm:
                continue
            _, is_new = await resolve(norm, db)
            processed += 1
            if is_new:
                new += 1

        await db.commit()
        elapsed = int((time.monotonic() - start) * 1000)
        db.add(CrawlLog(
            source_id=source.id if source else None,
            level="info",
            message=f"Bund RSS: {processed} processed, {new} new",
            entries_processed=processed,
            entries_new=new,
            duration_ms=elapsed,
        ))
        if source:
            source.last_run_at = datetime.now(timezone.utc)
            source.last_run_entries = new
            source.status = "ok"
        await db.commit()
        return new

    def _parse_item(self, item) -> NormalizedTender | None:
        title = item.find("title")
        title = title.get_text(strip=True) if title else None
        if not title:
            return None

        link = item.find("link")
        link = link.get_text(strip=True) if link else None

        raw_desc = ""
        desc_tag = item.find("description")
        if desc_tag:
            raw_desc = desc_tag.get_text()

        try:
            soup = BeautifulSoup(raw_desc, "lxml")
            description = soup.get_text(separator="\n").strip()[:2000]
        except Exception:
            description = re.sub(r"<[^>]+>", " ", raw_desc).strip()[:2000]

        authority = None
        auth_match = re.search(r"Auftraggeber[:\s]+(.+?)(?:\n|<)", raw_desc)
        if auth_match:
            authority = auth_match.group(1).strip()[:300]

        cpv_codes = extract_cpv_codes(raw_desc)

        deadline = None
        for pattern in [r"Angebotsfrist[:\s]+([^\n<]+)", r"Einreichungsfrist[:\s]+([^\n<]+)"]:
            m = re.search(pattern, raw_desc)
            if m:
                deadline = _parse_de_date(m.group(1))
                if deadline:
                    break

        return NormalizedTender(
            title=title[:500],
            source_slug=self.slug,
            source_url=link,
            description=description,
            contracting_authority=authority,
            deadline=deadline,
            cpv_codes=cpv_codes,
            platform_name="service.bund.de",
        )
