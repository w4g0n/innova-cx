#!/bin/bash
# Feature Engineering Training Pipeline (V8)
# Mirrors synthesizerv7phase2 runtime style and directory conventions.

set -euo pipefail
export PYTHONNOUSERSITE=1

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

INPUT_CSV="Input/complaints_2500.csv"
ROWS="2500"
EPOCHS="5"
BATCH_SIZE="16"
LEARNING_RATE="2e-5"
DRY_RUN=""
SKIP_GENERATE=""
SKIP_SPLIT=""
SKIP_TRAIN=""
SKIP_EVAL=""
SKIP_PREFLIGHT=""
BASE_MODEL="microsoft/deberta-v3-small"
SMOKE_TEST=""

log() { echo "[$(date '+%H:%M:%S')] $1"; }

check_file() {
  if [ ! -f "$1" ]; then
    echo "ERROR: Required file not found: $1"
    exit 1
  fi
}

while [[ "$#" -gt 0 ]]; do
  case $1 in
    --input) INPUT_CSV="$2"; shift ;;
    --rows) ROWS="$2"; shift ;;
    --epochs) EPOCHS="$2"; shift ;;
    --batch-size) BATCH_SIZE="$2"; shift ;;
    --learning-rate) LEARNING_RATE="$2"; shift ;;
    --dry-run) DRY_RUN="--dry-run" ;;
    --skip-generate) SKIP_GENERATE="1" ;;
    --skip-split) SKIP_SPLIT="1" ;;
    --skip-train) SKIP_TRAIN="1" ;;
    --skip-eval) SKIP_EVAL="1" ;;
    --skip-preflight) SKIP_PREFLIGHT="1" ;;
    --base-model) BASE_MODEL="$2"; shift ;;
    --smoke-test) SMOKE_TEST="1" ;;
    *) echo "Unknown arg: $1"; exit 1 ;;
  esac
  shift
done

if [ -n "${PYTHON_BIN:-}" ]; then
  if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
    log "ERROR: PYTHON_BIN set but not found: $PYTHON_BIN"
    exit 1
  fi
else
  if command -v python3 >/dev/null 2>&1; then
    PYTHON_BIN="python3"
  elif command -v python >/dev/null 2>&1; then
    PYTHON_BIN="python"
  else
    log "ERROR: No Python interpreter found"
    exit 1
  fi
fi

mkdir -p Input output test logs models/deberta_multitask

log "Starting feature engineering training pipeline"
log "Python        : $PYTHON_BIN"
log "Input CSV     : $INPUT_CSV"
log "Rows          : $ROWS"
log "Epochs        : $EPOCHS"
log "Batch size    : $BATCH_SIZE"
log "Learning rate : $LEARNING_RATE"
log "Base model    : $BASE_MODEL"
[ -n "$SMOKE_TEST" ] && log "Mode          : SMOKE TEST (mock generate/train/eval)"
[ -n "$DRY_RUN" ] && log "Mode          : DRY RUN"

if [ -z "$SKIP_PREFLIGHT" ]; then
  if [ -n "$SMOKE_TEST" ]; then
    log "STEP 0 skipped in smoke-test mode (real dependency checks not required)"
  else
  log "────────────────────────────────────"
  log "STEP 0: Cloud preflight checks"
  log "────────────────────────────────────"
  "$PYTHON_BIN" cloud_preflight.py 2>&1 | tee logs/preflight.log
  fi
else
  log "STEP 0 skipped (--skip-preflight)"
fi

if [ -z "$SKIP_GENERATE" ]; then
  log "────────────────────────────────────"
  log "STEP 1: Generate balanced synthetic data"
  log "────────────────────────────────────"
  if [ -n "$SMOKE_TEST" ]; then
    "$PYTHON_BIN" mock_generate.py \
      --rows "$ROWS" \
      --output "$INPUT_CSV" \
      --report output/balance_report.json \
      $DRY_RUN \
      2>&1 | tee logs/generate.log
  else
    "$PYTHON_BIN" generate_balanced_phi4.py \
      --rows "$ROWS" \
      --output "$INPUT_CSV" \
      --report output/balance_report.json \
      $DRY_RUN \
      2>&1 | tee logs/generate.log
  fi
else
  log "STEP 1 skipped (--skip-generate)"
fi

check_file "$INPUT_CSV"

if [ -z "$SKIP_SPLIT" ]; then
  log "────────────────────────────────────"
  log "STEP 2: Stratified split (train/val/test)"
  log "────────────────────────────────────"
  "$PYTHON_BIN" preprocess_split.py \
    --input "$INPUT_CSV" \
    --train-output output/train.csv \
    --val-output output/val.csv \
    --test-output test/test.csv \
    2>&1 | tee logs/preprocess.log
else
  log "STEP 2 skipped (--skip-split)"
fi

check_file output/train.csv
check_file output/val.csv
check_file test/test.csv

if [ -n "$DRY_RUN" ]; then
  log "DRY RUN complete: training and eval skipped"
  exit 0
fi

if [ -z "$SKIP_TRAIN" ]; then
  log "────────────────────────────────────"
  log "STEP 3: Train multitask DeBERTa-v3-small"
  log "────────────────────────────────────"
  if [ -n "$SMOKE_TEST" ]; then
    "$PYTHON_BIN" mock_train.py \
      --train output/train.csv \
      --val output/val.csv \
      --output-dir models/deberta_multitask \
      --epochs "$EPOCHS" \
      --batch-size "$BATCH_SIZE" \
      --learning-rate "$LEARNING_RATE" \
      --base-model "$BASE_MODEL" \
      2>&1 | tee logs/train.log
  else
    "$PYTHON_BIN" train.py \
      --train output/train.csv \
      --val output/val.csv \
      --output-dir models/deberta_multitask \
      --epochs "$EPOCHS" \
      --batch-size "$BATCH_SIZE" \
      --learning-rate "$LEARNING_RATE" \
      --base-model "$BASE_MODEL" \
      2>&1 | tee logs/train.log
  fi
else
  log "STEP 3 skipped (--skip-train)"
fi

if [ -z "$SKIP_TRAIN" ]; then
  check_file models/deberta_multitask/model.pt
fi

if [ -z "$SKIP_EVAL" ]; then
  log "────────────────────────────────────"
  log "STEP 4: Evaluate on holdout test set"
  log "────────────────────────────────────"
  if [ -n "$SMOKE_TEST" ]; then
    "$PYTHON_BIN" mock_evaluate.py \
      --test test/test.csv \
      --model-dir models/deberta_multitask \
      --output-report output/eval_external_report.json \
      --output-preds output/eval_external_predictions.csv \
      2>&1 | tee logs/evaluate.log
  else
    "$PYTHON_BIN" evaluate_checkpoint.py \
      --test test/test.csv \
      --model-dir models/deberta_multitask \
      --output-report output/eval_external_report.json \
      --output-preds output/eval_external_predictions.csv \
      2>&1 | tee logs/evaluate.log
  fi
else
  log "STEP 4 skipped (--skip-eval)"
fi

log "Pipeline complete"
