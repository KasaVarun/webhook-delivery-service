#!/usr/bin/env bash
set -euo pipefail

# Run from a checked-out release on the target host after setting SERVICE_DIR.
SERVICE_DIR="${SERVICE_DIR:-/opt/webhook-delivery-service}"
SERVICE_NAME="${SERVICE_NAME:-webhook-delivery.service}"

python3.11 -m venv "$SERVICE_DIR/.venv"
"$SERVICE_DIR/.venv/bin/pip" install --upgrade pip
"$SERVICE_DIR/.venv/bin/pip" install "$SERVICE_DIR"
sudo install -m 0644 "$SERVICE_DIR/scripts/webhook-delivery.service" "/etc/systemd/system/$SERVICE_NAME"
sudo systemctl daemon-reload
sudo systemctl enable --now "$SERVICE_NAME"
sudo systemctl status "$SERVICE_NAME" --no-pager