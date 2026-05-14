import uuid
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
from ..models import Source, KomunenSource


SOURCES = [
    ("TED Europa", "ted", "api", "https://api.ted.europa.eu/v3", "TEDCrawler", 4),
    ("service.bund.de", "bund", "rss", "https://www.service.bund.de", "BundRssCrawler", 2),
]

STARTER_KOMUNEN = [
    ("09162000", "München", "Bayern", 1512491, "https://www.muenchen.de", "https://vergabe.muenchen.de"),
    ("11000000", "Berlin", "Berlin", 3677472, "https://www.berlin.de", "https://my.vergabeplattform.berlin.de"),
    ("02000000", "Hamburg", "Hamburg", 1853935, "https://www.hamburg.de", None),
    ("05111000", "Düsseldorf", "Nordrhein-Westfalen", 619294, "https://www.duesseldorf.de", "https://vergabe.duesseldorf.de"),
    ("05315000", "Köln", "Nordrhein-Westfalen", 1073096, "https://www.koeln.de", "https://vergabeplattform.stadt-koeln.de"),
    ("08111000", "Stuttgart", "Baden-Württemberg", 626275, "https://www.stuttgart.de", "https://vergabe.stuttgart.de"),
    ("09564000", "Nürnberg", "Bayern", 515543, "https://www.nuernberg.de", None),
    ("06412000", "Frankfurt am Main", "Hessen", 773068, "https://www.frankfurt.de", "https://vergabe.stadt-frankfurt.de"),
    ("03241001", "Hannover", "Niedersachsen", 538068, "https://www.hannover.de", "https://evergabe.hannover-stadt.de"),
    ("14612000", "Leipzig", "Sachsen", 620507, "https://www.leipzig.de", None),
    ("14628370", "Dresden", "Sachsen", 557098, "https://www.dresden.de", None),
    ("04011000", "Bremen", "Bremen", 563290, "https://www.bremen.de", "https://vergabe.bremen.de"),
    ("05382024", "Dortmund", "Nordrhein-Westfalen", 588250, "https://www.dortmund.de", None),
    ("05113000", "Essen", "Nordrhein-Westfalen", 576259, "https://www.essen.de", None),
    ("12053000", "Potsdam", "Brandenburg", 181963, "https://www.potsdam.de", None),
]


async def seed_all(db: AsyncSession) -> None:
    await _seed_sources(db)
    await _seed_komunen(db)


async def _seed_sources(db: AsyncSession) -> None:
    for name, slug, stype, base_url, cls, interval in SOURCES:
        existing = (await db.execute(select(Source).where(Source.slug == slug))).scalar_one_or_none()
        if not existing:
            db.add(Source(
                id=uuid.uuid4(), name=name, slug=slug, source_type=stype,
                base_url=base_url, scraper_class=cls, interval_hours=interval,
            ))
    await db.commit()


async def _seed_komunen(db: AsyncSession) -> None:
    count = (await db.execute(select(KomunenSource).limit(1))).scalar_one_or_none()
    if count:
        return
    for ags, name, bl, ew, main_url, vergabe_url in STARTER_KOMUNEN:
        db.add(KomunenSource(
            id=uuid.uuid4(), ags=ags, name=name, bundesland=bl, einwohner=ew,
            main_url=main_url, vergabe_url=vergabe_url,
            discovery_confidence=1.0 if vergabe_url else None,
            status="verified" if vergabe_url else "auto",
        ))
    await db.commit()
