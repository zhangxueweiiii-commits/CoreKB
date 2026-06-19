#!/usr/bin/env sh
set -eu

BACKUP_DIR="${BACKUP_DIR:-./backups/$(date +%Y%m%d_%H%M%S)}"
UPLOAD_DIR="${UPLOAD_DIR:-./backend/storage/uploads}"
mkdir -p "$BACKUP_DIR/uploads"

if [ -d "$UPLOAD_DIR" ]; then
  tar -czf "$BACKUP_DIR/uploads/uploads.tgz" -C "$UPLOAD_DIR" .
  echo "Uploads backup written to $BACKUP_DIR/uploads/uploads.tgz"
else
  echo "Upload path not found: $UPLOAD_DIR" >&2
  exit 1
fi
