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
DAYS_BACK = 2  # Letzten N Tage abrufen (heute + gestern für Überlappung)

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


def _releases_from_zip(zip_bytes: bytes) -> tuple[list[dict], int, int]:
    """Extrahiert OCDS-Releases aus der ZIP-Datei.
    Gibt (releases, files_count, parse_errors) zurück.
    """
    releases: list[dict] = []
    files_count = 0
    parse_errors = 0
    try:
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            for name in zf.namelist():
                if not name.lower().endswith(".json"):
                    continue
                files_count += 1
                try:
                    data = json.loads(zf.read(name))
                except Exception:
                    parse_errors += 1
                    continue
                if isinstance(data, list):
                    releases.extend(data)
                elif isinstance(data, dict):
                    found = False
                    for key in ("releases", "records", "items"):
                        if isinstance(data.get(key), list):
                            releases.extend(data[key])
                            found = True
                            break
                    if not found and (data.get("tender") or data.get("ocid")):
                        releases.append(data)
    except zipfile.BadZipFile:
        parse_errors += 1
    return releases, files_count, parse_errors


class DoeCrawler:
    slug = "doe"

    async def run(self) -> int:
        async with AsyncSessionLocal() as db:
            return await self._crawl(db)

    async def _crawl(self, db: AsyncSession) -> int:
        source = (await db.execute(select(Source).where(Source.slug == self.slug))).scalar_one_or_none()
        start = time.monotonic()
        processed = new = 0

        days = [
            (datetime.now(timezone.utc) - timedelta(days=i)).strftime("%Y-%m-%d")
            for i in range(DAYS_BACK)
        ]

        ip_blocked = False
        days_log: list[dict] = []

        async with httpx.AsyncClient(timeout=120, headers=_HEADERS, follow_redirects=True) as client:
            for day in days:
                releases, day_stats, status = await self._fetch_day(client, day)
                days_log.append({"day": day, "status": status, **day_stats})

                if status == "blocked":
                    ip_blocked = True
                    break
                if status == "error":
                    break

                day_ocds_errors = 0
                for release in releases:
                    norm = _parse_ocds_release(release)
                    if not norm:
                        day_ocds_errors += 1
                        continue
                    _, is_new = await resolve(norm, db)
                    processed += 1
                    if is_new:
                        new += 1

                days_log[-1]["ocds_parse_errors"] = day_ocds_errors

                await db.commit()
                await asyncio.sleep(1.0)

        elapsed = int((time.monotonic() - start) * 1000)
        if source:
            source.last_run_at = datetime.now(timezone.utc)
            if not ip_blocked:
                source.last_run_entries = new

        details = {"days": days_log}

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
                details=details,
            ))
        else:
            level = "info" if processed > 0 else "warn"
            if source:
                source.status = "ok" if processed > 0 else source.status
            db.add(CrawlLog(
                source_id=source.id if source else None,
                level=level,
                message=(
                    f"DÖE: {processed} processed, {new} new"
                    if processed > 0
                    else "DÖE: 0 Einträge abgerufen — API-Pfad oder Datenformat prüfen"
                ),
                entries_processed=processed,
                entries_new=new,
                duration_ms=elapsed,
                details=details,
            ))
        await db.commit()
        return new

    async def _fetch_day(self, client: httpx.AsyncClient, day: str) -> tuple[list[dict], dict, str]:
        """Lädt alle Notices eines Tages als ocds.zip.
        Gibt (releases, stats_dict, status) zurück. status: 'ok' | 'blocked' | 'error'
        """
        url = f"{API_BASE}{ENDPOINT}"
        t0 = time.monotonic()
        try:
            r = await client.get(url, params={"pubDay": day, "format": "ocds.zip"})
            ms = int((time.monotonic() - t0) * 1000)
            stats: dict = {"http_status": r.status_code, "ms": ms}

            if r.status_code == 403:
                return [], stats, "blocked"
            if r.status_code == 404:
                stats["note"] = "kein Export für diesen Tag (Wochenende / kein Datensatz)"
                return [], stats, "ok"
            r.raise_for_status()

            content_type = r.headers.get("content-type", "")
            stats["content_type"] = content_type
            stats["size_bytes"] = len(r.content)

            if "zip" in content_type or r.content[:4] == b"PK\x03\x04":
                releases, files_count, zip_errors = _releases_from_zip(r.content)
                stats["zip_files"] = files_count
                stats["zip_parse_errors"] = zip_errors
                stats["releases_in_zip"] = len(releases)
                return releases, stats, "ok"

            stats["note"] = f"unerwartetes Format: {content_type}"
            return [], stats, "ok"

        except httpx.HTTPStatusError as e:
            ms = int((time.monotonic() - t0) * 1000)
            stats = {"http_status": e.response.status_code, "ms": ms}
            if e.response.status_code == 403:
                return [], stats, "blocked"
            return [], stats, "error"
        except Exception as e:
            ms = int((time.monotonic() - t0) * 1000)
            return [], {"ms": ms, "error": type(e).__name__}, "error"
