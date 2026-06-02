"""
Crawler für den Vergabemarktplatz NRW (vergabe.NRW)

Primär: CKAN Open.NRW API (ckan.open.nrw.de)
  Dataset: ausschreibungen_des_vergabemarktplatzes_nrw_1587477165
  → package_show gibt Ressourcen-URLs → JSON-Download

Fallback: daten.vergabe.nrw.de REST (war Hauptaggregator, DNS existiert nicht mehr)

Auth: Keine (Open Data)
"""

import asyncio
import time
import httpx
from datetime import datetime, timezone, timedelta
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.database import AsyncSessionLocal  # für run()
from ...models import Source, CrawlLog
from ..pipeline.normalizer import NormalizedTender, extract_cpv_codes, parse_dt, is_it_relevant
from ..pipeline.entity_resolution import resolve

# CKAN Open.NRW — Dataset mit allen Vergabemarktplatz-NRW-Ausschreibungen
_CKAN_API = "https://ckan.open.nrw.de/api/3/action"
_CKAN_DATASET_ID = "ausschreibungen_des_vergabemarktplatzes_nrw_1587477165"

# Legacy REST — daten.vergabe.nrw.de existiert DNS-seitig nicht mehr (Stand 06/2026).
# Bleibt als Fallback, falls Domain reaktiviert wird.
_LEGACY_API_CANDIDATES = [
    "https://daten.vergabe.nrw.de/rest/evergabe",
    "https://daten.vergabe.nrw.de/rest/vergabe_westfalen",
]

PAGE_SIZE = 50
MAX_PAGES = 40
SLEEP_S = 1.0

_HEADERS = {
    "User-Agent": "vergabe.io/1.0 (opendata@vergabe.io)",
    "Accept": "application/json",
}

# Feldnamen-Mapping (CKAN-Ressourcen nutzen deutsche Spaltenbezeichnungen)
_FIELD_TITLE = ("titel", "bezeichnung", "betreff", "title", "beschreibung_kurz", "Bekanntmachungstitel")
_FIELD_AUTHORITY = ("auftraggeber", "vergabestelle", "auftraggeber_name", "Auftraggeber")
_FIELD_DEADLINE = ("angebotsfrist", "einreichungsfrist", "frist", "deadline", "Angebotsfrist")
_FIELD_PUBDATE = ("veroeffentlichungsdatum", "bekanntmachungsdatum", "datum", "Datum", "Bekanntmachungsdatum")
_FIELD_CPV = ("cpv_code", "cpv", "cpvCode", "CPV", "cpv_codes", "klassifikation")
_FIELD_VALUE = ("auftragswert", "auftragswert_von", "value", "Auftragswert")
_FIELD_ID = ("id", "notice_id", "vergabe_id", "ID", "Vergabe-ID", "noticeId")
_FIELD_URL = ("url", "link", "detail_url", "URL", "Bekanntmachungs-URL")


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
    if not cpv_codes:
        cpv_codes = extract_cpv_codes(str(item))

    if not is_it_relevant(title, cpv_codes=cpv_codes):
        return None

    notice_id = _get(item, *_FIELD_ID)
    url_raw = _get(item, *_FIELD_URL)
    source_url = url_raw or (f"https://www.vergabe.nrw.de/ausschreibung/{notice_id}" if notice_id else None)

    desc = _get(item, "beschreibung", "leistungsbeschreibung", "description", "Beschreibung", "text")
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

    region = _get(item, "ort", "stadt", "region", "bundesland", "Ort") or "Nordrhein-Westfalen"

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

        requests_log: list[dict] = []

        async with httpx.AsyncClient(timeout=30, headers=_HEADERS, follow_redirects=True) as client:
            items = await self._fetch_items(client, requests_log)

        if items is None:
            elapsed = int((time.monotonic() - start) * 1000)
            if source:
                source.status = "warn"
                source.last_run_at = datetime.now(timezone.utc)
            db.add(CrawlLog(
                source_id=source.id if source else None,
                level="warn",
                message="NRW: Keine Daten abgerufen — CKAN und Legacy-API nicht erreichbar",
                entries_processed=0, entries_new=0, duration_ms=elapsed,
                details={"requests": requests_log},
            ))
            await db.commit()
            return 0

        total_fetched = len(items)
        parse_errors = 0
        filtered = 0

        for item in items:
            norm = _parse_item(item)
            if not norm:
                if _get(item, *_FIELD_TITLE):
                    filtered += 1
                else:
                    parse_errors += 1
                continue
            _, is_new = await resolve(norm, db)
            processed += 1
            if is_new:
                new += 1

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
            details={
                "fetched": total_fetched,
                "parse_errors": parse_errors,
                "filtered": filtered,
                "requests": requests_log,
            },
        ))
        await db.commit()
        return new

    async def _fetch_items(self, client: httpx.AsyncClient, requests_log: list[dict]) -> list[dict] | None:
        """Versucht CKAN zuerst, dann Legacy-REST."""
        items = await self._fetch_via_ckan(client, requests_log)
        if items is not None:
            return items

        date_from = (datetime.now(timezone.utc) - timedelta(days=3)).strftime("%Y-%m-%d")
        for base in _LEGACY_API_CANDIDATES:
            t0 = time.monotonic()
            try:
                r = await client.get(base, params={"page": 0, "size": PAGE_SIZE,
                                                    "sort": "veroeffentlichungsdatum,desc",
                                                    "filter[veroeffentlichungsdatum][$gte]": date_from})
                ms = int((time.monotonic() - t0) * 1000)
                requests_log.append({"url": base, "http_status": r.status_code, "ms": ms, "source": "legacy"})
                if r.status_code == 200:
                    data = r.json()
                    legacy_items: list = []
                    if "_embedded" in data:
                        for v in data["_embedded"].values():
                            if isinstance(v, list):
                                legacy_items = v
                                break
                    elif "content" in data:
                        legacy_items = data["content"]
                    elif isinstance(data, list):
                        legacy_items = data
                    if legacy_items:
                        requests_log[-1]["items_found"] = len(legacy_items)
                        return legacy_items
            except Exception as e:
                ms = int((time.monotonic() - t0) * 1000)
                requests_log.append({"url": base, "ms": ms, "error": type(e).__name__, "source": "legacy"})
                continue

        return None

    async def _fetch_via_ckan(self, client: httpx.AsyncClient, requests_log: list[dict]) -> list[dict] | None:
        """Lädt aktuelle Ausschreibungen über die CKAN Open.NRW API."""
        ckan_url = f"{_CKAN_API}/package_show"
        t0 = time.monotonic()
        try:
            r = await client.get(ckan_url, params={"id": _CKAN_DATASET_ID})
            ms = int((time.monotonic() - t0) * 1000)
            requests_log.append({"url": ckan_url, "http_status": r.status_code, "ms": ms, "source": "ckan_meta"})
            if r.status_code != 200:
                return None

            resources = r.json().get("result", {}).get("resources", [])
            if not resources:
                requests_log[-1]["note"] = "keine Ressourcen im Dataset"
                return None

            json_resources = [res for res in resources if res.get("format", "").upper() == "JSON"]
            csv_resources = [res for res in resources if res.get("format", "").upper() == "CSV"]
            candidates = json_resources or csv_resources or resources

            requests_log[-1]["resources_total"] = len(resources)
            requests_log[-1]["resources_json"] = len(json_resources)
            requests_log[-1]["resources_csv"] = len(csv_resources)

            for res in candidates[:3]:
                url = res.get("url")
                if not url:
                    continue
                t1 = time.monotonic()
                try:
                    r2 = await client.get(url, timeout=60)
                    ms2 = int((time.monotonic() - t1) * 1000)
                    ct = r2.headers.get("content-type", "")
                    entry: dict = {
                        "url": url, "http_status": r2.status_code, "ms": ms2,
                        "content_type": ct, "size_bytes": len(r2.content), "source": "ckan_resource",
                    }
                    requests_log.append(entry)
                    if r2.status_code != 200:
                        continue
                    if "json" in ct or url.endswith(".json"):
                        data = r2.json()
                        if isinstance(data, list):
                            entry["items_found"] = len(data)
                            return data
                        for key in ("result", "records", "data", "items", "results"):
                            if isinstance(data.get(key), list):
                                entry["items_found"] = len(data[key])
                                return data[key]
                    elif "csv" in ct or url.endswith(".csv"):
                        items = self._parse_csv(r2.text)
                        entry["items_found"] = len(items)
                        return items
                except Exception as e:
                    ms2 = int((time.monotonic() - t1) * 1000)
                    requests_log.append({"url": url, "ms": ms2, "error": type(e).__name__, "source": "ckan_resource"})
                    continue

        except Exception as e:
            ms = int((time.monotonic() - t0) * 1000)
            requests_log.append({"url": ckan_url, "ms": ms, "error": type(e).__name__, "source": "ckan_meta"})
        return None

    @staticmethod
    def _parse_csv(text: str) -> list[dict]:
        import csv, io
        reader = csv.DictReader(io.StringIO(text))
        return list(reader)
