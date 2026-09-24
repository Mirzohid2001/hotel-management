#!/usr/bin/env bash
# Safe on-server backup: Postgres dump + media archive.
# Does NOT drop DB, stop services, or touch git.
#
# Usage (on the VPS, from app root or anywhere):
#   ./scripts/backup.sh
#   ./scripts/backup.sh --dry-run
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

DRY_RUN=0
for arg in "$@"; do
  case "$arg" in
    --dry-run) DRY_RUN=1 ;;
    -h|--help)
      sed -n '2,12p' "$0"
      exit 0
      ;;
    *)
      echo "Unknown option: $arg" >&2
      exit 2
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

APP_DIR="${APP_DIR:-$ROOT_DIR}"
BACKUP_DIR="${BACKUP_DIR:-/var/backups/hotel-pms}"
KEEP_BACKUPS="${KEEP_BACKUPS:-14}"
POSTGRES_DB="${POSTGRES_DB:-hotel_management}"
POSTGRES_USER="${POSTGRES_USER:-}"
POSTGRES_HOST="${POSTGRES_HOST:-localhost}"
POSTGRES_PORT="${POSTGRES_PORT:-5432}"
MEDIA_DIR="${MEDIA_DIR:-media}"

STAMP="$(date +%Y%m%d_%H%M%S)"
DEST="$BACKUP_DIR/$STAMP"
MEDIA_SRC="$APP_DIR/$MEDIA_DIR"

run() {
  if [[ "$DRY_RUN" -eq 1 ]]; then
    echo "[dry-run] $*"
  else
    "$@"
  fi
}

echo "==> Backup start ($STAMP)"
echo "    APP_DIR=$APP_DIR"
echo "    DEST=$DEST"

run mkdir -p "$DEST"

# --- Postgres ---
DUMP_FILE="$DEST/db.dump"
echo "==> Postgres dump → $DUMP_FILE"
export PGHOST="$POSTGRES_HOST"
export PGPORT="$POSTGRES_PORT"
if [[ -n "${POSTGRES_PASSWORD:-}" ]]; then
  export PGPASSWORD="$POSTGRES_PASSWORD"
fi

PG_DUMP_ARGS=(pg_dump --format=custom --file="$DUMP_FILE" --no-owner --no-acl)
if [[ -n "$POSTGRES_USER" ]]; then
  PG_DUMP_ARGS+=(--username="$POSTGRES_USER")
fi
PG_DUMP_ARGS+=("$POSTGRES_DB")

if [[ "$DRY_RUN" -eq 1 ]]; then
  echo "[dry-run] ${PG_DUMP_ARGS[*]}"
else
  if command -v pg_dump >/dev/null 2>&1; then
    "${PG_DUMP_ARGS[@]}"
  elif command -v sudo >/dev/null 2>&1; then
    # Common Contabo layout: dump as postgres OS user (peer auth)
    sudo -u postgres pg_dump --format=custom --file="$DUMP_FILE" --no-owner --no-acl "$POSTGRES_DB"
  else
    echo "pg_dump not found" >&2
    exit 1
  fi
  # quick integrity: file non-empty
  if [[ ! -s "$DUMP_FILE" ]]; then
    echo "ERROR: dump file empty" >&2
    exit 1
  fi
fi

# --- Media ---
MEDIA_TAR="$DEST/media.tar.gz"
if [[ -d "$MEDIA_SRC" ]]; then
  echo "==> Media archive → $MEDIA_TAR"
  run tar -czf "$MEDIA_TAR" -C "$APP_DIR" "$MEDIA_DIR"
else
  echo "==> No media dir at $MEDIA_SRC (skip)"
  if [[ "$DRY_RUN" -eq 0 ]]; then
    echo "no-media" >"$DEST/media.skipped"
  fi
fi

# --- Meta (no secrets) ---
META="$DEST/meta.txt"
if [[ "$DRY_RUN" -eq 1 ]]; then
  echo "[dry-run] write $META"
else
  {
    echo "stamp=$STAMP"
    echo "host=$(hostname 2>/dev/null || true)"
    echo "app_dir=$APP_DIR"
    echo "db=$POSTGRES_DB"
    if [[ -d "$APP_DIR/.git" ]]; then
      echo "git_head=$(git -C "$APP_DIR" rev-parse --short HEAD 2>/dev/null || true)"
      echo "git_branch=$(git -C "$APP_DIR" rev-parse --abbrev-ref HEAD 2>/dev/null || true)"
    fi
  } >"$META"
fi

# --- Retention ---
echo "==> Retention: keep last $KEEP_BACKUPS backups in $BACKUP_DIR"
if [[ "$DRY_RUN" -eq 1 ]]; then
  echo "[dry-run] prune old backup dirs"
else
  # shellcheck disable=SC2012
  ls -1dt "$BACKUP_DIR"/*/ 2>/dev/null | tail -n +"$((KEEP_BACKUPS + 1))" | while read -r old; do
    echo "    prune $old"
    rm -rf "$old"
  done
fi

echo "==> Backup OK: $DEST"
if [[ "$DRY_RUN" -eq 0 ]]; then
  du -sh "$DEST"/* 2>/dev/null || true
fi
