#!/usr/bin/env python3
"""
vergabe.io — First-run setup script.
Runs automatically via Docker Compose 'setup' service on every start,
but is idempotent: migrations and seeding are skipped if already done.
Admin creation is only prompted when no admin exists yet.
"""
import asyncio
import sys
import os
import getpass

sys.path.insert(0, "/app")

from sqlalchemy import text, select
from database import engine, AsyncSessionLocal
from models import KomunenSource, Source, CrawlLog


# ── Step 1: Run Alembic migrations ────────────────────────────────────────
def run_migrations():
    import subprocess
    print("▶  Running database migrations…")
    result = subprocess.run(
        ["alembic", "upgrade", "head"],
        cwd="/app",
        capture_output=False,
    )
    if result.returncode != 0:
        print("✗  Migration failed. Aborting.")
        sys.exit(1)
    print("✓  Migrations applied.")


# ── Step 2: Seed default sources (idempotent) ──────────────────────────────
async def seed_sources():
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Source).limit(1))
        if result.scalar_one_or_none():
            print("✓  Sources already seeded.")
            return

        print("▶  Seeding default data sources…")
        await db.execute(text("""
            INSERT INTO sources (id, name, slug, source_type, base_url, scraper_class, interval_hours, is_active, status)
            VALUES
            (gen_random_uuid(), 'TED Europa',         'ted',            'api',     'https://api.ted.europa.eu/v3',          'TEDScraper',         4, true, 'ok'),
            (gen_random_uuid(), 'service.bund.de',    'bund',           'rss',     'https://www.service.bund.de',           'BundRSSScraper',     2, true, 'ok'),
            (gen_random_uuid(), 'evergabe-online.de', 'evergabe-online','rss',     'https://www.evergabe-online.de',        'EvergabeRSSScraper', 4, true, 'ok'),
            (gen_random_uuid(), 'DTVP',               'dtvp',           'scraper', 'https://www.dtvp.de',                   'DTVPScraper',        6, true, 'ok'),
            (gen_random_uuid(), 'cosinex NRW',        'cosinex-nrw',    'scraper', 'https://www.evergabe.nrw.de',           'CosinexScraper',     6, true, 'ok'),
            (gen_random_uuid(), 'simap.ch',           'simap',          'api',     'https://www.simap.ch',                  'SimapScraper',       6, true, 'ok'),
            (gen_random_uuid(), 'DTVP Hannover',      'dtvp-hannover',  'scraper', 'https://www.evergabe.hannover-stadt.de','DTVPScraper',        6, true, 'ok'),
            (gen_random_uuid(), 'sachsen-vergabe.de', 'sachsen',        'scraper', 'https://www.sachsen-vergabe.de',        'GenericScraper',     8, true, 'ok')
            ON CONFLICT (slug) DO NOTHING
        """))
        await db.commit()
        print("✓  Default sources seeded.")


# ── Step 3: Seed starter Kommunen (idempotent) ────────────────────────────
async def seed_komunen():
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(KomunenSource).limit(1))
        if result.scalar_one_or_none():
            print("✓  Kommunen already seeded.")
            return

        print("▶  Seeding starter Kommunen list…")
        import uuid
        STARTER = [
            ("09162000", "München",           "Bayern",                  1512491, "https://www.muenchen.de",        "https://vergabe.muenchen.de"),
            ("11000000", "Berlin",            "Berlin",                  3677472, "https://www.berlin.de",          "https://my.vergabeplattform.berlin.de"),
            ("02000000", "Hamburg",           "Hamburg",                 1853935, "https://www.hamburg.de",         None),
            ("05111000", "Düsseldorf",        "Nordrhein-Westfalen",      619294, "https://www.duesseldorf.de",     "https://vergabe.duesseldorf.de"),
            ("05315000", "Köln",              "Nordrhein-Westfalen",     1073096, "https://www.koeln.de",           "https://vergabeplattform.stadt-koeln.de"),
            ("08111000", "Stuttgart",         "Baden-Württemberg",        626275, "https://www.stuttgart.de",       "https://vergabe.stuttgart.de"),
            ("09564000", "Nürnberg",          "Bayern",                   515543, "https://www.nuernberg.de",       None),
            ("06412000", "Frankfurt am Main", "Hessen",                   773068, "https://www.frankfurt.de",       "https://vergabe.stadt-frankfurt.de"),
            ("03241001", "Hannover",          "Niedersachsen",            538068, "https://www.hannover.de",        "https://evergabe.hannover-stadt.de"),
            ("14612000", "Leipzig",           "Sachsen",                  620507, "https://www.leipzig.de",         None),
            ("14628370", "Dresden",           "Sachsen",                  557098, "https://www.dresden.de",         None),
            ("15003000", "Halle (Saale)",     "Sachsen-Anhalt",           238321, "https://www.halle.de",           "https://ausschreibung.halle.de"),
            ("04011000", "Bremen",            "Bremen",                   563290, "https://www.bremen.de",          "https://vergabe.bremen.de"),
            ("09761000", "Augsburg",          "Bayern",                   294100, "https://www.augsburg.de",        None),
            ("05314000", "Bonn",              "Nordrhein-Westfalen",      333011, "https://www.bonn.de",            None),
            ("05711000", "Bielefeld",         "Nordrhein-Westfalen",      343433, "https://www.bielefeld.de",       None),
            ("06414000", "Wiesbaden",         "Hessen",                   285723, "https://www.wiesbaden.de",       None),
            ("05515000", "Münster",           "Nordrhein-Westfalen",      317763, "https://www.muenster.de",        None),
            ("14713000", "Chemnitz",          "Sachsen",                  247237, "https://www.chemnitz.de",        None),
            ("05162004", "Recklinghausen",    "Nordrhein-Westfalen",      113902, "https://www.recklinghausen.de",  None),
            ("09362000", "Regensburg",        "Bayern",                   155519, "https://www.regensburg.de",      None),
            ("01002000", "Kiel",              "Schleswig-Holstein",       246794, "https://www.kiel.de",            None),
            ("09461000", "Erlangen",          "Bayern",                   114624, "https://www.erlangen.de",        None),
            ("05382024", "Dortmund",          "Nordrhein-Westfalen",      588250, "https://www.dortmund.de",        None),
            ("05113000", "Essen",             "Nordrhein-Westfalen",      576259, "https://www.essen.de",           None),
            ("12053000", "Potsdam",           "Brandenburg",              181963, "https://www.potsdam.de",         None),
            ("06412000", "Darmstadt",         "Hessen",                   159878, "https://www.darmstadt.de",       None),
        ]
        for ags, name, bl, ew, main_url, vergabe_url in STARTER:
            k = KomunenSource(
                id=uuid.uuid4(),
                ags=ags,
                name=name,
                bundesland=bl,
                einwohner=ew,
                main_url=main_url,
                vergabe_url=vergabe_url,
                discovery_confidence=1.0 if vergabe_url else None,
                status="verified" if vergabe_url else "auto",
            )
            db.add(k)
        await db.commit()
        print(f"✓  {len(STARTER)} Kommunen seeded.")


# ── Step 4: Create admin user (interactive, only if none exists) ───────────
async def setup_admin():
    """Check if an admin token is already configured; if not, prompt."""
    admin_file = "/data/admin.key"
    os.makedirs("/data", exist_ok=True)

    if os.path.exists(admin_file):
        print("✓  Admin already configured.")
        return

    print("\n" + "═" * 50)
    print("  vergabe.io — Erster Start: Admin einrichten")
    print("═" * 50)
    print("Bitte wähle ein Passwort für den Admin-Zugang.")
    print("Dieses Passwort wird zum Einloggen in die App benötigt.\n")

    while True:
        try:
            password = getpass.getpass("  Admin-Passwort: ")
        except EOFError:
            # Non-interactive mode (e.g. CI) — use env var fallback
            password = os.environ.get("ADMIN_PASSWORD", "")
            if not password:
                print("✗  Kein Passwort gesetzt. Setze ADMIN_PASSWORD in .env.")
                sys.exit(1)
            print("  (Passwort aus Umgebungsvariable ADMIN_PASSWORD übernommen)")
            break

        if len(password) < 8:
            print("  ✗  Mindestens 8 Zeichen erforderlich.\n")
            continue

        try:
            confirm = getpass.getpass("  Passwort bestätigen: ")
        except EOFError:
            confirm = password

        if password != confirm:
            print("  ✗  Passwörter stimmen nicht überein.\n")
            continue

        break

    # Write to persistent volume + inject into env for backend
    with open(admin_file, "w") as f:
        f.write(password)
    os.chmod(admin_file, 0o600)

    # Also update the DB config marker
    async with AsyncSessionLocal() as db:
        await db.execute(text("INSERT INTO crawl_logs (id, level, message) VALUES (gen_random_uuid(), 'info', 'Admin user configured') ON CONFLICT DO NOTHING"))
        await db.commit()

    print("\n✓  Admin-Passwort gespeichert.")
    print("✓  Starte vergabe.io…\n")


# ── Step 5: Trigger initial crawl ─────────────────────────────────────────
async def trigger_initial_crawl():
    """Enqueue initial crawl jobs so data is available immediately."""
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(CrawlLog).limit(1))
        if result.scalar_one_or_none():
            print("✓  Initial crawl already ran.")
            return

    print("▶  Triggering initial data fetch (TED + bund.de)…")
    print("   (runs in background via scheduler — data appears within minutes)")

    # Write a marker so scheduler knows to run immediately on startup
    async with AsyncSessionLocal() as db:
        log = CrawlLog(level="info", message="setup:initial_crawl_requested")
        db.add(log)
        await db.commit()
    print("✓  Initial crawl queued.")


# ── Main ───────────────────────────────────────────────────────────────────
async def async_main():
    await seed_sources()
    await seed_komunen()
    await setup_admin()
    await trigger_initial_crawl()
    # Destatis erweiterte Liste (ergänzt die 27 Starter-Kommunen)
    try:
        from crawler.komunen.destatis_sync import sync_from_destatis
        await sync_from_destatis()
    except Exception as e:
        print(f"[Setup] Destatis sync skipped: {e} (wird vom Scheduler nachgeholt)")


def main():
    print("\n╔══════════════════════════════╗")
    print("║   vergabe.io — Setup         ║")
    print("╚══════════════════════════════╝\n")

    run_migrations()
    asyncio.run(async_main())

    print("\n✓  Setup abgeschlossen. App startet…\n")


if __name__ == "__main__":
    main()
