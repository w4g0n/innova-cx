#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/innova-cx}"
PROFILE="${PROFILE:-live}"

cd "${APP_DIR}"

if [[ ! -f ".env" ]]; then
  echo "[gcp-live-up] Missing ${APP_DIR}/.env" >&2
  exit 1
fi

echo "[gcp-live-up] $(date -u '+%Y-%m-%dT%H:%M:%SZ') starting ${PROFILE} stack from ${APP_DIR}"

docker compose --profile "${PROFILE}" up -d --build --remove-orphans

echo "[gcp-live-up] stack is up"
