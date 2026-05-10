#!/bin/bash
# entrypoint.sh — reads /data/admin.key (written by setup) and
# injects ADMIN_PASSWORD + SECRET_KEY into the process environment
# before starting the actual service command.

set -e

ADMIN_KEY_FILE="/data/admin.key"
SECRET_KEY_FILE="/data/secret.key"

# Wait for setup to complete (admin.key must exist)
MAX_WAIT=120
WAITED=0
while [ ! -f "$ADMIN_KEY_FILE" ]; do
  if [ $WAITED -ge $MAX_WAIT ]; then
    echo "[entrypoint] Timeout waiting for setup to complete."
    exit 1
  fi
  echo "[entrypoint] Waiting for setup to complete… ($WAITED/${MAX_WAIT}s)"
  sleep 3
  WAITED=$((WAITED + 3))
done

# Generate a stable secret key from the password on first run
if [ ! -f "$SECRET_KEY_FILE" ]; then
  ADMIN_PASSWORD=$(cat "$ADMIN_KEY_FILE")
  python3 -c "
import hashlib, os, sys
pw = sys.argv[1]
salt = os.urandom(16).hex()
key = hashlib.sha256((pw + salt).encode()).hexdigest() + hashlib.sha256((salt + pw).encode()).hexdigest()
print(key[:64])
" "$ADMIN_PASSWORD" > "$SECRET_KEY_FILE"
fi

export ADMIN_PASSWORD=$(cat "$ADMIN_KEY_FILE")
export SECRET_KEY=$(cat "$SECRET_KEY_FILE")

echo "[entrypoint] Config loaded. Starting: $*"
exec "$@"
