#!/bin/bash
# run_pipeline.sh — Orchestrates labeling + training pipeline
# ============================================================
# Usage:
#   bash run_pipeline.sh
#   bash run_pipeline.sh --dry-run       # test with 10 rows
#   bash run_pipeline.sh --epochs 5      # override training epochs
#   bash run_pipeline.sh --full-run --epochs 3   # explicit uncapped full dataset run
#   bash run_pipeline.sh --skip-label --epochs 2 --resume-from models/deberta_multitask/model.pt
#   bash run_pipeline.sh --full-run --resume-from models/deberta_multitask/model.pt --weighted-safety-loss
#   bash run_pipeline.sh --full-run --run-guarded-predict
#   bash run_pipeline.sh --skip-label --generate-safety-rows 1000 --augment-with-safety --external-test output/safety_test_v2.csv

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
SKIP_LABEL=""
RESUME_FROM=""
WEIGHTED_SAFETY_LOSS=""
SAFETY_POSITIVE_WEIGHT=""
RUN_GUARDED_PREDICT=""
PREDICT_INPUT=""
PREDICT_OUTPUT="output/predictions_guarded.csv"
SAFETY_THRESHOLD="0.30"
UNCERTAINTY_MARGIN="0.15"
GENERATE_SAFETY_ROWS="0"
SAFETY_SYNTH_OUTPUT="output/safety_synth_1000.csv"
AUGMENT_WITH_SAFETY=""
AUGMENTED_OUTPUT="labeled_augmented.csv"
EXTERNAL_TEST=""
EXTERNAL_EVAL_REPORT="output/eval_external_report.json"
EXTERNAL_EVAL_PREDS="output/eval_external_predictions.csv"
TRAIN_INPUT=""

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
        --skip-label) SKIP_LABEL="1" ;;
        --resume-from) RESUME_FROM="$2"; shift ;;
        --weighted-safety-loss) WEIGHTED_SAFETY_LOSS="1" ;;
        --safety-positive-weight) SAFETY_POSITIVE_WEIGHT="$2"; shift ;;
        --run-guarded-predict) RUN_GUARDED_PREDICT="1" ;;
        --predict-input) PREDICT_INPUT="$2"; shift ;;
        --predict-output) PREDICT_OUTPUT="$2"; shift ;;
        --safety-threshold) SAFETY_THRESHOLD="$2"; shift ;;
        --uncertainty-margin) UNCERTAINTY_MARGIN="$2"; shift ;;
        --generate-safety-rows) GENERATE_SAFETY_ROWS="$2"; shift ;;
        --safety-synth-output) SAFETY_SYNTH_OUTPUT="$2"; shift ;;
        --augment-with-safety) AUGMENT_WITH_SAFETY="1" ;;
        --augmented-output) AUGMENTED_OUTPUT="$2"; shift ;;
        --external-test) EXTERNAL_TEST="$2"; shift ;;
        --external-eval-report) EXTERNAL_EVAL_REPORT="$2"; shift ;;
        --external-eval-preds) EXTERNAL_EVAL_PREDS="$2"; shift ;;
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
if [ -n "$SKIP_LABEL" ]; then
    log "Skip label   : enabled"
fi
if [ "${GENERATE_SAFETY_ROWS}" != "0" ]; then
    log "Safety synth : ${GENERATE_SAFETY_ROWS} rows -> ${SAFETY_SYNTH_OUTPUT}"
fi
if [ -n "$AUGMENT_WITH_SAFETY" ]; then
    log "Augment data : enabled -> ${AUGMENTED_OUTPUT}"
fi
if [ -n "$EXTERNAL_TEST" ]; then
    log "External test: ${EXTERNAL_TEST}"
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

if [ -z "$SKIP_LABEL" ]; then
    log "────────────────────────────────────"
    log "STEP 1: Labeling with Phi-4-mini"
    log "────────────────────────────────────"

    LABEL_CMD=("$PYTHON_BIN" "label.py" "--input" "$INPUT" "--output" "$LABELED")
    [ -n "$DRY_RUN" ] && LABEL_CMD+=("$DRY_RUN")
    if [ -z "$FULL_RUN" ]; then
        LABEL_CMD+=("--max-complaints" "$MAX_COMPLAINTS")
    fi

    "${LABEL_CMD[@]}" 2>&1 | tee logs/label.log
else
    log "────────────────────────────────────"
    log "STEP 1: Labeling skipped (--skip-label)"
    log "────────────────────────────────────"
fi

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
# STEP 2 — GENERATE SAFETY SYNTHETIC DATA (OPTIONAL)
# ─────────────────────────────────────────────

if [ "${GENERATE_SAFETY_ROWS}" != "0" ]; then
    log "────────────────────────────────────"
    log "STEP 2: Generate safety synthetic data (Phi-4)"
    log "────────────────────────────────────"

    "$PYTHON_BIN" generate_safety_phi4.py \
        --rows "$GENERATE_SAFETY_ROWS" \
        --output "$SAFETY_SYNTH_OUTPUT" \
        2>&1 | tee logs/generate_safety.log
fi

# ─────────────────────────────────────────────
# STEP 3 — MERGE AUGMENTED TRAINING DATA (OPTIONAL)
# ─────────────────────────────────────────────

TRAIN_INPUT="$LABELED"
if [ -n "$AUGMENT_WITH_SAFETY" ] || [ "${GENERATE_SAFETY_ROWS}" != "0" ]; then
    log "────────────────────────────────────"
    log "STEP 3: Merge augmented training data"
    log "────────────────────────────────────"

    check_file "$SAFETY_SYNTH_OUTPUT"
    "$PYTHON_BIN" merge_training_data.py \
        --base "$LABELED" \
        --add "$SAFETY_SYNTH_OUTPUT" \
        --output "$AUGMENTED_OUTPUT" \
        2>&1 | tee logs/merge_training.log

    TRAIN_INPUT="$AUGMENTED_OUTPUT"
fi

# ─────────────────────────────────────────────
# STEP 4 — TRAIN
# ─────────────────────────────────────────────

log "────────────────────────────────────"
log "STEP 4: Fine-tuning DeBERTa"
log "────────────────────────────────────"

TRAIN_CMD=(
    "$PYTHON_BIN" train.py
    --input "$TRAIN_INPUT"
    --output-dir "$MODELS_DIR"
    --epochs "$EPOCHS"
)
[ -n "$RESUME_FROM" ] && TRAIN_CMD+=(--resume-from "$RESUME_FROM")
[ -n "$WEIGHTED_SAFETY_LOSS" ] && TRAIN_CMD+=(--weighted-safety-loss)
[ -n "$SAFETY_POSITIVE_WEIGHT" ] && TRAIN_CMD+=(--safety-positive-weight "$SAFETY_POSITIVE_WEIGHT")

"${TRAIN_CMD[@]}" 2>&1 | tee logs/train.log

# ─────────────────────────────────────────────
# STEP 5 — GUARDED PREDICTION (OPTIONAL)
# ─────────────────────────────────────────────

if [ -n "$RUN_GUARDED_PREDICT" ]; then
    log "────────────────────────────────────"
    log "STEP 5: Guarded prediction (no retrain)"
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
# STEP 6 — EXTERNAL EVALUATION (OPTIONAL)
# ─────────────────────────────────────────────

if [ -n "$EXTERNAL_TEST" ]; then
    log "────────────────────────────────────"
    log "STEP 6: External test-set evaluation"
    log "────────────────────────────────────"

    check_file "$EXTERNAL_TEST"
    "$PYTHON_BIN" evaluate_checkpoint.py \
        --test "$EXTERNAL_TEST" \
        --model-dir "${MODELS_DIR%/}/deberta_multitask" \
        --output-report "$EXTERNAL_EVAL_REPORT" \
        --output-preds "$EXTERNAL_EVAL_PREDS" \
        2>&1 | tee logs/eval_external.log
fi

# ─────────────────────────────────────────────
# DONE
# ─────────────────────────────────────────────

log "────────────────────────────────────"
log "Pipeline complete"
log "  Labeled CSV       : $LABELED"
if [ "$TRAIN_INPUT" != "$LABELED" ]; then
    log "  Train input       : $TRAIN_INPUT"
fi
log "  Models            : $MODELS_DIR"
log "  Evaluation report : ${MODELS_DIR}evaluation_report.json"
if [ -n "$RUN_GUARDED_PREDICT" ]; then
    log "  Guarded preds     : $PREDICT_OUTPUT"
fi
if [ -n "$EXTERNAL_TEST" ]; then
    log "  External report   : $EXTERNAL_EVAL_REPORT"
    log "  External preds    : $EXTERNAL_EVAL_PREDS"
fi
log "  Logs              : logs/"
log "────────────────────────────────────"
