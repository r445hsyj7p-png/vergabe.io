"""
Wikidata URL-Ableitung
Fragt für Gemeinden ohne main_url die offizielle Website
über die Wikidata SPARQL API ab.

Wird wöchentlich vom Scheduler aufgerufen (nach Destatis-Sync).
"""
import asyncio
import uuid
from typing import Optional
import httpx

from database import AsyncSessionLocal
from models import KomunenSource, CrawlLog
from sqlalchemy import select, and_

SPARQL_ENDPOINT = "https://query.wikidata.org/sparql"
BATCH_SIZE = 50  # max AGS per SPARQL query
RATE_LIMIT_DELAY = 1.5  # seconds between requests (Wikidata fair use)


def _build_sparql(ags_list: list[str]) -> str:
    """SPARQL: AGS → offizielle Website (P856)."""
    values = " ".join(f'"{ags}"' for ags in ags_list)
    return f"""
SELECT ?ags ?website WHERE {{
  VALUES ?ags {{ {values} }}
  ?item wdt:P439 ?ags .
  ?item wdt:P856 ?website .
}}
"""


async def resolve_wikidata_urls():
    """Für alle Gemeinden ohne main_url: URL via Wikidata auflösen."""
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(KomunenSource).where(
                and_(
                    KomunenSource.main_url.is_(None),
                    KomunenSource.ags.isnot(None),
                )
            ).limit(500)
        )
        sources = result.scalars().all()

    if not sources:
        print("[Wikidata] Keine Gemeinden ohne URL.")
        return

    print(f"[Wikidata] Resolving URLs for {len(sources)} Gemeinden…")
    ags_map = {k.ags: k.id for k in sources}
    ags_list = list(ags_map.keys())

    url_map: dict[str, str] = {}

    async with httpx.AsyncClient(timeout=30) as client:
        for i in range(0, len(ags_list), BATCH_SIZE):
            batch = ags_list[i:i + BATCH_SIZE]
            sparql = _build_sparql(batch)
            try:
                r = await client.get(
                    SPARQL_ENDPOINT,
                    params={"query": sparql, "format": "json"},
                    headers={"Accept": "application/sparql-results+json",
                             "User-Agent": "vergabe.io/1.0 (Ausschreibungsaggregator)"},
                )
                r.raise_for_status()
                data = r.json()
                for binding in data.get("results", {}).get("bindings", []):
                    ags = binding.get("ags", {}).get("value", "")
                    website = binding.get("website", {}).get("value", "")
                    if ags and website:
                        # Prefer .de domains over others
                        if ags not in url_map or website.endswith(".de"):
                            url_map[ags] = website
            except Exception as e:
                print(f"[Wikidata] Batch {i}-{i+BATCH_SIZE} error: {e}")

            await asyncio.sleep(RATE_LIMIT_DELAY)

    # Update DB
    resolved = 0
    async with AsyncSessionLocal() as db:
        for ags, url in url_map.items():
            komunen_id = ags_map.get(ags)
            if not komunen_id:
                continue
            result = await db.execute(select(KomunenSource).where(KomunenSource.id == komunen_id))
            k = result.scalar_one_or_none()
            if k and not k.main_url:
                k.main_url = url
                resolved += 1
        await db.commit()

    await _log("info", f"Wikidata: {resolved}/{len(sources)} URLs aufgelöst")
    print(f"[Wikidata] {resolved} URLs aufgelöst.")


async def _log(level: str, message: str):
    async with AsyncSessionLocal() as db:
        log = CrawlLog(level=level, message=message)
        db.add(log)
        await db.commit()


if __name__ == "__main__":
    asyncio.run(resolve_wikidata_urls())
