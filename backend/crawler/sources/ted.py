"""TED Europa REST API fetcher — api.ted.europa.eu/v3"""
import asyncio
from datetime import datetime, timezone, timedelta
from typing import List, Optional
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from pipeline.normalizer import NormalizedTender, parse_date, parse_value_cents
from pipeline.entity_resolution import resolve
from database import AsyncSessionLocal
from models import Source, CrawlLog
from sqlalchemy import select
import uuid

TED_BASE = "https://api.ted.europa.eu/v3"
HEADERS = {"Content-Type": "application/json", "Accept": "application/json"}


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=30))
async def _fetch_page(client: httpx.AsyncClient, params: dict) -> dict:
    resp = await client.get(f"{TED_BASE}/notices/search", params=params, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    return resp.json()


def _normalize_ted_notice(notice: dict) -> NormalizedTender:
    n = NormalizedTender()
    n.platform_name = "TED Europa"
    n.country = notice.get("buyer", {}).get("country", {}).get("code", "EU")

    # Title — prefer German, fallback English/FR
    titles = notice.get("title", {})
    n.title = (
        titles.get("DEU") or titles.get("ENG") or titles.get("FRA") or
        next(iter(titles.values()), "Unbekannt")
    )

    # Description
    descs = notice.get("description", {})
    n.description = descs.get("DEU") or descs.get("ENG") or next(iter(descs.values()), None)

    # Contracting authority
    buyer = notice.get("buyer", {})
    n.contracting_authority = buyer.get("officialName")
    addr = buyer.get("address", {})
    n.authority_address = f"{addr.get('street', '')} {addr.get('town', '')} {addr.get('postalCode', '')}".strip()
    n.authority_email = buyer.get("email")
    n.authority_phone = buyer.get("phone")
    n.region = addr.get("town") or addr.get("nuts", {}).get("label")

    # Dates
    n.deadline = parse_date(notice.get("submissionDeadlineDate"))
    n.publication_date = parse_date(notice.get("publicationDate"))

    # CPV
    cpvs = notice.get("cpvCodes", [])
    n.cpv_codes = [c.get("code", "") for c in cpvs if c.get("code")]

    # Value
    val = notice.get("estimatedTotalValue", {})
    if val:
        n.value_min = parse_value_cents(str(val.get("minValue", "") or ""))
        n.value_max = parse_value_cents(str(val.get("maxValue", "") or val.get("value", "") or ""))
    n.currency = val.get("currency", "EUR") if val else "EUR"

    # IDs
    n.external_id = notice.get("noticeId") or notice.get("id")
    n.source_url = f"https://ted.europa.eu/en/notice/-/detail/{n.external_id}" if n.external_id else None
    n.procedure_type = notice.get("procedureType", {}).get("label", {}).get("DEU")

    # Lots
    for lot in notice.get("lots", []):
        lot_titles = lot.get("title", {})
        lot_descs = lot.get("description", {})
        n.lots.append({
            "lot_number": lot.get("lotNumber"),
            "title": lot_titles.get("DEU") or lot_titles.get("ENG") or next(iter(lot_titles.values()), None),
            "description": lot_descs.get("DEU") or lot_descs.get("ENG") or next(iter(lot_descs.values()), None),
        })

    n.raw_data = {"source": "ted", "notice_id": n.external_id}
    n.finalize()
    return n


async def run_ted_fetcher(source_id: uuid.UUID, since: Optional[datetime] = None):
    if not since:
        since = datetime.now(timezone.utc) - timedelta(hours=8)

    start = datetime.now(timezone.utc)
    new_count = 0
    total = 0

    consecutive_errors = 0
    max_consecutive_errors = 3

    async with httpx.AsyncClient(timeout=60) as client:
        page = 1
        while True:
            params = {
                "publishedFrom": since.strftime("%Y%m%d"),
                "scope": "3",
                "fields": "noticeId,title,description,buyer,cpvCodes,estimatedTotalValue,submissionDeadlineDate,publicationDate,procedureType,lots",
                "page": page,
                "pageSize": 50,
                "sortBy": "publicationDate",
                "sortOrder": "desc",
            }
            try:
                data = await _fetch_page(client, params)
                consecutive_errors = 0
            except Exception as e:
                consecutive_errors += 1
                await _log(source_id, "error", f"TED fetch error page {page}: {e}")
                if consecutive_errors >= max_consecutive_errors:
                    break
                page += 1
                await asyncio.sleep(2 ** consecutive_errors)
                continue

            notices = data.get("notices", [])
            if not notices:
                break

            async with AsyncSessionLocal() as db:
                for notice in notices:
                    try:
                        normalized = _normalize_ted_notice(notice)
                        tender, is_new = await resolve(db, normalized, source_id)
                        if is_new:
                            from models import Lot
                            for lot_data in normalized.lots:
                                lot = Lot(tender_id=tender.id, **lot_data)
                                db.add(lot)
                            new_count += 1
                        total += 1
                    except Exception as e:
                        await _log(source_id, "warn", f"TED notice parse error: {e}")
                await db.commit()

            total_pages = data.get("totalPages", 1)
            if page >= total_pages or page >= 20:  # max 20 pages / run
                break
            page += 1
            await asyncio.sleep(1.0)  # respectful rate limiting

    duration = int((datetime.now(timezone.utc) - start).total_seconds() * 1000)
    await _log(source_id, "info", f"TED: {total} processed, {new_count} new", total, new_count, duration)
    await _update_source(source_id, new_count)
    return new_count


async def _log(source_id, level, message, processed=0, new=0, duration=None):
    async with AsyncSessionLocal() as db:
        log = CrawlLog(
            source_id=source_id,
            level=level,
            message=message,
            entries_processed=processed,
            entries_new=new,
            duration_ms=duration,
        )
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
