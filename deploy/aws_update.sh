#!/usr/bin/env bash
set -Eeuo pipefail

# Run in Session Manager. A failed update leaves the service stopped.
APP_DIR="${APP_DIR:-/opt/roostoo}"
ENV_FILE="${ENV_FILE:-/etc/roostoo/roostoo.env}"
export APP_DIR ENV_FILE
if [[ "$(id -u)" -ne 0 ]]; then
  echo "Run: sudo bash deploy/aws_update.sh" >&2
  exit 1
fi
trap 'echo "Update failed. Inspect the error and service status; preserve the existing ledger." >&2' ERR
cd "$APP_DIR"
systemctl stop roostoo-bot.service
if [[ "${1:-}" != "--apply" ]]; then
  BRANCH="$(git symbolic-ref --short HEAD)"
  git pull --ff-only origin "$BRANCH"
  # Execute the freshly pulled updater, not the old shell script.
  exec bash "$APP_DIR/deploy/aws_update.sh" --apply
fi
set -a
source "$ENV_FILE"
set +a
CONFIG_PATH="${ROOSTOO_CONFIG:-$APP_DIR/config/live_candidate.json}"
STATE_PATH="${ROOSTOO_STATE:-$APP_DIR/runs/aws/state.json}"
UNIVERSE_PATH="${ROOSTOO_UNIVERSE_CONFIG:-$APP_DIR/config/universe-50.json}"
echo "Updating config=$CONFIG_PATH state=$STATE_PATH"
"$APP_DIR/.venv/bin/python" -m roostoo.migrate_state \
  --config "$CONFIG_PATH" --state "$STATE_PATH" --universe "$UNIVERSE_PATH"
# Regenerate the unit from the env file without pulling a different revision.
ROOSTOO_SKIP_PULL=1 bash "$APP_DIR/deploy/aws_start.sh"
