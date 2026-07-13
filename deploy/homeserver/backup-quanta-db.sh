#!/usr/bin/env bash
# WAL-safe online backup of the Quanta SQLite database, with rotation.
#
# Uses SQLite's backup API (src.backup(dst)) run INSIDE the backend container — its python and
# the live DB file are always present, and the backup API is safe to run while the app writes
# (a plain `cp` of a WAL database can capture a torn state). Backups land in the bind-mounted
# data dir, so they're visible on the host at backend/data/backups/.
#
# Schedule it from the deploy user's crontab, e.g. every 6h keeping ~2 weeks:
#   0 */6 * * * /path/to/quanta_social/deploy/homeserver/backup-quanta-db.sh >> /tmp/quanta-backup.log 2>&1
set -euo pipefail

cd "$(dirname "$0")/../.."          # repo root (where compose.yaml lives)
KEEP=${KEEP:-14}                    # how many backups to retain
STAMP=$(date +%Y%m%d-%H%M%S)
DEST_DIR=backend/data/backups
mkdir -p "$DEST_DIR"

docker compose exec -T quanta-backend python - "$STAMP" <<'PY'
import sqlite3, sys
stamp = sys.argv[1]
src = sqlite3.connect("/app/data/data.db")
dst = sqlite3.connect(f"/app/data/backups/quanta-{stamp}.db")
try:
    with dst:
        src.backup(dst)      # WAL-safe consistent snapshot
finally:
    dst.close(); src.close()
print(f"backed up to backups/quanta-{stamp}.db")
PY

# Rotate: keep only the newest $KEEP snapshots.
( ls -1t "$DEST_DIR"/quanta-*.db 2>/dev/null || true ) | tail -n +$((KEEP + 1)) | xargs -r rm -f
echo "kept newest $KEEP backups in $DEST_DIR"
