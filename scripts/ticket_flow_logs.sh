#!/usr/bin/env bash
set -euo pipefail

BACKEND_CONTAINER="${BACKEND_CONTAINER:-innovacx-backend}"
ORCH_CONTAINER="${ORCH_CONTAINER:-innovacx-orchestrator}"
FLOW_VIEW="${FLOW_VIEW:-simple}"

SIMPLE_PATTERN="${SIMPLE_PATTERN:-ticket_gate_create_done|customer_ticket_submit|orchestrator_dispatch|orchestrator_ticket_update|department_routing|routing_review_decision|approval_decision|employee_rescore|employee_reroute|manager_rescore|priority_relearn|auto_assign_|Processing text input|STAGE_START|STAGE_ERROR|classifier_decision|feature_decision|priority \\||ticket_status_update|pipeline_done}"
VERBOSE_PATTERN="${VERBOSE_PATTERN:-ticket_gate_|customer_ticket_submit|orchestrator_dispatch|orchestrator_ticket_update|department_routing|routing_review_decision|approval_decision|employee_rescore|employee_reroute|manager_rescore|priority_relearn|auto_assign_|Processing text input|execution_log|STAGE_START|STAGE_OUTPUT|STAGE_ERROR|classifier_decision|sentiment \\||sentiment_combiner|audio_analysis|feature_decision|feature_engineering|priority \\||ticket_status_update|pipeline_done|failed to create initial open ticket}"
PATTERN="${PATTERN:-$SIMPLE_PATTERN}"

if command -v rg >/dev/null 2>&1; then
  FILTER_CMD=(rg --line-buffered -n "$PATTERN")
else
  FILTER_CMD=(grep -E --line-buffered -n "$PATTERN")
fi

backend_format_compact() {
  sed -u -E \
    -e 's/^[0-9]+://' \
    -e 's/^([0-9-]{10} [0-9:,]{12}) \| ([A-Z]+) \| /\1 [\2] /' \
    -e 's/ticket_gate_create_done \| ticket_code=([^ ]+) .*status=([^ ]+) priority=([^ ]+).*/create ticket=\1 status=\2 priority=\3/' \
    -e 's/customer_ticket_submit \| ticket_code=([^ ]+) .* type=([^ ]+) status=([^ ]+) priority=([^ ]+).*/submit ticket=\1 type=\2 status=\3 priority=\4/' \
    -e 's/orchestrator_dispatch \| queued for ticket=([^ ]+)/dispatch queued ticket=\1/' \
    -e 's/orchestrator_dispatch \| accepted for ticket=([^ ]+)/dispatch accepted ticket=\1/' \
    -e 's/orchestrator_ticket_update \| ticket_id=([^ ]+) status=([^ ]+) priority=([^ ]+) asset_type=([^ ]+) department=([^ ]+).*/ticket update=\1 status=\2 priority=\3 asset=\4 dept=\5/' \
    -e 's/department_routing \| ticket=([^ ]+) suggested=([^ ].*) confidence_pct=([0-9.]+) is_confident=([^ ]+) queued=([^ ]+)/routing ticket=\1 suggested=\2 conf=\3% confident=\4 queued=\5/' \
    -e 's/employee_rescore \| ticket=([^ ]+) from=([^ ]+) to=([^ ]+) request=([^ ]+) by=([^ ]+)/rescore request ticket=\1 \2->\3 request=\4 by=\5/' \
    -e 's/employee_reroute \| ticket=([^ ]+) from=([^ ]+) to=([^ ]+) request=([^ ]+)/reroute request ticket=\1 \2->\3 request=\4/' \
    -e 's/approval_decision \| request=([^ ]+) decision=([^ ]+) by=([^ ]+)/approval request=\1 decision=\2 by=\3/' \
    -e 's/routing_review_decision \| review=([^ ]+) decision=([^ ]+) dept=(.*) by=([^ ]+)/routing review=\1 decision=\2 dept=\3 by=\4/'
}

orchestrator_format_compact() {
  sed -u -E \
    -e 's/^[0-9]+://' \
    -e 's/^([0-9:]{8}) \| ([A-Z]+)[[:space:]]+\| /\1 [\2] /' \
    -e 's/execution_log \| agent=([^ ]+) step=([0-9]+) time_ms=([0-9]+).*error=([^ ]+)/stage=\2 agent=\1 ms=\3 error=\4/' \
    -e 's/STAGE_START \| execution_id=([^ ]+) step=([0-9]+) agent=([^ ]+) ticket_id=([^ ]+)/stage \2 \3 ticket=\4/' \
    -e 's/STAGE_ERROR \| execution_id=([^ ]+) step=([0-9]+) agent=([^ ]+) ticket_id=([^ ]+) error=(.*)/error stage=\2 agent=\3 exec=\1 ticket=\4 err=\5/'
}

cleanup() {
  jobs -p | xargs -r kill >/dev/null 2>&1 || true
}
trap cleanup EXIT INT TERM

if [[ "$FLOW_VIEW" == "verbose" ]]; then
  PATTERN="${VERBOSE_PATTERN}"
fi

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
