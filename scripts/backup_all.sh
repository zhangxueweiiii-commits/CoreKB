#!/usr/bin/env sh
set -eu

BACKUP_DIR="${BACKUP_DIR:-./backups/$(date +%Y%m%d_%H%M%S)}"
export BACKUP_DIR
mkdir -p "$BACKUP_DIR/config"

sh ./scripts/backup_postgres.sh
sh ./scripts/backup_uploads.sh

if [ -n "${QDRANT_STORAGE:-}" ]; then
  sh ./scripts/backup_qdrant.sh
else
  echo "Skipping Qdrant file backup. Set QDRANT_STORAGE when running outside Docker volumes."
fi

cp docker-compose.yml "$BACKUP_DIR/config/docker-compose.yml"
cp .env.example "$BACKUP_DIR/config/.env.example"

echo "Full backup written to $BACKUP_DIR"
