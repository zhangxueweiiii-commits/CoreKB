#!/usr/bin/env sh
set -eu

: "${BACKUP_FILE:?Set BACKUP_FILE to the .dump file path}"
: "${POSTGRES_USER:=corekb}"
: "${POSTGRES_DB:=corekb}"
: "${POSTGRES_HOST:=postgres}"
: "${POSTGRES_PORT:=5432}"

pg_restore -h "$POSTGRES_HOST" -p "$POSTGRES_PORT" -U "$POSTGRES_USER" -d "$POSTGRES_DB" --clean --if-exists "$BACKUP_FILE"

echo "PostgreSQL restored from $BACKUP_FILE"
