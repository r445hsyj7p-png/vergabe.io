import uuid
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from ...models import KomunenSource

FALLBACK = [
    ("09162000", "München", "Bayern", 1512491),
    ("11000000", "Berlin", "Berlin", 3677472),
    ("02000000", "Hamburg", "Hamburg", 1853935),
    ("05315000", "Köln", "Nordrhein-Westfalen", 1073096),
    ("05111000", "Düsseldorf", "Nordrhein-Westfalen", 619294),
    ("08111000", "Stuttgart", "Baden-Württemberg", 626275),
    ("06412000", "Frankfurt am Main", "Hessen", 773068),
    ("03241001", "Hannover", "Niedersachsen", 538068),
    ("05382024", "Dortmund", "Nordrhein-Westfalen", 588250),
    ("05113000", "Essen", "Nordrhein-Westfalen", 576259),
    ("14612000", "Leipzig", "Sachsen", 620507),
    ("14628370", "Dresden", "Sachsen", 557098),
    ("04011000", "Bremen", "Bremen", 563290),
    ("12053000", "Potsdam", "Brandenburg", 181963),
    ("01002000", "Kiel", "Schleswig-Holstein", 246794),
    ("09564000", "Nürnberg", "Bayern", 515543),
    ("05314000", "Bonn", "Nordrhein-Westfalen", 333011),
    ("05515000", "Münster", "Nordrhein-Westfalen", 317763),
    ("05711000", "Bielefeld", "Nordrhein-Westfalen", 343433),
    ("06414000", "Wiesbaden", "Hessen", 285723),
    ("09761000", "Augsburg", "Bayern", 294100),
    ("09362000", "Regensburg", "Bayern", 155519),
    ("09461000", "Erlangen", "Bayern", 114624),
    ("14713000", "Chemnitz", "Sachsen", 247237),
    ("15003000", "Halle (Saale)", "Sachsen-Anhalt", 238321),
]


async def sync_from_destatis(db: AsyncSession) -> int:
    added = 0
    for ags, name, bundesland, einwohner in FALLBACK:
        existing = (await db.execute(
            select(KomunenSource).where(KomunenSource.ags == ags)
        )).scalar_one_or_none()
        if not existing:
            db.add(KomunenSource(
                id=uuid.uuid4(), ags=ags, name=name,
                bundesland=bundesland, einwohner=einwohner, status="auto",
            ))
            added += 1
    await db.commit()
    return added
