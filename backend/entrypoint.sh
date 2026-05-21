#!/bin/bash
set -e

CREDS_FILE="/app/generated_credentials.txt"

if [ -z "$SECRET_KEY" ] || [ "$SECRET_KEY" = "changeme" ]; then
    export SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))")
    echo "[entrypoint] WARNING: Generated ephemeral SECRET_KEY — set SECRET_KEY env var to persist sessions across restarts"
fi

if [ -z "$ADMIN_PASSWORD" ] || [ "$ADMIN_PASSWORD" = "admin" ]; then
    export ADMIN_PASSWORD=$(python3 -c "import secrets; print(secrets.token_urlsafe(16))")
    echo "[entrypoint] Generated admin password — run: docker exec <container> cat $CREDS_FILE"
    echo "ADMIN_PASSWORD=$ADMIN_PASSWORD" > "$CREDS_FILE"
    chmod 600 "$CREDS_FILE"
fi

echo "[entrypoint] Running database migrations…"
alembic upgrade head

echo "[entrypoint] Starting application…"
exec "$@"
