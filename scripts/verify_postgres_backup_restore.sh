#!/usr/bin/env bash
set -euo pipefail

# Restores a PostgreSQL custom-format backup into an isolated database and then
# runs LumisPixel's application-level restore verifier against it.
#
# Required:
#   BACKUP_FILE=/secure/path/lumispixel.dump
#   RESTORE_DATABASE_URL=postgresql://user:pass@host:5432/isolated_restore_db
#
# Safety: this script refuses database names that do not clearly identify an
# isolated restore/drill database. It never drops or creates the target DB.

: "${BACKUP_FILE:?BACKUP_FILE is required}"
: "${RESTORE_DATABASE_URL:?RESTORE_DATABASE_URL is required}"

if [[ ! -r "$BACKUP_FILE" ]]; then
  echo "Backup file is not readable: $BACKUP_FILE" >&2
  exit 2
fi

DB_NAME="$(python - <<'PY'
import os
from urllib.parse import urlparse
url = urlparse(os.environ["RESTORE_DATABASE_URL"])
print((url.path or "").lstrip("/"))
PY
)"

case "$DB_NAME" in
  *restore*|*recovery*|*drill*) ;;
  *)
    echo "Refusing restore: target database '$DB_NAME' is not clearly an isolated restore/recovery/drill database." >&2
    exit 3
    ;;
esac

if ! pg_restore --list "$BACKUP_FILE" >/dev/null; then
  echo "Backup failed pg_restore validation." >&2
  exit 4
fi

# The isolated target must already exist and must not receive production traffic.
pg_restore \
  --exit-on-error \
  --no-owner \
  --no-privileges \
  --clean \
  --if-exists \
  --dbname="$RESTORE_DATABASE_URL" \
  "$BACKUP_FILE"

DATABASE_URL="$RESTORE_DATABASE_URL" python manage.py verify_database_restore

echo "Backup restore drill passed for isolated database '$DB_NAME'."
