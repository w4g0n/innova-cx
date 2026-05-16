#!/bin/bash
# One-time setup: installs weekly docker prune timer on the GCP VM
# Usage: sudo bash scripts/maintenance/install-maintenance.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

cp "$SCRIPT_DIR/docker-prune.service" /etc/systemd/system/docker-prune.service
cp "$SCRIPT_DIR/docker-prune.timer"   /etc/systemd/system/docker-prune.timer

systemctl daemon-reload
systemctl enable docker-prune.timer
systemctl start docker-prune.timer

echo "Installed. Next scheduled run:"
systemctl list-timers docker-prune.timer --no-pager
