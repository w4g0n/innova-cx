#!/bin/bash
# run_pipeline.sh — Orchestrates labeling + training pipeline
# ============================================================
# Usage:
#   bash run_pipeline.sh
#   bash run_pipeline.sh --dry-run       # test with 10 rows
#   bash run_pipeline.sh --epochs 5      # override training epochs
#   bash run_pipeline.sh --full-run --epochs 3   # explicit uncapped full dataset run
#   bash run_pipeline.sh --full-run --resume-from models/deberta_multitask/model.pt --weighted-safety-loss
#   bash run_pipeline.sh --full-run --run-guarded-predict

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
RESUME_FROM=""
WEIGHTED_SAFETY_LOSS=""
SAFETY_POSITIVE_WEIGHT=""
RUN_GUARDED_PREDICT=""
PREDICT_INPUT=""
PREDICT_OUTPUT="output/predictions_guarded.csv"
SAFETY_THRESHOLD="0.30"
UNCERTAINTY_MARGIN="0.15"

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
        --resume-from) RESUME_FROM="$2"; shift ;;
        --weighted-safety-loss) WEIGHTED_SAFETY_LOSS="1" ;;
        --safety-positive-weight) SAFETY_POSITIVE_WEIGHT="$2"; shift ;;
        --run-guarded-predict) RUN_GUARDED_PREDICT="1" ;;
        --predict-input) PREDICT_INPUT="$2"; shift ;;
        --predict-output) PREDICT_OUTPUT="$2"; shift ;;
        --safety-threshold) SAFETY_THRESHOLD="$2"; shift ;;
        --uncertainty-margin) UNCERTAINTY_MARGIN="$2"; shift ;;
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
if [ -n "$RESUME_FROM" ]; then
    log "Resume from  : $RESUME_FROM"
fi
if [ -n "$WEIGHTED_SAFETY_LOSS" ]; then
    log "Weighted loss: safety_concern enabled"
fi
if [ -n "$RUN_GUARDED_PREDICT" ]; then
    log "Guarded pred : enabled"
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

TRAIN_CMD=(
    "$PYTHON_BIN" train.py
    --input "$LABELED"
    --output-dir "$MODELS_DIR"
    --epochs "$EPOCHS"
)
[ -n "$RESUME_FROM" ] && TRAIN_CMD+=(--resume-from "$RESUME_FROM")
[ -n "$WEIGHTED_SAFETY_LOSS" ] && TRAIN_CMD+=(--weighted-safety-loss)
[ -n "$SAFETY_POSITIVE_WEIGHT" ] && TRAIN_CMD+=(--safety-positive-weight "$SAFETY_POSITIVE_WEIGHT")

"${TRAIN_CMD[@]}" 2>&1 | tee logs/train.log

# ─────────────────────────────────────────────
# STEP 3 — GUARDED PREDICTION (OPTIONAL)
# ─────────────────────────────────────────────

if [ -n "$RUN_GUARDED_PREDICT" ]; then
    log "────────────────────────────────────"
    log "STEP 3: Guarded prediction (no retrain)"
    log "────────────────────────────────────"

    if [ -z "$PREDICT_INPUT" ]; then
        PREDICT_INPUT="$INPUT"
    fi
    check_file "$PREDICT_INPUT"

    "$PYTHON_BIN" predict_guarded.py \
        --input "$PREDICT_INPUT" \
        --output "$PREDICT_OUTPUT" \
        --model-dir "${MODELS_DIR%/}/deberta_multitask" \
        --safety-threshold "$SAFETY_THRESHOLD" \
        --uncertainty-margin "$UNCERTAINTY_MARGIN" \
        2>&1 | tee logs/predict_guarded.log
fi

# ─────────────────────────────────────────────
# DONE
# ─────────────────────────────────────────────

log "────────────────────────────────────"
log "Pipeline complete"
log "  Labeled CSV       : $LABELED"
log "  Models            : $MODELS_DIR"
log "  Evaluation report : ${MODELS_DIR}evaluation_report.json"
if [ -n "$RUN_GUARDED_PREDICT" ]; then
    log "  Guarded preds     : $PREDICT_OUTPUT"
fi
log "  Logs              : logs/"
log "────────────────────────────────────"
