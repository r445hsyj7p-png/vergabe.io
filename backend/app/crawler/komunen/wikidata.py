import asyncio
import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from ...models import KomunenSource

SPARQL_URL = "https://query.wikidata.org/sparql"
BATCH_SIZE = 50


async def resolve_wikidata_urls(db: AsyncSession) -> int:
    rows = (await db.execute(
        select(KomunenSource).where(KomunenSource.main_url.is_(None), KomunenSource.ags.isnot(None))
    )).scalars().all()

    updated = 0
    for i in range(0, len(rows), BATCH_SIZE):
        batch = rows[i:i + BATCH_SIZE]
        ags_list = " ".join(f'"{k.ags}"' for k in batch)
        query = f"""
        SELECT ?ags ?website WHERE {{
            ?item wdt:P439 ?ags .
            ?item wdt:P856 ?website .
            FILTER(?ags IN ({ags_list}))
        }}"""
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                r = await client.get(
                    SPARQL_URL,
                    params={"query": query, "format": "json"},
                    headers={"User-Agent": "vergabe.io/1.0 (https://vergabe.io)"},
                )
                data = r.json()
            ags_map = {
                b["ags"]["value"]: b["website"]["value"]
                for b in data.get("results", {}).get("bindings", [])
            }
            for k in batch:
                if k.ags in ags_map:
                    k.main_url = ags_map[k.ags]
                    updated += 1
        except Exception:
            pass
        await asyncio.sleep(1.5)

    await db.commit()
    return updated
