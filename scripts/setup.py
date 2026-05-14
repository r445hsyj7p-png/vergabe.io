#!/usr/bin/env python3
"""
vergabe.io — First-run setup script.
Runs automatically via Docker Compose 'setup' service on every start,
but is idempotent: migrations and seeding are skipped if already done.
"""
import asyncio
import sys
import os
import traceback

sys.path.insert(0, "/app")


# ── Step 1: Run Alembic migrations ────────────────────────────────────────
def run_migrations():
    print("▶  Running database migrations…")
    try:
        from alembic.config import Config
        from alembic import command as alembic_command

        cfg = Config("/app/alembic.ini")
        cfg.set_main_option("script_location", "/app/alembic")
        alembic_command.upgrade(cfg, "head")
        print("✓  Migrations applied.")
    except SystemExit as exc:
        print(f"✗  Migration failed (alembic exited with code {exc.code}).")
        traceback.print_exc()
        sys.exit(1)
    except Exception:
        print("✗  Migration failed.")
        traceback.print_exc()
        sys.exit(1)


# ── Step 2: Seed default sources (idempotent) ──────────────────────────────
async def seed_sources():
    from sqlalchemy import text
    from sqlalchemy.future import select
    from database import AsyncSessionLocal
    from models import Source

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
    from sqlalchemy.future import select
    from database import AsyncSessionLocal
    from models import KomunenSource
    import uuid

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(KomunenSource).limit(1))
        if result.scalar_one_or_none():
            print("✓  Kommunen already seeded.")
            return

        print("▶  Seeding starter Kommunen list…")
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


# ── Step 4: Create admin user (non-interactive) ────────────────────────────
async def setup_admin():
    """Write admin password to /data/admin.key if not already set.

    Priority:
      1. /data/admin.key already exists → skip (idempotent)
      2. ADMIN_PASSWORD env var is set → use it
      3. Fallback → generate a random 20-char password and print it to stdout
    """
    import secrets
    import string
    from sqlalchemy import text
    from database import AsyncSessionLocal

    admin_file = "/data/admin.key"
    os.makedirs("/data", exist_ok=True)

    if os.path.exists(admin_file):
        print("✓  Admin already configured.")
        return

    password = os.environ.get("ADMIN_PASSWORD", "").strip()

    if password:
        print("  (Admin-Passwort aus Umgebungsvariable ADMIN_PASSWORD übernommen)")
    else:
        alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
        password = "".join(secrets.choice(alphabet) for _ in range(20))
        print("\n" + "!" * 60)
        print("  KEIN ADMIN_PASSWORD GESETZT — zufälliges Passwort generiert:")
        print(f"  ADMIN_PASSWORD = {password}")
        print("  Bitte in der .env-Datei setzen, um dieses Passwort zu")
        print("  behalten. Andernfalls wird bei erneutem Setup ein neues")
        print("  Passwort generiert.")
        print("!" * 60 + "\n")

    with open(admin_file, "w") as f:
        f.write(password)
    os.chmod(admin_file, 0o600)

    async with AsyncSessionLocal() as db:
        await db.execute(text(
            "INSERT INTO crawl_logs (id, level, message) "
            "VALUES (gen_random_uuid(), 'info', 'Admin user configured') "
            "ON CONFLICT DO NOTHING"
        ))
        await db.commit()

    print("✓  Admin-Passwort gespeichert.")
    print("✓  Starte vergabe.io…\n")


# ── Step 5: Trigger initial crawl ─────────────────────────────────────────
async def trigger_initial_crawl():
    from sqlalchemy.future import select
    from database import AsyncSessionLocal
    from models import CrawlLog

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(CrawlLog).limit(1))
        if result.scalar_one_or_none():
            print("✓  Initial crawl already ran.")
            return

    print("▶  Triggering initial data fetch (TED + bund.de)…")
    print("   (runs in background via scheduler — data appears within minutes)")

    async with AsyncSessionLocal() as db:
        from models import CrawlLog
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
    try:
        main()
    except SystemExit:
        raise
    except Exception:
        print("\n✗  Setup fehlgeschlagen mit unerwartetem Fehler:")
        traceback.print_exc()
        sys.exit(1)
