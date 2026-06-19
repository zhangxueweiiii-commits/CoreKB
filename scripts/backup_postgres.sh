#!/usr/bin/env sh
set -eu

BACKUP_DIR="${BACKUP_DIR:-./backups/$(date +%Y%m%d_%H%M%S)}"
mkdir -p "$BACKUP_DIR/postgres"

: "${POSTGRES_USER:=corekb}"
: "${POSTGRES_DB:=corekb}"
: "${POSTGRES_HOST:=postgres}"
: "${POSTGRES_PORT:=5432}"

pg_dump -h "$POSTGRES_HOST" -p "$POSTGRES_PORT" -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc \
  -f "$BACKUP_DIR/postgres/corekb.dump"

echo "PostgreSQL backup written to $BACKUP_DIR/postgres/corekb.dump"
