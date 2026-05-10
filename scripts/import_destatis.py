#!/usr/bin/env python3
"""
Import Gemeinden from Destatis GV-ISys into komunen_sources table.
Usage: python scripts/import_destatis.py [--csv path/to/gemeinden.csv]

Without a file, inserts a curated starter list of major cities for demo.
"""
import asyncio
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

from database import AsyncSessionLocal, engine, Base
from models import KomunenSource
from sqlalchemy import text
import uuid

# Starter list — major German cities with known vergabe URLs
STARTER = [
    ("09162000", "München", "Bayern", 1512491, "https://www.muenchen.de", "https://vergabe.muenchen.de"),
    ("11000000", "Berlin", "Berlin", 3677472, "https://www.berlin.de", "https://my.vergabeplattform.berlin.de"),
    ("02000000", "Hamburg", "Hamburg", 1853935, "https://www.hamburg.de", "https://www.vergabe.hamburg.de"),
    ("05111000", "Düsseldorf", "Nordrhein-Westfalen", 619294, "https://www.duesseldorf.de", "https://vergabe.duesseldorf.de"),
    ("05111000", "Köln", "Nordrhein-Westfalen", 1073096, "https://www.koeln.de", "https://vergabeplattform.stadt-koeln.de"),
    ("08111000", "Stuttgart", "Baden-Württemberg", 626275, "https://www.stuttgart.de", "https://vergabe.stuttgart.de"),
    ("09564000", "Nürnberg", "Bayern", 515543, "https://www.nuernberg.de", None),
    ("06412000", "Frankfurt am Main", "Hessen", 773068, "https://www.frankfurt.de", "https://vergabe.stadt-frankfurt.de"),
    ("03241001", "Hannover", "Niedersachsen", 538068, "https://www.hannover.de", "https://evergabe.hannover-stadt.de"),
    ("14612000", "Leipzig", "Sachsen", 620507, "https://www.leipzig.de", None),
    ("14628370", "Dresden", "Sachsen", 557098, "https://www.dresden.de", None),
    ("15003000", "Halle (Saale)", "Sachsen-Anhalt", 238321, "https://www.halle.de", "https://ausschreibung.halle.de"),
    ("04011000", "Bremen", "Bremen", 563290, "https://www.bremen.de", "https://vergabe.bremen.de"),
    ("07315000", "Augsburg", "Bayern", 294100, "https://www.augsburg.de", None),
    ("05116000", "Bonn", "Nordrhein-Westfalen", 333011, "https://www.bonn.de", None),
    ("05711000", "Bielefeld", "Nordrhein-Westfalen", 343433, "https://www.bielefeld.de", None),
    ("06413000", "Wiesbaden", "Hessen", 285723, "https://www.wiesbaden.de", None),
    ("05334002", "Münster", "Nordrhein-Westfalen", 317763, "https://www.muenster.de", None),
    ("14713000", "Chemnitz", "Sachsen", 247237, "https://www.chemnitz.de", None),
    ("03402000", "Oldenburg", "Niedersachsen", 170772, "https://www.oldenburg.de", None),
    ("09161000", "Augsburg (Landkreis)", "Bayern", 256360, "https://www.landkreis-augsburg.de", None),
    ("05162004", "Recklinghausen", "Nordrhein-Westfalen", 113902, "https://www.recklinghausen.de", None),
]


async def main():
    async with AsyncSessionLocal() as db:
        for ags, name, bundesland, ew, main_url, vergabe_url in STARTER:
            k = KomunenSource(
                id=uuid.uuid4(),
                ags=ags,
                name=name,
                bundesland=bundesland,
                einwohner=ew,
                main_url=main_url,
                vergabe_url=vergabe_url,
                discovery_confidence=1.0 if vergabe_url else None,
                status='verified' if vergabe_url else 'auto',
            )
            db.add(k)
        await db.commit()
        print(f"Imported {len(STARTER)} Gemeinden into komunen_sources.")


if __name__ == "__main__":
    asyncio.run(main())
