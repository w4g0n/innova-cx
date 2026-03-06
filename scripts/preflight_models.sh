#!/usr/bin/env bash
set -euo pipefail

echo "[1] compose yaml"
docker compose config >/dev/null

echo "[2] required host model files"
test -f /opt/innova-models/subjectgeneration/flan-t5-small/config.json
test -f /opt/innova-models/suggestedresolution/flan-t5-small/config.json
test -f /opt/innova-models/departmentrouting/deberta-v3-base-mnli-fever-anli/config.json
test -f /opt/innova-models/chatbot/config.json

echo "[3] containers"
docker compose up -d --build backend orchestrator chatbot >/dev/null

echo "[4] orchestrator mount"
docker inspect innovacx-orchestrator --format '{{json .Mounts}}' | grep -q '"/opt/innova-models"'

echo "[5] health modes"
H="$(curl -sS http://localhost:8004/health)"
echo "$H" | jq -e '.subject_generator_mode=="model"' >/dev/null
echo "$H" | jq -e '.sentiment_mode=="model"' >/dev/null
echo "$H" | jq -e '.department_router_mode=="model"' >/dev/null

echo "OK: preflight passed"
