#!/usr/bin/env sh
set -eu

BACKUP_DIR="${BACKUP_DIR:-./backups/$(date +%Y%m%d_%H%M%S)}"
QDRANT_STORAGE="${QDRANT_STORAGE:-./qdrant_storage}"
mkdir -p "$BACKUP_DIR/qdrant"

if [ -d "$QDRANT_STORAGE" ]; then
  tar -czf "$BACKUP_DIR/qdrant/qdrant_storage.tgz" -C "$QDRANT_STORAGE" .
  echo "Qdrant storage backup written to $BACKUP_DIR/qdrant/qdrant_storage.tgz"
else
  echo "Qdrant storage path not found: $QDRANT_STORAGE" >&2
  exit 1
fi
