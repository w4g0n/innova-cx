#!/usr/bin/env bash
set -euo pipefail

BACKEND_CONTAINER="${BACKEND_CONTAINER:-innovacx-backend}"
ORCH_CONTAINER="${ORCH_CONTAINER:-innovacx-orchestrator}"
FLOW_VIEW="${FLOW_VIEW:-compact}"

PATTERN="${PATTERN:-ticket_gate_|customer_ticket_submit|orchestrator_dispatch|orchestrator_ticket_update|department_routing|routing_review_decision|auto_assign_|Processing text input|execution_log|pipeline_done|failed to create initial open ticket|ticket_status_update}"

if command -v rg >/dev/null 2>&1; then
  FILTER_CMD=(rg --line-buffered -n "$PATTERN")
else
  FILTER_CMD=(grep -E --line-buffered -n "$PATTERN")
fi

backend_format_compact() {
  sed -u -E \
    -e 's/^[0-9]+://' \
    -e 's/^([0-9-]{10} [0-9:,]{12}) \| ([A-Z]+) \| /\1 [\2] /'
}

orchestrator_format_compact() {
  sed -u -E \
    -e 's/^[0-9]+://' \
    -e 's/^([0-9:]{8}) \| ([A-Z]+)[[:space:]]+\| /\1 [\2] /' \
    -e 's/execution_log \| agent=([^ ]+) step=([0-9]+) time_ms=([0-9]+).*error=([^ ]+)/stage=\2 agent=\1 ms=\3 error=\4/'
}

cleanup() {
  jobs -p | xargs -r kill >/dev/null 2>&1 || true
}
trap cleanup EXIT INT TERM

if [[ "$FLOW_VIEW" == "raw" ]]; then
  docker logs -f "$BACKEND_CONTAINER" 2>&1 \
    | "${FILTER_CMD[@]}" \
    | sed -u 's/^/[backend] /' &

  docker logs -f "$ORCH_CONTAINER" 2>&1 \
    | "${FILTER_CMD[@]}" \
    | sed -u 's/^/[orchestrator] /' &
else
  docker logs -f "$BACKEND_CONTAINER" 2>&1 \
    | "${FILTER_CMD[@]}" \
    | backend_format_compact \
    | sed -u 's/^/[backend] /' &

  docker logs -f "$ORCH_CONTAINER" 2>&1 \
    | "${FILTER_CMD[@]}" \
    | orchestrator_format_compact \
    | sed -u 's/^/[orchestrator] /' &
fi

wait
