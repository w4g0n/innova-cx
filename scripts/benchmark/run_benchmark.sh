#!/usr/bin/env bash
# =============================================================================
# run_benchmark.sh — Chatbot LLM Benchmark Orchestrator
# =============================================================================
# Runs on the GCP VM at /opt/innova-cx.
# Tests the current LLM model (Tier 1 + Tier 2), then downloads and tests
# Qwen2.5-1.5B-Instruct, generates a comparison report, restores the original
# model, and cleans up all test data from the DB.
#
# Usage:
#   cd /opt/innova-cx
#   bash scripts/benchmark/run_benchmark.sh
#
# Requirements:
#   - innovacx-chatbot container must be running (docker compose profile=dev)
#   - innovacx-db container must be running
#   - At least 4GB free disk space for Qwen model download
#   - HF_TOKEN env var or internet access to Hugging Face
# =============================================================================

set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
BENCH_DIR="$REPO_DIR/scripts/benchmark"
CONTAINER_BENCH="/tmp/benchmark"
RESULTS_DIR="$BENCH_DIR/results"
CHATBOT_CONTAINER="innovacx-chatbot"
DB_CONTAINER="innovacx-db"
DB_USER="innovacx_user"
DB_NAME="complaints_db"
QWEN_MODEL_ID="Qwen/Qwen2.5-1.5B-Instruct"
QWEN_LOCAL_PATH="/app/hf_cache/qwen2.5-1.5b-instruct"
ENV_FILE="$REPO_DIR/.env"

# Colours
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'

log()   { echo -e "${GREEN}[$(date '+%H:%M:%S')]${NC} $*"; }
warn()  { echo -e "${YELLOW}[$(date '+%H:%M:%S')] WARN:${NC} $*"; }
error() { echo -e "${RED}[$(date '+%H:%M:%S')] ERROR:${NC} $*" >&2; }
die()   { error "$*"; exit 1; }

# =============================================================================
# Step 0 — Preflight checks
# =============================================================================
log "=== PREFLIGHT CHECKS ==="

# Confirm we are in the right directory
[[ -f "$ENV_FILE" ]] || die ".env file not found at $ENV_FILE. Run from /opt/innova-cx."

# Check containers are running
docker ps --format '{{.Names}}' | grep -q "^${CHATBOT_CONTAINER}$" \
    || die "Container $CHATBOT_CONTAINER is not running. Start with: docker compose --profile dev up -d"
docker ps --format '{{.Names}}' | grep -q "^${DB_CONTAINER}$" \
    || die "Container $DB_CONTAINER is not running."

# Check disk space (need ≥ 4GB for Qwen)
AVAIL_GB=$(df -BG "$REPO_DIR" | awk 'NR==2{gsub(/G/,"",$4); print $4}')
if (( AVAIL_GB < 4 )); then
    die "Only ${AVAIL_GB}GB free. Need at least 4GB for Qwen model. Free space with: docker system prune -f"
fi
log "Disk: ${AVAIL_GB}GB available — OK"

# Check chatbot health
HEALTH=$(docker exec "$CHATBOT_CONTAINER" \
    python -c "import urllib.request, json; r=urllib.request.urlopen('http://localhost:8000/health',timeout=5); print(r.read().decode())" 2>/dev/null) \
    || die "Chatbot health check failed. Is the service running?"
log "Chatbot health: $HEALTH"

# Capture current model config (before we change anything)
ORIGINAL_MODEL_PATH=$(docker exec "$CHATBOT_CONTAINER" printenv CHATBOT_MODEL_PATH 2>/dev/null || echo "")
ORIGINAL_USE_MOCK=$(docker exec "$CHATBOT_CONTAINER" printenv CHATBOT_USE_MOCK 2>/dev/null || echo "true")
log "Current CHATBOT_MODEL_PATH: '${ORIGINAL_MODEL_PATH}'"
log "Current CHATBOT_USE_MOCK:   '${ORIGINAL_USE_MOCK}'"

if [[ "$ORIGINAL_USE_MOCK" == "true" ]]; then
    warn "CHATBOT_USE_MOCK=true — benchmark will test mock responses, not a real LLM."
    warn "Set CHATBOT_MODEL_PATH and CHATBOT_USE_MOCK=false in .env then restart the chatbot service."
    warn "Continuing anyway (useful for validating the test harness)."
fi

# Get test customer user_id from DB
CUSTOMER_ID=$(docker exec "$DB_CONTAINER" \
    psql -U "$DB_USER" -d "$DB_NAME" -t -c \
    "SELECT id FROM users WHERE email='customer1@innova.cx' LIMIT 1;" 2>/dev/null | tr -d ' \n')
[[ -n "$CUSTOMER_ID" ]] || die "Could not find customer1@innova.cx in the DB. Check seed data."
log "Test user ID: $CUSTOMER_ID"

# Create results dir
mkdir -p "$RESULTS_DIR"

# =============================================================================
# Step 1 — Copy benchmark scripts into container
# =============================================================================
log "=== COPYING BENCHMARK SCRIPTS TO CONTAINER ==="
docker exec "$CHATBOT_CONTAINER" mkdir -p "$CONTAINER_BENCH"
docker cp "$BENCH_DIR/benchmark_llm.py" "${CHATBOT_CONTAINER}:${CONTAINER_BENCH}/benchmark_llm.py"
docker cp "$BENCH_DIR/test_cases.json"  "${CHATBOT_CONTAINER}:${CONTAINER_BENCH}/test_cases.json"
log "Scripts copied to ${CHATBOT_CONTAINER}:${CONTAINER_BENCH}"

# =============================================================================
# Helper: wait_for_health
# =============================================================================
wait_for_health() {
    local max_wait=120
    local elapsed=0
    local interval=5
    log "Waiting for chatbot service to be healthy (max ${max_wait}s) ..."
    while (( elapsed < max_wait )); do
        if docker exec "$CHATBOT_CONTAINER" \
            python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health',timeout=5)" \
            > /dev/null 2>&1; then
            log "Chatbot is healthy."
            return 0
        fi
        sleep $interval
        elapsed=$(( elapsed + interval ))
        echo -n "."
    done
    echo ""
    die "Chatbot did not become healthy within ${max_wait}s."
}

# =============================================================================
# Helper: run_tier1
# =============================================================================
run_tier1() {
    local label="$1"
    local output_container="${CONTAINER_BENCH}/results_${label}.json"
    local output_host="${RESULTS_DIR}/results_${label}.json"
    log "--- Tier 1: ${label} ---"
    docker exec -e PYTHONPATH=/app "$CHATBOT_CONTAINER" \
        python "${CONTAINER_BENCH}/benchmark_llm.py" \
        --test-cases "${CONTAINER_BENCH}/test_cases.json" \
        --output "$output_container"
    docker cp "${CHATBOT_CONTAINER}:${output_container}" "$output_host"
    log "Tier 1 results saved to $output_host"
}

# =============================================================================
# Helper: run_tier2
# =============================================================================
run_tier2() {
    local label="$1"
    local output_host="${RESULTS_DIR}/e2e_${label}.json"
    log "--- Tier 2 E2E: ${label} ---"
    python3 "$BENCH_DIR/e2e_smoke.py" \
        --user-id "$CUSTOMER_ID" \
        --base-url "http://localhost:8001" \
        --output "$output_host" \
        --timeout 180 || warn "Some E2E scenarios failed for ${label} — check ${output_host}"
    log "Tier 2 results saved to $output_host"
}

# =============================================================================
# Step 2 — Run benchmarks against CURRENT model
# =============================================================================
log "=== STEP 2: BENCHMARK CURRENT MODEL ==="
run_tier1 "current"
run_tier2 "current"

# =============================================================================
# Step 3 — Download Qwen2.5-1.5B-Instruct
# =============================================================================
log "=== STEP 3: DOWNLOAD QWEN MODEL ==="

# Check if already downloaded
QWEN_EXISTS=$(docker exec "$CHATBOT_CONTAINER" \
    python -c "from pathlib import Path; print('yes' if (Path('${QWEN_LOCAL_PATH}')/'config.json').exists() else 'no')" 2>/dev/null || echo "no")

if [[ "$QWEN_EXISTS" == "yes" ]]; then
    log "Qwen model already at ${QWEN_LOCAL_PATH} — skipping download."
else
    log "Downloading ${QWEN_MODEL_ID} to ${QWEN_LOCAL_PATH} inside container ..."
    log "This may take 5-15 minutes depending on network speed ..."
    docker exec "$CHATBOT_CONTAINER" python3 -c "
from huggingface_hub import snapshot_download
import sys
print('Downloading ${QWEN_MODEL_ID} ...', flush=True)
snapshot_download(
    '${QWEN_MODEL_ID}',
    local_dir='${QWEN_LOCAL_PATH}',
    ignore_patterns=['*.gguf', '*.bin'],   # prefer safetensors
)
print('Download complete.', flush=True)
"
    log "Qwen download complete."
fi

# Verify config.json exists
docker exec "$CHATBOT_CONTAINER" \
    python -c "
from pathlib import Path
p = Path('${QWEN_LOCAL_PATH}') / 'config.json'
assert p.exists(), f'config.json not found at {p}'
print('config.json verified at ${QWEN_LOCAL_PATH}')
" || die "Qwen model directory is missing config.json — download may have failed."

# =============================================================================
# Step 4 — Update .env and restart chatbot with Qwen
# =============================================================================
log "=== STEP 4: SWITCH TO QWEN ==="
log "Backing up .env ..."
cp "$ENV_FILE" "${ENV_FILE}.backup.$(date +%Y%m%d_%H%M%S)"

log "Updating .env for Qwen ..."
# Use Python for safe line-by-line env update (handles missing keys gracefully)
python3 - <<'PYEOF'
import re, sys
env_file = "/opt/innova-cx/.env"
qwen_path = "/app/hf_cache/qwen2.5-1.5b-instruct"

with open(env_file) as f:
    lines = f.readlines()

updated = []
found_model = found_mock = False
for line in lines:
    if re.match(r'^\s*CHATBOT_MODEL_PATH\s*=', line):
        updated.append(f"CHATBOT_MODEL_PATH={qwen_path}\n")
        found_model = True
    elif re.match(r'^\s*CHATBOT_USE_MOCK\s*=', line):
        updated.append("CHATBOT_USE_MOCK=false\n")
        found_mock = True
    else:
        updated.append(line)

if not found_model:
    updated.append(f"CHATBOT_MODEL_PATH={qwen_path}\n")
if not found_mock:
    updated.append("CHATBOT_USE_MOCK=false\n")

with open(env_file, "w") as f:
    f.writelines(updated)
print(f"Updated .env: CHATBOT_MODEL_PATH={qwen_path}, CHATBOT_USE_MOCK=false")
PYEOF

log "Restarting chatbot with Qwen ..."
cd "$REPO_DIR" && docker compose --profile dev restart chatbot
wait_for_health

# Verify Qwen loaded
DIAG=$(docker exec "$CHATBOT_CONTAINER" \
    python -c "from core.llm import get_llm_diagnostics; import json; print(json.dumps(get_llm_diagnostics()))" \
    2>/dev/null)
log "Post-restart LLM diagnostics: $DIAG"

# =============================================================================
# Step 5 — Run benchmarks against Qwen
# =============================================================================
log "=== STEP 5: BENCHMARK QWEN ==="
run_tier1 "qwen"
run_tier2 "qwen"

# =============================================================================
# Step 6 — Generate comparison report
# =============================================================================
log "=== STEP 6: GENERATING COMPARISON REPORT ==="
REPORT_PATH="$RESULTS_DIR/comparison_report.txt"
python3 "$BENCH_DIR/compare_results.py" \
    --tier1-a "$RESULTS_DIR/results_current.json" \
    --tier1-b "$RESULTS_DIR/results_qwen.json" \
    --tier2-a "$RESULTS_DIR/e2e_current.json" \
    --tier2-b "$RESULTS_DIR/e2e_qwen.json" \
    --labels  "current" "qwen2.5-1.5b" \
    --output  "$REPORT_PATH"
log "Comparison report saved to $REPORT_PATH"

# =============================================================================
# Step 7 — Restore original model
# =============================================================================
log "=== STEP 7: RESTORING ORIGINAL MODEL ==="
python3 - <<PYEOF
import re, sys
env_file = "/opt/innova-cx/.env"
original_path = """${ORIGINAL_MODEL_PATH}"""
original_mock = """${ORIGINAL_USE_MOCK}"""

with open(env_file) as f:
    lines = f.readlines()

updated = []
found_model = found_mock = False
for line in lines:
    if re.match(r'^\s*CHATBOT_MODEL_PATH\s*=', line):
        updated.append(f"CHATBOT_MODEL_PATH={original_path}\n")
        found_model = True
    elif re.match(r'^\s*CHATBOT_USE_MOCK\s*=', line):
        updated.append(f"CHATBOT_USE_MOCK={original_mock}\n")
        found_mock = True
    else:
        updated.append(line)

if not found_model:
    updated.append(f"CHATBOT_MODEL_PATH={original_path}\n")
if not found_mock:
    updated.append(f"CHATBOT_USE_MOCK={original_mock}\n")

with open(env_file, "w") as f:
    f.writelines(updated)
print(f"Restored .env: CHATBOT_MODEL_PATH={original_path}, CHATBOT_USE_MOCK={original_mock}")
PYEOF

log "Restarting chatbot with original model ..."
cd "$REPO_DIR" && docker compose --profile dev restart chatbot
wait_for_health
log "Original model restored and chatbot healthy."

# =============================================================================
# Step 8 — Cleanup test DB data
# =============================================================================
log "=== STEP 8: CLEANING UP TEST DB DATA ==="

# Collect all session IDs from both E2E result files
SESSION_IDS=$(python3 - <<'PYEOF'
import json, sys
results_dir = "/opt/innova-cx/scripts/benchmark/results"
ids = set()
for fname in ["e2e_current.json", "e2e_qwen.json"]:
    try:
        with open(f"{results_dir}/{fname}") as f:
            data = json.load(f)
        ids.update(data.get("session_ids", []))
    except FileNotFoundError:
        pass
if not ids:
    print("")
else:
    # Format as PostgreSQL array literal: {uuid1,uuid2,...}
    print("{" + ",".join(ids) + "}")
PYEOF
)

if [[ -z "$SESSION_IDS" ]]; then
    warn "No session IDs found in E2E results — skipping DB cleanup."
else
    log "Cleaning up ${SESSION_IDS} ..."
    docker exec -i "$DB_CONTAINER" psql -U "$DB_USER" -d "$DB_NAME" \
        -v "session_ids=$SESSION_IDS" \
        < "$BENCH_DIR/cleanup.sql" \
        && log "DB cleanup complete." \
        || warn "DB cleanup encountered an issue — check output above."
fi

# =============================================================================
# Done
# =============================================================================
log "=== BENCHMARK COMPLETE ==="
log ""
log "Results:"
log "  Tier 1 current   : $RESULTS_DIR/results_current.json"
log "  Tier 1 qwen      : $RESULTS_DIR/results_qwen.json"
log "  Tier 2 current   : $RESULTS_DIR/e2e_current.json"
log "  Tier 2 qwen      : $RESULTS_DIR/e2e_qwen.json"
log "  Comparison report: $REPORT_PATH"
log ""
log "To view the report:"
log "  cat $REPORT_PATH"
log ""
log "To copy results to local machine:"
log "  scp -r innovacx-vm:$RESULTS_DIR ./benchmark_results/"
