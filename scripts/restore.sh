#!/usr/bin/env bash
# Restore Postgres (+ optional media) from a backup made by backup.sh.
# DANGEROUS: overwrites the live database. Requires --confirm AND backup path.
#
# Usage:
#   ./scripts/restore.sh --list
#   ./scripts/restore.sh --dry-run /var/backups/hotel-pms/20260924_120000
#   ./scripts/restore.sh --confirm /var/backups/hotel-pms/20260924_120000
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

DRY_RUN=0
CONFIRM=0
LIST=0
BACKUP_PATH=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run) DRY_RUN=1; shift ;;
    --confirm) CONFIRM=1; shift ;;
    --list) LIST=1; shift ;;
    -h|--help)
      sed -n '2,12p' "$0"
      exit 0
      ;;
    *)
      BACKUP_PATH="$1"
      shift
      ;;
  esac
done

load_ops_env() {
  local f
  for f in "$SCRIPT_DIR/ops.env" "$ROOT_DIR/scripts/ops.env"; do
    if [[ -f "$f" ]]; then
      # shellcheck disable=SC1090
      set -a
      source "$f"
      set +a
      return 0
    fi
  done
  echo "Missing scripts/ops.env — copy from scripts/ops.env.example first." >&2
  exit 1
}

load_ops_env

BACKUP_DIR="${BACKUP_DIR:-/var/backups/hotel-pms}"
APP_DIR="${APP_DIR:-$ROOT_DIR}"
POSTGRES_DB="${POSTGRES_DB:-hotel_management}"
POSTGRES_USER="${POSTGRES_USER:-}"
POSTGRES_HOST="${POSTGRES_HOST:-localhost}"
POSTGRES_PORT="${POSTGRES_PORT:-5432}"
MEDIA_DIR="${MEDIA_DIR:-media}"

if [[ "$LIST" -eq 1 ]]; then
  echo "Backups in $BACKUP_DIR:"
  ls -1dt "$BACKUP_DIR"/*/ 2>/dev/null || echo "(none)"
  exit 0
fi

if [[ -z "$BACKUP_PATH" ]]; then
  echo "Usage: $0 --confirm /path/to/backup_dir" >&2
  exit 2
fi

if [[ ! -d "$BACKUP_PATH" ]]; then
  echo "Backup dir not found: $BACKUP_PATH" >&2
  exit 1
fi

DUMP="$BACKUP_PATH/db.dump"
if [[ ! -f "$DUMP" ]]; then
  echo "Missing $DUMP" >&2
  exit 1
fi

if [[ "$DRY_RUN" -eq 0 && "$CONFIRM" -eq 0 ]]; then
  echo "Refusing restore without --confirm (destroys current DB contents)." >&2
  echo "Preview: $0 --dry-run $BACKUP_PATH" >&2
  exit 2
fi

echo "==> Restore from $BACKUP_PATH"
echo "    TARGET DB=$POSTGRES_DB @ $POSTGRES_HOST:$POSTGRES_PORT"
echo "    THIS OVERWRITES LIVE DATA"

export PGHOST="$POSTGRES_HOST"
export PGPORT="$POSTGRES_PORT"
if [[ -n "${POSTGRES_PASSWORD:-}" ]]; then
  export PGPASSWORD="$POSTGRES_PASSWORD"
fi

RESTORE_CMD=(pg_restore --clean --if-exists --no-owner --no-acl --dbname="$POSTGRES_DB")
if [[ -n "$POSTGRES_USER" ]]; then
  RESTORE_CMD+=(--username="$POSTGRES_USER")
fi
RESTORE_CMD+=("$DUMP")

if [[ "$DRY_RUN" -eq 1 ]]; then
  echo "[dry-run] ${RESTORE_CMD[*]}"
else
  echo "==> pg_restore (clean)"
  if command -v pg_restore >/dev/null 2>&1; then
    "${RESTORE_CMD[@]}"
  else
    sudo -u postgres pg_restore --clean --if-exists --no-owner --no-acl --dbname="$POSTGRES_DB" "$DUMP"
  fi
fi

MEDIA_TAR="$BACKUP_PATH/media.tar.gz"
if [[ -f "$MEDIA_TAR" ]]; then
  echo "==> restore media → $APP_DIR/$MEDIA_DIR"
  if [[ "$DRY_RUN" -eq 1 ]]; then
    echo "[dry-run] tar -xzf $MEDIA_TAR -C $APP_DIR"
  else
    # Extract into APP_DIR; archive contains MEDIA_DIR/ prefix
    tar -xzf "$MEDIA_TAR" -C "$APP_DIR"
  fi
else
  echo "==> No media.tar.gz in backup (skip)"
fi

echo "==> Restore finished. Restart the app (gunicorn) if needed."
