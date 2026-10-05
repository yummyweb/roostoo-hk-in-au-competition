#!/usr/bin/env bash
set -Eeuo pipefail

# Idempotent Amazon Linux EC2 installer. It installs the repository and a locked
# systemd runner. Live orders require ROOSTOO_LIVE=1 in the root-owned
# env file; the default is paper mode. Credentials are deliberately read from
# that host-only file and are never written into the repository.
REPO_URL="${REPO_URL:-https://github.com/yummyweb/roostoo-hk-in-au-competition.git}"
APP_DIR="${APP_DIR:-/opt/roostoo}"
ENV_DIR="${ENV_DIR:-/etc/roostoo}"
ENV_FILE="${ENV_FILE:-$ENV_DIR/roostoo.env}"
SERVICE="roostoo-bot.service"

if [[ "$(id -u)" -ne 0 ]]; then
  echo "Run as root (for example: sudo bash deploy/aws_start.sh)." >&2
  exit 1
fi

if ! command -v dnf >/dev/null 2>&1; then
  echo "dnf is required; this installer targets the hackathon Amazon Linux image." >&2
  exit 1
fi
dnf install -y ca-certificates git python3 python3-pip

if [[ -d "$APP_DIR/.git" ]]; then
  git -C "$APP_DIR" remote set-url origin "$REPO_URL"
  git -C "$APP_DIR" fetch --prune origin
  git -C "$APP_DIR" pull --ff-only origin "$(git -C "$APP_DIR" symbolic-ref --short HEAD 2>/dev/null || echo main)"
else
  install -d -m 0755 "$(dirname "$APP_DIR")"
  git clone "$REPO_URL" "$APP_DIR"
fi

python3 -m venv "$APP_DIR/.venv"
"$APP_DIR/.venv/bin/python" -m pip install --upgrade pip setuptools wheel

install -d -m 0750 "$ENV_DIR" "$APP_DIR/runs/aws"
if [[ ! -f "$ENV_FILE" ]]; then
  install -m 0600 "$APP_DIR/deploy/roostoo.env.example" "$ENV_FILE"
  echo "Created $ENV_FILE. Edit it with the Roostoo credentials, then rerun this script." >&2
  exit 2
fi
chown root:root "$ENV_FILE"
chmod 0600 "$ENV_FILE"

# Environment values are read by systemd and by roostoo.bot. Only an explicit
# value of 1 enables POST /place_order; all other values remain paper mode.
set -a
# shellcheck disable=SC1090
source "$ENV_FILE"
set +a
if [[ "${ROOSTOO_LIVE:-0}" == "1" ]]; then
  [[ -n "${ROOSTOO_API_KEY:-}" && -n "${ROOSTOO_API_SECRET:-}" ]] || {
    echo "ROOSTOO_LIVE=1 requires ROOSTOO_API_KEY and ROOSTOO_API_SECRET in $ENV_FILE" >&2
    exit 1
  }
fi
CONFIG_PATH="${ROOSTOO_CONFIG:-$APP_DIR/config/live_candidate.json}"
UNIVERSE_PATH="${ROOSTOO_UNIVERSE_CONFIG:-$APP_DIR/config/universe-50.json}"
STATE_PATH="${ROOSTOO_STATE:-$APP_DIR/runs/aws/state.json}"

cat > "/etc/systemd/system/$SERVICE" <<UNIT
[Unit]
Description=Roostoo competition bot (explicit paper/live mode)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=root
WorkingDirectory=$APP_DIR
EnvironmentFile=$ENV_FILE
Environment=PYTHONUNBUFFERED=1
Environment=ROOSTOO_CONFIG=$CONFIG_PATH
Environment=ROOSTOO_UNIVERSE_CONFIG=$UNIVERSE_PATH
ExecStart=$APP_DIR/.venv/bin/python -m roostoo.bot --config $CONFIG_PATH --state $STATE_PATH
Restart=on-failure
RestartSec=30
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ReadWritePaths=$APP_DIR/runs

[Install]
WantedBy=multi-user.target
UNIT

systemctl daemon-reload
systemctl enable "$SERVICE"
# enable --now leaves an already running process on its old code/environment.
systemctl restart "$SERVICE"
systemctl --no-pager --full status "$SERVICE"
echo "Restarted $SERVICE with ROOSTOO_LIVE=${ROOSTOO_LIVE:-0}, state=$STATE_PATH. Logs: journalctl -u $SERVICE -f"
