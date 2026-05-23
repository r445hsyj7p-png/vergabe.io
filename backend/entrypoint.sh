#!/bin/bash
set -e

if [ -z "$SECRET_KEY" ] || [ "$SECRET_KEY" = "changeme" ]; then
    export SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))")
    echo "[entrypoint] WARNING: Generated ephemeral SECRET_KEY — set SECRET_KEY env var to persist sessions across restarts"
fi

echo "[entrypoint] Running database migrations…"
alembic upgrade head

echo "[entrypoint] Starting application…"
exec "$@"
