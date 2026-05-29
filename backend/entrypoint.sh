#!/bin/bash
set -e

if [ -z "$SECRET_KEY" ] || [ "$SECRET_KEY" = "changeme" ]; then
    export SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))")
    echo "[entrypoint] WARNING: Generated ephemeral SECRET_KEY — set SECRET_KEY env var to persist sessions across restarts"
fi

echo "[entrypoint] Running database migrations…"

# Falls alembic_version fehlt aber Tabellen schon existieren (z.B. manuell oder
# durch vorherigen Deploy ohne Alembic), Schema als aktuell markieren statt
# Migrationen nochmals auszuführen.
python3 - <<'PYEOF'
import asyncio, os, sys
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

async def stamp_if_needed():
    url = os.environ["DATABASE_URL"]
    engine = create_async_engine(url)
    try:
        async with engine.connect() as conn:
            # Prüfe ob alembic_version leer/fehlt, aber sources-Tabelle existiert
            has_version = await conn.scalar(text(
                "SELECT EXISTS(SELECT 1 FROM information_schema.tables "
                "WHERE table_name='alembic_version')"
            ))
            if has_version:
                version = await conn.scalar(text("SELECT version_num FROM alembic_version LIMIT 1"))
                if version:
                    print(f"[entrypoint] alembic already at {version}, skipping stamp")
                    return
            has_schema = await conn.scalar(text(
                "SELECT EXISTS(SELECT 1 FROM information_schema.tables "
                "WHERE table_name='sources')"
            ))
            if has_schema:
                print("[entrypoint] Schema exists but no alembic_version — stamping head")
                await conn.execute(text("CREATE TABLE IF NOT EXISTS alembic_version (version_num VARCHAR(32) NOT NULL PRIMARY KEY)"))
                await conn.execute(text("DELETE FROM alembic_version"))
                await conn.execute(text("INSERT INTO alembic_version VALUES ('002')"))
                await conn.commit()
    finally:
        await engine.dispose()

asyncio.run(stamp_if_needed())
PYEOF

alembic upgrade head

echo "[entrypoint] Starting application…"
exec "$@"
