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

from ...core.database import AsyncSessionLocal
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

        async with httpx.AsyncClient(timeout=30, headers=_HEADERS, follow_redirects=True) as client:
            items = await self._fetch_items(client, source, db)

        if items is None:
            # Fehler wurde bereits geloggt
            elapsed = int((time.monotonic() - start) * 1000)
            if source:
                source.status = "warn"
                source.last_run_at = datetime.now(timezone.utc)
            db.add(CrawlLog(source_id=source.id if source else None, level="warn",
                            message="NRW: Keine Daten abgerufen — CKAN und Legacy-API nicht erreichbar",
                            entries_processed=0, entries_new=0, duration_ms=elapsed))
            await db.commit()
            return 0

        async with AsyncSessionLocal() as db2:
            for item in items:
                norm = _parse_item(item)
                if not norm:
                    continue
                _, is_new = await resolve(norm, db2)
                processed += 1
                if is_new:
                    new += 1
            await db2.commit()

        elapsed = int((time.monotonic() - start) * 1000)
        async with AsyncSessionLocal() as db3:
            src = (await db3.execute(select(Source).where(Source.slug == self.slug))).scalar_one_or_none()
            if src:
                src.last_run_at = datetime.now(timezone.utc)
                src.last_run_entries = new
                src.status = "ok" if processed > 0 else src.status
            db3.add(CrawlLog(
                source_id=src.id if src else None,
                level="info",
                message=f"NRW: {processed} processed, {new} new",
                entries_processed=processed,
                entries_new=new,
                duration_ms=elapsed,
            ))
            await db3.commit()
        return new

    async def _fetch_items(self, client: httpx.AsyncClient, source, db: AsyncSession) -> list[dict] | None:
        """Versucht CKAN zuerst, dann Legacy-REST."""
        # 1. CKAN Open.NRW
        items = await self._fetch_via_ckan(client)
        if items is not None:
            return items

        # 2. Legacy REST (daten.vergabe.nrw.de — möglicherweise reaktiviert)
        date_from = (datetime.now(timezone.utc) - timedelta(days=3)).strftime("%Y-%m-%d")
        for base in _LEGACY_API_CANDIDATES:
            try:
                r = await client.get(base, params={"page": 0, "size": PAGE_SIZE,
                                                    "sort": "veroeffentlichungsdatum,desc",
                                                    "filter[veroeffentlichungsdatum][$gte]": date_from})
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
                        return legacy_items
            except Exception:
                continue

        return None

    async def _fetch_via_ckan(self, client: httpx.AsyncClient) -> list[dict] | None:
        """Lädt aktuelle Ausschreibungen über die CKAN Open.NRW API."""
        try:
            # Ressourcen-URLs aus Dataset-Metadaten holen
            r = await client.get(f"{_CKAN_API}/package_show",
                                  params={"id": _CKAN_DATASET_ID})
            if r.status_code != 200:
                return None

            resources = r.json().get("result", {}).get("resources", [])
            if not resources:
                return None

            # JSON-Ressourcen bevorzugen; CSV als Fallback
            json_resources = [res for res in resources if res.get("format", "").upper() == "JSON"]
            csv_resources = [res for res in resources if res.get("format", "").upper() == "CSV"]
            candidates = json_resources or csv_resources
            if not candidates:
                candidates = resources  # beliebiges Format versuchen

            for res in candidates[:3]:
                url = res.get("url")
                if not url:
                    continue
                try:
                    r2 = await client.get(url, timeout=60)
                    if r2.status_code != 200:
                        continue
                    ct = r2.headers.get("content-type", "")
                    if "json" in ct or url.endswith(".json"):
                        data = r2.json()
                        if isinstance(data, list):
                            return data
                        for key in ("result", "records", "data", "items", "results"):
                            if isinstance(data.get(key), list):
                                return data[key]
                    elif "csv" in ct or url.endswith(".csv"):
                        return self._parse_csv(r2.text)
                except Exception:
                    continue

        except Exception:
            pass
        return None

    @staticmethod
    def _parse_csv(text: str) -> list[dict]:
        """Parst CSV-Text in eine Liste von Dicts."""
        import csv, io
        reader = csv.DictReader(io.StringIO(text))
        return list(reader)
