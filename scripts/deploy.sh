#!/usr/bin/env bash
# Safe on-server deploy: backup → git pull --ff-only → migrate → collectstatic → restart.
# Never force-pushes, never drops DB, never uses git reset --hard.
#
# Usage (on the VPS):
#   ./scripts/deploy.sh --dry-run          # show steps only
#   ./scripts/deploy.sh --confirm          # real deploy (runs backup first)
#   ./scripts/deploy.sh --confirm --skip-backup   # only if you JUST backed up
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

DRY_RUN=0
CONFIRM=0
SKIP_BACKUP=0
SKIP_MIGRATE=0
SKIP_STATIC=0
SKIP_RESTART=0

for arg in "$@"; do
  case "$arg" in
    --dry-run) DRY_RUN=1 ;;
    --confirm) CONFIRM=1 ;;
    --skip-backup) SKIP_BACKUP=1 ;;
    --skip-migrate) SKIP_MIGRATE=1 ;;
    --skip-static) SKIP_STATIC=1 ;;
    --skip-restart) SKIP_RESTART=1 ;;
    -h|--help)
      sed -n '2,14p' "$0"
      exit 0
      ;;
    *)
      echo "Unknown option: $arg" >&2
      exit 2
      ;;
  esac
done

if [[ "$DRY_RUN" -eq 0 && "$CONFIRM" -eq 0 ]]; then
  echo "Refusing to deploy without --confirm (or use --dry-run)." >&2
  echo "Example: ./scripts/deploy.sh --dry-run" >&2
  echo "         ./scripts/deploy.sh --confirm" >&2
  exit 2
fi

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
VENV_DIR="${VENV_DIR:-$APP_DIR/venv}"
DJANGO_SETTINGS_MODULE="${DJANGO_SETTINGS_MODULE:-config.settings_prod}"
RESTART_CMD="${RESTART_CMD:-}"

run() {
  if [[ "$DRY_RUN" -eq 1 ]]; then
    echo "[dry-run] $*"
  else
    "$@"
  fi
}

echo "==> Deploy"
echo "    APP_DIR=$APP_DIR"
echo "    SETTINGS=$DJANGO_SETTINGS_MODULE"
echo "    dry_run=$DRY_RUN confirm=$CONFIRM"

# Working tree must be clean of local edits we might overwrite — warn only
if [[ -d "$APP_DIR/.git" ]]; then
  if ! git -C "$APP_DIR" diff --quiet || ! git -C "$APP_DIR" diff --cached --quiet; then
    echo "WARNING: dirty working tree on server. deploy uses pull --ff-only only;" >&2
    echo "         uncommitted files are NOT deleted, but pull may fail." >&2
  fi
fi

# 1) Backup first
if [[ "$SKIP_BACKUP" -eq 1 ]]; then
  echo "==> Skip backup (--skip-backup)"
else
  echo "==> Pre-deploy backup"
  if [[ "$DRY_RUN" -eq 1 ]]; then
    bash "$SCRIPT_DIR/backup.sh" --dry-run
  else
    bash "$SCRIPT_DIR/backup.sh"
  fi
fi

# 2) Fast-forward pull only (never force)
echo "==> git pull --ff-only"
if [[ "$DRY_RUN" -eq 1 ]]; then
  echo "[dry-run] git -C $APP_DIR pull --ff-only"
else
  git -C "$APP_DIR" pull --ff-only
fi

# 3) Dependencies (safe: only installs what's in requirements)
PIP="$VENV_DIR/bin/pip"
PYTHON="$VENV_DIR/bin/python"
if [[ ! -x "$PYTHON" ]]; then
  echo "ERROR: venv python not found at $PYTHON — fix VENV_DIR in ops.env" >&2
  exit 1
fi

echo "==> pip install -r requirements.txt"
if [[ "$DRY_RUN" -eq 1 ]]; then
  echo "[dry-run] $PIP install -r $APP_DIR/requirements.txt"
else
  "$PIP" install -r "$APP_DIR/requirements.txt"
fi

# 4) Migrate (forward only; never fake or reverse)
export DJANGO_SETTINGS_MODULE
if [[ "$SKIP_MIGRATE" -eq 1 ]]; then
  echo "==> Skip migrate"
else
  echo "==> migrate --noinput"
  if [[ "$DRY_RUN" -eq 1 ]]; then
    echo "[dry-run] $PYTHON $APP_DIR/manage.py migrate --noinput"
  else
    "$PYTHON" "$APP_DIR/manage.py" migrate --noinput
  fi
fi

# 5) Static + messages
if [[ "$SKIP_STATIC" -eq 1 ]]; then
  echo "==> Skip collectstatic"
else
  echo "==> collectstatic + compilemessages"
  if [[ "$DRY_RUN" -eq 1 ]]; then
    echo "[dry-run] collectstatic --noinput"
    echo "[dry-run] compilemessages"
  else
    "$PYTHON" "$APP_DIR/manage.py" collectstatic --noinput
    "$PYTHON" "$APP_DIR/manage.py" compilemessages || true
  fi
fi

# 6) Deploy check (non-fatal warnings OK)
echo "==> check --deploy (warnings ok)"
if [[ "$DRY_RUN" -eq 1 ]]; then
  echo "[dry-run] manage.py check --deploy"
else
  "$PYTHON" "$APP_DIR/manage.py" check --deploy || true
fi

# 7) Restart
if [[ "$SKIP_RESTART" -eq 1 ]]; then
  echo "==> Skip restart"
elif [[ -z "$RESTART_CMD" ]]; then
  echo "==> RESTART_CMD empty — app code updated; restart gunicorn/systemd yourself."
  echo "    Set RESTART_CMD in scripts/ops.env when you know the unit name."
else
  echo "==> restart: $RESTART_CMD"
  if [[ "$DRY_RUN" -eq 1 ]]; then
    echo "[dry-run] $RESTART_CMD"
  else
    # shellcheck disable=SC2086
    eval $RESTART_CMD
  fi
fi

echo "==> Deploy finished OK"
if [[ -d "$APP_DIR/.git" && "$DRY_RUN" -eq 0 ]]; then
  git -C "$APP_DIR" log -1 --oneline
fi
