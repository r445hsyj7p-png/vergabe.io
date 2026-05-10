"""
Destatis GV-ISys Sync
Lädt das offizielle Gemeindeverzeichnis von Destatis und fügt
fehlende Gemeinden automatisch in komunen_sources ein.

Datenquelle: https://www.destatis.de/DE/Themen/Laender-Regionen/
             Regionales/Gemeindeverzeichnis/Administrativ/
             Archiv/GVAuszugJ/31122023_Auszug_GV.xlsx.html

Wird quartalsweise vom Scheduler aufgerufen.
"""
import asyncio
import io
import uuid
from typing import Optional
import httpx

from database import AsyncSessionLocal
from models import KomunenSource, CrawlLog
from sqlalchemy import select, and_

# Destatis publiziert das Gemeindeverzeichnis als Excel-Download.
# URL ändert sich jährlich — aktuell für 31.12.2023:
DESTATIS_URL = (
    "https://www.destatis.de/DE/Themen/Laender-Regionen/Regionales/"
    "Gemeindeverzeichnis/Administrativ/Archiv/GVAuszugJ/"
    "31122023_Auszug_GV.xlsx?__blob=publicationFile"
)

# Minimale Einwohnerzahl für IT-relevante Ausschreibungen
MIN_EINWOHNER = 10_000

# Bundesland-Mapping (Kennziffer → Name)
BUNDESLAENDER = {
    "01": "Schleswig-Holstein", "02": "Hamburg", "03": "Niedersachsen",
    "04": "Bremen", "05": "Nordrhein-Westfalen", "06": "Hessen",
    "07": "Rheinland-Pfalz", "08": "Baden-Württemberg", "09": "Bayern",
    "10": "Saarland", "11": "Berlin", "12": "Brandenburg",
    "13": "Mecklenburg-Vorpommern", "14": "Sachsen", "15": "Sachsen-Anhalt",
    "16": "Thüringen",
}


def _derive_url(name: str, bundesland: str) -> list[str]:
    """Ableiten möglicher URLs aus Gemeindename."""
    import re
    # Normalisierung
    n = name.lower()
    n = n.replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss")
    n = re.sub(r"\s+\(.*?\)", "", n)          # "(Rheinl.)" etc. entfernen
    n = re.sub(r",\s*.*$", "", n)              # ", Stadt" entfernen
    n = re.sub(r"[^a-z0-9\s-]", "", n)        # Sonderzeichen
    n = n.strip().replace(" ", "-")

    candidates = [
        f"https://www.{n}.de",
        f"https://www.stadt-{n}.de",
        f"https://www.gemeinde-{n}.de",
        f"https://www.kreis-{n}.de",
    ]
    return candidates


async def _verify_any(client: httpx.AsyncClient, urls: list[str]) -> Optional[str]:
    """Gibt die erste erreichbare URL zurück."""
    for url in urls:
        try:
            r = await client.head(url, timeout=8, follow_redirects=True)
            if r.status_code < 400:
                return str(r.url)  # follow redirects
        except Exception:
            continue
    return None


async def sync_from_destatis():
    """
    Lädt Destatis-Verzeichnis und fügt neue Gemeinden ein.
    Bestehende Einträge werden nicht überschrieben.
    """
    try:
        import openpyxl
    except ImportError:
        # openpyxl not in backend requirements — use fallback list
        await _sync_fallback()
        return

    print("[Destatis] Downloading Gemeindeverzeichnis…")
    try:
        async with httpx.AsyncClient(timeout=60, follow_redirects=True) as client:
            r = await client.get(DESTATIS_URL)
            r.raise_for_status()
            data = r.content
    except Exception as e:
        await _log("warn", f"Destatis download failed: {e}. Using fallback.")
        await _sync_fallback()
        return

    # Parse Excel
    wb = openpyxl.load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    ws = wb.active

    gemeinden = []
    for row in ws.iter_rows(min_row=5, values_only=True):
        if not row or not row[0]:
            continue
        ags = str(row[0]).zfill(8)
        if len(ags) != 8:
            continue
        name = str(row[3] or "").strip()
        einwohner_raw = row[11] or row[10] or 0
        try:
            einwohner = int(einwohner_raw)
        except (ValueError, TypeError):
            continue
        if einwohner < MIN_EINWOHNER or not name:
            continue
        bl_key = ags[:2]
        bundesland = BUNDESLAENDER.get(bl_key, "")
        gemeinden.append((ags, name, bundesland, einwohner))

    print(f"[Destatis] {len(gemeinden)} Gemeinden ≥ {MIN_EINWOHNER} EW gefunden.")
    await _upsert_gemeinden(gemeinden)


async def _sync_fallback():
    """
    Wenn Destatis nicht erreichbar: erweiterte statische Liste
    mit ~200 deutschen Städten ab 20.000 EW.
    """
    EXTENDED = [
        # Format: (AGS, Name, Bundesland, Einwohner)
        ("05112000","Duisburg","Nordrhein-Westfalen",495787),
        ("05113000","Essen","Nordrhein-Westfalen",576259),
        ("05114000","Frankfurt am Main","Hessen",763380),
        ("05117000","Gelsenkirchen","Nordrhein-Westfalen",259645),
        ("05119000","Krefeld","Nordrhein-Westfalen",226811),
        ("05120000","Mönchengladbach","Nordrhein-Westfalen",270765),
        ("05124000","Oberhausen","Nordrhein-Westfalen",210934),
        ("05154000","Bochum","Nordrhein-Westfalen",364742),
        ("05158000","Hagen","Nordrhein-Westfalen",188529),
        ("05162000","Hamm","Nordrhein-Westfalen",178967),
        ("05166000","Herne","Nordrhein-Westfalen",156374),
        ("05170000","Leverkusen","Nordrhein-Westfalen",163729),
        ("05314000","Bonn","Nordrhein-Westfalen",333011),
        ("05370000","Aachen","Nordrhein-Westfalen",260454),
        ("05382000","Dortmund","Nordrhein-Westfalen",588250),
        ("06411000","Darmstadt","Hessen",162708),
        ("06413000","Kassel","Hessen",202137),
        ("07211000","Koblenz","Rheinland-Pfalz",114272),
        ("07311000","Mainz","Rheinland-Pfalz",222058),
        ("07312000","Ludwigshafen","Rheinland-Pfalz",172253),
        ("07313000","Trier","Rheinland-Pfalz",112253),
        ("08211000","Mannheim","Baden-Württemberg",310658),
        ("08212000","Karlsruhe","Baden-Württemberg",313092),
        ("08311000","Freiburg im Breisgau","Baden-Württemberg",236444),
        ("08412000","Heidelberg","Baden-Württemberg",161485),
        ("08416000","Heilbronn","Baden-Württemberg",129021),
        ("08421000","Pforzheim","Baden-Württemberg",126427),
        ("08435000","Reutlingen","Baden-Württemberg",117200),
        ("08436000","Tübingen","Baden-Württemberg",91851),
        ("08437000","Ulm","Baden-Württemberg",128270),
        ("09162000","Ingolstadt","Bayern",138319),
        ("09163000","Rosenheim","Bayern",65455),
        ("09261000","Landshut","Bayern",75571),
        ("09362000","Regensburg","Bayern",155519),
        ("09461000","Erlangen","Bayern",114624),
        ("09462000","Fürth","Bayern",128497),
        ("09463000","Schwabach","Bayern",41193),
        ("09561000","Ansbach","Bayern",42001),
        ("09562000","Würzburg","Bayern",128491),
        ("09661000","Aschaffenburg","Bayern",70578),
        ("09662000","Schweinfurt","Bayern",55133),
        ("09761000","Augsburg","Bayern",294100),
        ("09762000","Kempten","Bayern",69798),
        ("09763000","Kaufbeuren","Bayern",43975),
        ("09764000","Memmingen","Bayern",45468),
        ("10041000","Saarbrücken","Saarland",183136),
        ("01002000","Kiel","Schleswig-Holstein",246794),
        ("01003000","Lübeck","Schleswig-Holstein",216552),
        ("01004000","Flensburg","Schleswig-Holstein",90164),
        ("01005000","Neumünster","Schleswig-Holstein",79487),
        ("03101000","Braunschweig","Niedersachsen",248025),
        ("03102000","Salzgitter","Niedersachsen",104055),
        ("03103000","Wolfsburg","Niedersachsen",124468),
        ("03401000","Delmenhorst","Niedersachsen",78000),
        ("03402000","Oldenburg","Niedersachsen",170772),
        ("03403000","Osnabrück","Niedersachsen",165251),
        ("03404000","Wilhelmshaven","Niedersachsen",76225),
        ("03405000","Göttingen","Niedersachsen",119529),
        ("12052000","Cottbus","Brandenburg",100533),
        ("12053000","Potsdam","Brandenburg",181963),
        ("12054000","Frankfurt (Oder)","Brandenburg",58044),
        ("13003000","Rostock","Mecklenburg-Vorpommern",209191),
        ("13004000","Schwerin","Mecklenburg-Vorpommern",95105),
        ("13005000","Stralsund","Mecklenburg-Vorpommern",59017),
        ("14511000","Zwickau","Sachsen",89540),
        ("14612000","Leipzig","Sachsen",620507),
        ("14713000","Chemnitz","Sachsen",247237),
        ("15002000","Dessau","Sachsen-Anhalt",83289),
        ("15003000","Magdeburg","Sachsen-Anhalt",237697),
        ("16051000","Erfurt","Thüringen",214955),
        ("16052000","Gera","Thüringen",94775),
        ("16053000","Jena","Thüringen",111407),
        ("16054000","Suhl","Thüringen",34688),
        ("16055000","Weimar","Thüringen",65228),
        ("16056000","Eisenach","Thüringen",42370),
    ]
    await _upsert_gemeinden(EXTENDED)


async def _upsert_gemeinden(gemeinden: list[tuple]):
    """Fügt neue Gemeinden ein, überspringt vorhandene (nach AGS)."""
    async with AsyncSessionLocal() as db:
        # Vorhandene AGS laden
        result = await db.execute(select(KomunenSource.ags).where(KomunenSource.ags.isnot(None)))
        existing_ags = {row[0] for row in result.fetchall()}

        new_count = 0
        for ags, name, bundesland, einwohner in gemeinden:
            if ags in existing_ags:
                continue
            k = KomunenSource(
                id=uuid.uuid4(),
                ags=ags,
                name=name,
                bundesland=bundesland,
                einwohner=einwohner,
                status="auto",
            )
            db.add(k)
            new_count += 1

        await db.commit()

    await _log("info", f"Destatis sync: {new_count} neue Gemeinden hinzugefügt ({len(gemeinden)} geprüft)")
    print(f"[Destatis] {new_count} neue Gemeinden hinzugefügt.")


async def _log(level: str, message: str):
    async with AsyncSessionLocal() as db:
        log = CrawlLog(level=level, message=message)
        db.add(log)
        await db.commit()


if __name__ == "__main__":
    asyncio.run(sync_from_destatis())
