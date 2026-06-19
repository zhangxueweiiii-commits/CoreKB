#!/usr/bin/env sh
set -eu

BACKUP_FILE="${1:-}"
TMP_DIR=""
RESULT_FILE="restore_check_result.json"

json_result() {
  python - "$RESULT_FILE" "$BACKUP_FILE" "$CHECKSUM_OK" "$POSTGRES_RESTORE_OK" "$UPLOADS_OK" "$QDRANT_BACKUP_OK" "$OVERALL_STATUS" "$ERROR_MESSAGE" <<'PY'
import json
import sys
from pathlib import Path

result_file, backup_file, checksum_ok, postgres_ok, uploads_ok, qdrant_ok, overall, error = sys.argv[1:]
payload = {
    "backup_file": backup_file,
    "checksum_ok": checksum_ok == "true",
    "postgres_restore_ok": postgres_ok == "true",
    "uploads_ok": uploads_ok == "true",
    "qdrant_backup_ok": qdrant_ok == "true",
    "overall_status": overall,
    "error_message": error or None,
}
Path(result_file).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(payload, ensure_ascii=False))
PY
}

fail() {
  ERROR_MESSAGE="$1"
  OVERALL_STATUS="failed"
  json_result
  [ -n "$TMP_DIR" ] && [ -d "$TMP_DIR" ] && rm -rf "$TMP_DIR"
  exit 1
}

CHECKSUM_OK=false
POSTGRES_RESTORE_OK=false
UPLOADS_OK=false
QDRANT_BACKUP_OK=false
OVERALL_STATUS=failed
ERROR_MESSAGE=""

[ -n "$BACKUP_FILE" ] || fail "Usage: scripts/dr_restore_check.sh /path/to/backup_all.tgz"
[ -f "$BACKUP_FILE" ] || fail "Backup file not found: $BACKUP_FILE"

TMP_DIR="$(mktemp -d)"

ACTUAL_CHECKSUM="$(python - "$BACKUP_FILE" <<'PY'
import hashlib
import sys
from pathlib import Path

digest = hashlib.sha256()
with Path(sys.argv[1]).open("rb") as handle:
    for block in iter(lambda: handle.read(1024 * 1024), b""):
        digest.update(block)
print(digest.hexdigest())
PY
)"

if [ -f "$BACKUP_FILE.sha256" ]; then
  EXPECTED_CHECKSUM="$(awk '{print $1}' "$BACKUP_FILE.sha256")"
  [ "$ACTUAL_CHECKSUM" = "$EXPECTED_CHECKSUM" ] || fail "Checksum mismatch"
fi
CHECKSUM_OK=true

tar -xzf "$BACKUP_FILE" -C "$TMP_DIR" || fail "Failed to extract backup archive"
RESTORE_ROOT="$(find "$TMP_DIR" -mindepth 1 -maxdepth 1 -type d | head -n 1)"
[ -n "$RESTORE_ROOT" ] || fail "Backup archive does not contain restore directory"

if [ -f "$RESTORE_ROOT/uploads.tgz" ]; then
  mkdir -p "$TMP_DIR/uploads_check"
  tar -xzf "$RESTORE_ROOT/uploads.tgz" -C "$TMP_DIR/uploads_check" || fail "Failed to extract uploads backup"
  [ -d "$TMP_DIR/uploads_check/uploads" ] && UPLOADS_OK=true
fi

[ -f "$RESTORE_ROOT/qdrant.tgz" ] && QDRANT_BACKUP_OK=true

if [ -f "$RESTORE_ROOT/postgres.dump" ]; then
  if command -v createdb >/dev/null 2>&1 && command -v pg_restore >/dev/null 2>&1 && command -v dropdb >/dev/null 2>&1; then
    TEST_DB="${DR_TEST_DB_NAME:-corekb_restore_check_$(date +%s)}"
    createdb "$TEST_DB" || fail "Failed to create temporary restore database"
    if pg_restore --dbname "$TEST_DB" "$RESTORE_ROOT/postgres.dump"; then
      POSTGRES_RESTORE_OK=true
    else
      dropdb "$TEST_DB" >/dev/null 2>&1 || true
      fail "Failed to restore PostgreSQL dump into temporary database"
    fi
    dropdb "$TEST_DB" >/dev/null 2>&1 || true
  else
    fail "PostgreSQL client tools not found: createdb/pg_restore/dropdb"
  fi
else
  fail "postgres.dump not found in backup archive"
fi

if [ "$CHECKSUM_OK" = "true" ] && [ "$POSTGRES_RESTORE_OK" = "true" ] && [ "$UPLOADS_OK" = "true" ] && [ "$QDRANT_BACKUP_OK" = "true" ]; then
  OVERALL_STATUS="passed"
  ERROR_MESSAGE=""
  json_result
  rm -rf "$TMP_DIR"
  exit 0
fi

fail "Restore check failed"
