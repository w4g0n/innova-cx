#!/bin/bash
# run_pipeline.sh — Orchestrates labeling + training pipeline
# ============================================================
# Usage:
#   bash run_pipeline.sh
#   bash run_pipeline.sh --dry-run       # test with 10 rows
#   bash run_pipeline.sh --epochs 5      # override training epochs
#   bash run_pipeline.sh --full-run --epochs 3   # explicit uncapped full dataset run

set -eo pipefail  # Exit immediately on any error and propagate failures in pipes
export PYTHONNOUSERSITE=1

# ─────────────────────────────────────────────
# DEFAULTS
# ─────────────────────────────────────────────

INPUT="input.csv"
LABELED="labeled.csv"
MODELS_DIR="models/"
EPOCHS=1
DRY_RUN=""
MAX_COMPLAINTS=200
FULL_RUN=""

# ─────────────────────────────────────────────
# PARSE ARGS
# ─────────────────────────────────────────────

while [[ "$#" -gt 0 ]]; do
    case $1 in
        --dry-run) DRY_RUN="--dry-run" ;;
        --epochs)  EPOCHS="$2"; shift ;;
        --input)   INPUT="$2";  shift ;;
        --max-complaints) MAX_COMPLAINTS="$2"; shift ;;
        --full-run) FULL_RUN="1" ;;
        *) echo "Unknown arg: $1"; exit 1 ;;
    esac
    shift
done

# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────

log() { echo "[$(date '+%H:%M:%S')] $1"; }

check_file() {
    if [ ! -f "$1" ]; then
        echo "ERROR: Required file not found: $1"
        exit 1
    fi
}

# ─────────────────────────────────────────────
# PRE-FLIGHT
# ─────────────────────────────────────────────

log "Starting pipeline"
log "Input        : $INPUT"
log "Labeled      : $LABELED"
log "Models dir   : $MODELS_DIR"
log "Epochs       : $EPOCHS"
[ -n "$DRY_RUN" ] && log "Mode         : DRY RUN"
if [ -n "$FULL_RUN" ]; then
    log "Run mode     : FULL RUN (uncapped complaints)"
else
    log "Run mode     : SAFE RUN (capped complaints)"
    log "Max complaints: $MAX_COMPLAINTS"
fi

check_file "$INPUT"

if [ -n "${PYTHON_BIN:-}" ]; then
    if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
        log "ERROR: PYTHON_BIN is set but not found: $PYTHON_BIN"
        exit 1
    fi
else
    if command -v python3 >/dev/null 2>&1; then
        PYTHON_BIN="python3"
    elif command -v python >/dev/null 2>&1; then
        PYTHON_BIN="python"
    else
        log "ERROR: No Python interpreter found. Install python3 or python."
        exit 1
    fi
fi
log "Python       : $PYTHON_BIN"

mkdir -p "$MODELS_DIR"
mkdir -p "logs/"

# ─────────────────────────────────────────────
# STEP 1 — LABEL
# ─────────────────────────────────────────────

log "────────────────────────────────────"
log "STEP 1: Labeling with Phi-4-mini"
log "────────────────────────────────────"

LABEL_CMD=("$PYTHON_BIN" "label.py" "--input" "$INPUT" "--output" "$LABELED")
[ -n "$DRY_RUN" ] && LABEL_CMD+=("$DRY_RUN")
if [ -z "$FULL_RUN" ]; then
    LABEL_CMD+=("--max-complaints" "$MAX_COMPLAINTS")
fi

"${LABEL_CMD[@]}" 2>&1 | tee logs/label.log

if [ ! -f "$LABELED" ]; then
    log "ERROR: label.py did not produce $LABELED — aborting"
    exit 1
fi

LABELED_ROWS=$("$PYTHON_BIN" -c "import pandas as pd; df=pd.read_csv('$LABELED'); print(len(df[df.ticket_type=='complaint']))")
log "Labeled $LABELED_ROWS complaint rows"

if [ "$LABELED_ROWS" -lt 10 ]; then
    log "ERROR: Too few labeled rows ($LABELED_ROWS) — check label.py output"
    exit 1
fi

if [ -n "$DRY_RUN" ]; then
    log "DRY RUN complete: training skipped by design"
    log "  Labeled CSV       : $LABELED"
    log "  Logs              : logs/"
    exit 0
fi

# ─────────────────────────────────────────────
# STEP 2 — TRAIN
# ─────────────────────────────────────────────

log "────────────────────────────────────"
log "STEP 2: Fine-tuning DeBERTa"
log "────────────────────────────────────"

"$PYTHON_BIN" train.py \
    --input      "$LABELED" \
    --output-dir "$MODELS_DIR" \
    --epochs     "$EPOCHS" \
    2>&1 | tee logs/train.log

# ─────────────────────────────────────────────
# DONE
# ─────────────────────────────────────────────

log "────────────────────────────────────"
log "Pipeline complete"
log "  Labeled CSV       : $LABELED"
log "  Models            : $MODELS_DIR"
log "  Evaluation report : ${MODELS_DIR}evaluation_report.json"
log "  Logs              : logs/"
log "────────────────────────────────────"
