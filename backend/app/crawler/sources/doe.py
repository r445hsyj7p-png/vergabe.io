"""
Crawler für den Datenservice Öffentlicher Einkauf (DÖE) / oeffentlichevergabe.de

Deckt EU-Schwellenwert-Ausschreibungen aller Ebenen (Bund, Länder, Kommunen) ab,
die seit 25.10.2023 pflichtgemäß als eForms-DE gemeldet werden.

API: GET https://www.oeffentlichevergabe.de/api/notice-exports
     ?pubDay=YYYY-MM-DD   (ein Tag)   ODER
     ?pubMonth=YYYY-MM    (ein Monat)
     &format=ocds.zip

Liefert eine ZIP-Datei mit OCDS-Release-JSON-Dateien — kein Auth erforderlich.
CPV-Filterung erfolgt client-seitig nach dem Download.

Swagger-Doku: https://oeffentlichevergabe.de/documentation/swagger-ui/opendata/index.html
"""

import asyncio
import io
import json
import time
import zipfile
from datetime import datetime, timezone, timedelta
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import httpx

from ...core.database import AsyncSessionLocal
from ...models import Source, CrawlLog
from ..pipeline.normalizer import NormalizedTender, parse_dt, is_it_relevant
from ..pipeline.entity_resolution import resolve

API_BASE = "https://www.oeffentlichevergabe.de"
ENDPOINT = "/api/notice-exports"
DAYS_BACK = 2  # Letzten N Tage abrufen (überlappend für Robustheit)

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; vergabe.io/1.0; +https://vergabe.io)",
    "Accept": "application/zip, application/octet-stream, */*",
}


def _prefer(obj, keys=("de", "DE", "en", "EN")):
    if not obj:
        return None
    if isinstance(obj, str):
        return obj
    for k in keys:
        if v := obj.get(k):
            return v
    return next(iter(obj.values()), None) if obj else None


def _parse_ocds_release(release: dict) -> NormalizedTender | None:
    tender_block = release.get("tender") or {}
    title = _prefer(tender_block.get("title")) or tender_block.get("title")
    if not title or not isinstance(title, str):
        return None

    # CPV-Codes aus tender.classification + tender.items[].classification
    cpv_ids: list[str] = []

    def _extract_cpv(cls_obj: dict) -> None:
        if cls_obj and cls_obj.get("scheme", "").upper() == "CPV" and cls_obj.get("id"):
            cpv_ids.append(str(cls_obj["id"]).replace("-", "")[:8])

    _extract_cpv(tender_block.get("classification") or {})
    for item in tender_block.get("items") or []:
        _extract_cpv(item.get("classification") or {})
        for add_cls in item.get("additionalClassifications") or []:
            _extract_cpv(add_cls)

    if not is_it_relevant("", cpv_codes=cpv_ids):
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

    # Wert (amount in cents; guard gegen amount=0)
    value_block = tender_block.get("value") or {}
    value_max = int(float(value_block["amount"]) * 100) if value_block.get("amount") is not None else None

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
        description=desc_raw[:2000] if desc_raw else None,
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


def _releases_from_zip(zip_bytes: bytes) -> list[dict]:
    """Extrahiert OCDS-Releases aus der gelieferten ZIP-Datei."""
    releases: list[dict] = []
    try:
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            for name in zf.namelist():
                if not name.lower().endswith(".json"):
                    continue
                try:
                    data = json.loads(zf.read(name))
                except Exception:
                    continue
                if isinstance(data, list):
                    releases.extend(data)
                elif isinstance(data, dict):
                    # OCDS Release-Package oder einzelnes Release
                    found = False
                    for key in ("releases", "records", "items"):
                        if isinstance(data.get(key), list):
                            releases.extend(data[key])
                            found = True
                            break
                    if not found and (data.get("tender") or data.get("ocid")):
                        releases.append(data)
    except zipfile.BadZipFile:
        pass
    return releases


class DoeCrawler:
    slug = "doe"

    async def run(self) -> int:
        async with AsyncSessionLocal() as db:
            return await self._crawl(db)

    async def _crawl(self, db: AsyncSession) -> int:
        source = (await db.execute(select(Source).where(Source.slug == self.slug))).scalar_one_or_none()
        start = time.monotonic()
        processed = new = 0

        # Letzten DAYS_BACK Tage abrufen (heute und gestern, für Überlappung)
        days = [
            (datetime.now(timezone.utc) - timedelta(days=i)).strftime("%Y-%m-%d")
            for i in range(DAYS_BACK)
        ]

        ip_blocked = False
        async with httpx.AsyncClient(timeout=120, headers=_HEADERS, follow_redirects=True) as client:
            for day in days:
                releases, status = await self._fetch_day(client, day)

                if status == "blocked":
                    ip_blocked = True
                    break
                if status == "error":
                    break
                # status == "ok" (auch wenn 0 Releases, z.B. Wochenende/Feiertag)

                for release in releases:
                    norm = _parse_ocds_release(release)
                    if not norm:
                        continue
                    _, is_new = await resolve(norm, db)
                    processed += 1
                    if is_new:
                        new += 1

                await db.commit()
                await asyncio.sleep(1.0)

        elapsed = int((time.monotonic() - start) * 1000)
        if source:
            source.last_run_at = datetime.now(timezone.utc)
            source.last_run_entries = new

        if ip_blocked:
            if source:
                source.status = "warn"
            db.add(CrawlLog(
                source_id=source.id if source else None,
                level="warn",
                message=(
                    "DÖE: Zugriff verweigert (403) — Server blockiert Datacenter-IPs. "
                    "Swagger-UI: https://oeffentlichevergabe.de/documentation/swagger-ui/opendata/index.html"
                ),
                entries_processed=0,
                entries_new=0,
                duration_ms=elapsed,
            ))
        else:
            if source:
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

    async def _fetch_day(self, client: httpx.AsyncClient, day: str) -> tuple[list[dict], str]:
        """Lädt alle Notices eines Tages als ocds.zip. Gibt (releases, status) zurück.
        status: 'ok' | 'blocked' | 'error'
        """
        try:
            r = await client.get(
                f"{API_BASE}{ENDPOINT}",
                params={"pubDay": day, "format": "ocds.zip"},
            )
            if r.status_code == 403:
                return [], "blocked"
            if r.status_code == 404:
                # Kein Export für diesen Tag (Wochenende / kein Datensatz)
                return [], "ok"
            r.raise_for_status()

            content_type = r.headers.get("content-type", "")
            if "zip" in content_type or r.content[:4] == b"PK\x03\x04":
                return _releases_from_zip(r.content), "ok"
            # Unerwartetes Format — ignorieren, aber nicht als Fehler werten
            return [], "ok"

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 403:
                return [], "blocked"
            return [], "error"
        except Exception:
            return [], "error"
