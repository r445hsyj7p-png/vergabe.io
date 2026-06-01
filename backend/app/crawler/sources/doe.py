"""
Crawler für den Datenservice Öffentlicher Einkauf (DÖE) / oeffentlichevergabe.de

Deckt EU-Schwellenwert-Ausschreibungen aller Ebenen (Bund, Länder, Kommunen) ab,
die seit 25.10.2023 pflichtgemäß als eForms-DE gemeldet werden.

API-Dokumentation: https://oeffentlichevergabe.de/documentation/swagger-ui/opendata/index.html
Format: OCDS (Open Contracting Data Standard) JSON — kein Auth erforderlich.

Endpoint-Konfiguration: Falls der erste Request 404 zurückgibt, kann die
API_PATH-Konstante angepasst werden (Swagger-UI im Browser öffnen für genaue Pfade).
"""

import asyncio
import time
import httpx
from datetime import datetime, timezone, timedelta
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.database import AsyncSessionLocal
from ...models import Source, CrawlLog
from ..pipeline.normalizer import NormalizedTender, parse_dt, is_it_relevant
from ..pipeline.entity_resolution import resolve

API_BASE = "https://oeffentlichevergabe.de"

# Mögliche Endpoint-Pfade (absteigend nach Wahrscheinlichkeit)
# Swagger-UI: https://oeffentlichevergabe.de/documentation/swagger-ui/opendata/index.html
# Operation "getExportAsEforms" → Pfad enthält wahrscheinlich "eforms" oder "export"
_CANDIDATE_PATHS = [
    "/api/opendata/notices",
    "/api/opendata/v1/notices",
    "/opendata/notices",
    "/opendata/v1/notices",
    "/api/v1/opendata/notices",
    "/api/notices",
    "/opendata/api/notices",
    "/api/opendata/eforms",
    "/opendata/eforms",
]

PAGE_SIZE = 50
MAX_PAGES = 40  # 2.000 Notices max pro Lauf
SLEEP_S = 1.0

# IT-relevante CPV-Präfixe

_HEADERS = {
    "User-Agent": "vergabe.io/1.0 (opendata@vergabe.io)",
    "Accept": "application/json",
}


def _prefer(obj: dict | None, keys: tuple = ("de", "DE", "en", "EN")) -> str | None:
    if not obj:
        return None
    if isinstance(obj, str):
        return obj
    for k in keys:
        if v := obj.get(k):
            return v
    return next(iter(obj.values()), None) if obj else None


def _is_it_relevant(cpv_ids: list[str]) -> bool:
    return is_it_relevant("", cpv_codes=cpv_ids)


def _parse_ocds_release(release: dict) -> NormalizedTender | None:
    """Parst ein OCDS-Release-Objekt in ein NormalizedTender."""
    tender_block = release.get("tender") or {}
    title = _prefer(tender_block.get("title")) or tender_block.get("title")
    if not title or not isinstance(title, str):
        return None

    # CPV-Codes: tender-level classification + items[].classification
    cpv_ids: list[str] = []
    def _extract_cpv(cls_obj: dict) -> None:
        if cls_obj and cls_obj.get("scheme", "").upper() == "CPV" and cls_obj.get("id"):
            cpv_ids.append(str(cls_obj["id"]).replace("-", "")[:8])
    _extract_cpv(tender_block.get("classification") or {})
    for item in tender_block.get("items") or []:
        _extract_cpv(item.get("classification") or {})
        for add_cls in item.get("additionalClassifications") or []:
            _extract_cpv(add_cls)

    if not _is_it_relevant(cpv_ids):
        return None

    # Auftraggeber
    buyer = release.get("buyer") or {}
    buyer_detail: dict = {}
    for party in release.get("parties") or []:
        if party.get("id") == buyer.get("id") or "buyer" in (party.get("roles") or []):
            buyer_detail = party
            break
    authority_name = _prefer(buyer_detail.get("name")) or _prefer(buyer.get("name"))
    addr = buyer_detail.get("address") or {}
    authority_addr = ", ".join(
        p for p in [addr.get("streetAddress"), addr.get("postalCode"), addr.get("locality")] if p
    ) or None

    # Fristen & Datum
    period = tender_block.get("tenderPeriod") or {}
    deadline = parse_dt(period.get("endDate"))
    pub_date = parse_dt(release.get("date"))

    # Wert
    value_block = tender_block.get("value") or {}
    value_max = int(float(value_block["amount"]) * 100) if value_block.get("amount") else None

    # Externe ID / URL
    notice_id = release.get("id") or release.get("ocid")
    source_url = None
    for doc in tender_block.get("documents") or []:
        if doc.get("documentType") in ("biddingDocuments", "x-notice") and doc.get("url"):
            source_url = doc["url"]
            break
    if not source_url and notice_id:
        source_url = f"{API_BASE}/ui/de/notice/{notice_id}"

    desc_raw = _prefer(tender_block.get("description")) or ""
    description = desc_raw[:2000] if desc_raw else None

    # Lose
    lots = []
    for i, lot in enumerate((tender_block.get("lots") or [])[:20]):
        lots.append({
            "number": i + 1,
            "title": _prefer(lot.get("title")),
            "description": _prefer(lot.get("description")),
            "cpv_codes": cpv_ids,
        })

    return NormalizedTender(
        title=title[:500],
        source_slug="doe",
        external_id=str(notice_id) if notice_id else None,
        source_url=source_url,
        description=description,
        contracting_authority=authority_name[:300] if authority_name else None,
        authority_address=authority_addr,
        deadline=deadline,
        publication_date=pub_date,
        value_max=value_max,
        cpv_codes=cpv_ids,
        country="DE",
        procedure_type=tender_block.get("procurementMethod"),
        lots=lots,
        platform_name="oeffentlichevergabe.de",
        raw_data={"ocid": release.get("ocid"), "noticeId": notice_id},
    )


class DoeCrawler:
    slug = "doe"

    async def run(self) -> int:
        async with AsyncSessionLocal() as db:
            return await self._crawl(db)

    async def _crawl(self, db: AsyncSession) -> int:
        source = (await db.execute(select(Source).where(Source.slug == self.slug))).scalar_one_or_none()
        start = time.monotonic()
        processed = new = 0

        # Nur Ausschreibungen der letzten 2 Tage abrufen (überlappend für Robustheit)
        date_from = (datetime.now(timezone.utc) - timedelta(days=2)).strftime("%Y-%m-%d")

        async with httpx.AsyncClient(timeout=30, headers=_HEADERS) as client:
            working_path = await self._discover_path(client, source, db)
            if working_path is None:
                elapsed = int((time.monotonic() - start) * 1000)
                db.add(CrawlLog(source_id=source.id if source else None, level="warn",
                                message="DÖE: Endpoint nicht erreichbar — 0 processed, 0 new",
                                entries_processed=0, entries_new=0, duration_ms=elapsed))
                await db.commit()
                return 0

            for page in range(1, MAX_PAGES + 1):
                try:
                    r = await client.get(
                        f"{API_BASE}{working_path}",
                        params={
                            "publishedFrom": date_from,
                            "page": page,
                            "size": PAGE_SIZE,
                            "format": "ocds",
                        },
                    )
                    r.raise_for_status()
                    data = r.json()
                except httpx.HTTPStatusError as e:
                    msg = f"DÖE page {page} HTTP {e.response.status_code}"
                    if source:
                        db.add(CrawlLog(source_id=source.id, level="warn", message=msg))
                        await db.commit()
                    break
                except Exception as e:
                    msg = f"DÖE page {page} error: {e}"
                    if source:
                        db.add(CrawlLog(source_id=source.id, level="warn", message=msg))
                        await db.commit()
                    break

                releases = (
                    data.get("releases")
                    or data.get("items")
                    or data.get("notices")
                    or []
                )
                if not releases:
                    break

                for rel in releases:
                    norm = _parse_ocds_release(rel)
                    if not norm:
                        continue
                    _, is_new = await resolve(norm, db)
                    processed += 1
                    if is_new:
                        new += 1

                await db.commit()

                total = data.get("totalElements") or data.get("total") or data.get("totalCount")
                if total and (page * PAGE_SIZE) >= int(total):
                    break
                if len(releases) < PAGE_SIZE:
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
            message=f"DÖE: {processed} processed, {new} new",
            entries_processed=processed,
            entries_new=new,
            duration_ms=elapsed,
        ))
        await db.commit()
        return new

    async def _discover_path(self, client: httpx.AsyncClient, source, db: AsyncSession) -> str | None:
        """Findet den korrekten API-Endpoint-Pfad durch sequentielles Ausprobieren."""
        ip_blocked = False
        for path in _CANDIDATE_PATHS:
            try:
                r = await client.get(
                    f"{API_BASE}{path}",
                    params={"page": 1, "size": 1, "format": "ocds"},
                )
                if r.status_code in (200, 206):
                    return path
                if r.status_code == 403:
                    # IP-Block gilt für alle Pfade auf diesem Server
                    ip_blocked = True
                    break
                # 404/405/etc. → falscher Pfad, weiter probieren
            except Exception:
                continue

        if ip_blocked:
            msg = (
                "DÖE: Zugriff verweigert (403) — Server-IP blockiert. "
                "Gleicher Mechanismus wie service.bund.de. "
                "Swagger-UI: https://oeffentlichevergabe.de/documentation/swagger-ui/opendata/index.html"
            )
        else:
            msg = (
                f"DÖE: Kein Endpoint erreichbar ({len(_CANDIDATE_PATHS)} Pfade getestet). "
                "Bitte Swagger-UI im Browser öffnen: "
                "https://oeffentlichevergabe.de/documentation/swagger-ui/opendata/index.html"
            )
        if source:
            source.status = "warn"
            db.add(CrawlLog(source_id=source.id, level="warn", message=msg))
            await db.commit()
        return None
