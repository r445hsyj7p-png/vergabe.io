#!/bin/bash
set -e

if [ -z "$ADMIN_PASSWORD" ] || [ "$ADMIN_PASSWORD" = "admin" ]; then
    echo "[entrypoint] ERROR: ADMIN_PASSWORD is not set or uses the insecure default 'admin'."
    echo "[entrypoint] Set ADMIN_PASSWORD as an environment variable before starting the container."
    exit 1
fi

if [ -z "$SECRET_KEY" ] || [ "$SECRET_KEY" = "changeme" ]; then
    export SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))")
    echo "[entrypoint] WARNING: Generated ephemeral SECRET_KEY — set SECRET_KEY env var to persist sessions across restarts"
fi

echo "[entrypoint] Running database migrations…"
alembic upgrade head

echo "[entrypoint] Starting application…"
exec "$@"
