#!/usr/bin/env bash
set -euo pipefail

# Wrapper pipeline that reuses data/synthesizerv7phase2 scripts.
# Flow: generate balanced synthetic -> train multitask NLI -> evaluate on external set.

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SRC_DIR="${ROOT_DIR}/data/synthesizerv7phase2"
WORK_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

ROWS=2500
EPOCHS=3
BATCH_SIZE=16
LR=2e-5
SEED=42
BASE_MODEL="MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli"

OUTPUT_DIR="${WORK_DIR}/output"
MODELS_DIR="${OUTPUT_DIR}/models_2500"
SYNTH_CSV="${OUTPUT_DIR}/balanced_synth_2500.csv"
EVAL_REPORT="${OUTPUT_DIR}/eval_external_report_2500.json"
EVAL_PREDS="${OUTPUT_DIR}/eval_external_predictions_2500.csv"
TEST_CSV="${SRC_DIR}/test/test_dataset_v2.csv"

DRY_RUN="0"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --rows) ROWS="$2"; shift 2 ;;
    --epochs) EPOCHS="$2"; shift 2 ;;
    --batch-size) BATCH_SIZE="$2"; shift 2 ;;
    --lr) LR="$2"; shift 2 ;;
    --seed) SEED="$2"; shift 2 ;;
    --base-model) BASE_MODEL="$2"; shift 2 ;;
    --test) TEST_CSV="$2"; shift 2 ;;
    --output-dir) OUTPUT_DIR="$2"; shift 2 ;;
    --models-dir) MODELS_DIR="$2"; shift 2 ;;
    --synth-csv) SYNTH_CSV="$2"; shift 2 ;;
    --eval-report) EVAL_REPORT="$2"; shift 2 ;;
    --eval-preds) EVAL_PREDS="$2"; shift 2 ;;
    --src-dir) SRC_DIR="$2"; shift 2 ;;
    --dry-run) DRY_RUN="1"; shift ;;
    -h|--help)
      cat << HELP
Usage: bash data/featureengineeringtraining/run_pipeline.sh [options]

Options:
  --rows N            Synthetic rows to generate (default: 2500)
  --epochs N          Training epochs (default: 3)
  --batch-size N      Train batch size (default: 16)
  --lr FLOAT          Learning rate (default: 2e-5)
  --seed N            Random seed for synthesis (default: 42)
  --base-model NAME   HF base model for train.py
  --test PATH         External test CSV with gold labels
  --output-dir PATH   Output root folder (default: ./output)
  --models-dir PATH   Model output dir (default: ./output/models_2500)
  --synth-csv PATH    Generated synthetic CSV path
  --eval-report PATH  Evaluation report JSON path
  --eval-preds PATH   Evaluation predictions CSV path
  --src-dir PATH      Path to synthesizerv7phase2 scripts
  --dry-run           Use 20 rows, 1 epoch, quick sanity run
HELP
      exit 0
      ;;
    *)
      echo "Unknown argument: $1"
      exit 1
      ;;
  esac
done

if [[ "$DRY_RUN" == "1" ]]; then
  ROWS=20
  EPOCHS=1
  MODELS_DIR="${OUTPUT_DIR}/models_smoke"
  SYNTH_CSV="${OUTPUT_DIR}/balanced_synth_20_smoke.csv"
  EVAL_REPORT="${OUTPUT_DIR}/eval_external_report_smoke.json"
  EVAL_PREDS="${OUTPUT_DIR}/eval_external_predictions_smoke.csv"
fi

# Resolve relative outputs after option parsing.
case "${OUTPUT_DIR}" in
  /*) ;;
  *) OUTPUT_DIR="${WORK_DIR}/${OUTPUT_DIR}" ;;
esac
case "${MODELS_DIR}" in
  /*) ;;
  *) MODELS_DIR="${WORK_DIR}/${MODELS_DIR}" ;;
esac
case "${SYNTH_CSV}" in
  /*) ;;
  *) SYNTH_CSV="${WORK_DIR}/${SYNTH_CSV}" ;;
esac
case "${EVAL_REPORT}" in
  /*) ;;
  *) EVAL_REPORT="${WORK_DIR}/${EVAL_REPORT}" ;;
esac
case "${EVAL_PREDS}" in
  /*) ;;
  *) EVAL_PREDS="${WORK_DIR}/${EVAL_PREDS}" ;;
esac
case "${TEST_CSV}" in
  /*) ;;
  *) TEST_CSV="${WORK_DIR}/${TEST_CSV}" ;;
esac

if ! command -v python3 >/dev/null 2>&1; then
  echo "ERROR: python3 not found"
  exit 1
fi

if [[ ! -f "${SRC_DIR}/generate_balanced_phi4.py" ]]; then
  echo "ERROR: Missing ${SRC_DIR}/generate_balanced_phi4.py"
  exit 1
fi
if [[ ! -f "${SRC_DIR}/train.py" ]]; then
  echo "ERROR: Missing ${SRC_DIR}/train.py"
  exit 1
fi
if [[ ! -f "${SRC_DIR}/evaluate_checkpoint.py" ]]; then
  echo "ERROR: Missing ${SRC_DIR}/evaluate_checkpoint.py"
  exit 1
fi
if [[ ! -f "${TEST_CSV}" ]]; then
  echo "ERROR: Missing external test set: ${TEST_CSV}"
  exit 1
fi

mkdir -p "${OUTPUT_DIR}" "${MODELS_DIR}" "${OUTPUT_DIR}/logs"

log() { printf '[%s] %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$1"; }

log "Root           : ${ROOT_DIR}"
log "Phase2 src     : ${SRC_DIR}"
log "Output dir     : ${OUTPUT_DIR}"
log "Rows           : ${ROWS}"
log "Epochs         : ${EPOCHS}"
log "Batch size     : ${BATCH_SIZE}"
log "LR             : ${LR}"
log "Base model     : ${BASE_MODEL}"
log "External test  : ${TEST_CSV}"

log "STEP 0: Environment preflight"
python3 - << 'PY'
import importlib
import sys

modules = [
    "torch",
    "transformers",
    "tokenizers",
    "accelerate",
    "bitsandbytes",
    "protobuf",
    "sentencepiece",
    "pandas",
    "sklearn",
    "tqdm",
]

missing = []
versions = {}
for name in modules:
    try:
        m = importlib.import_module(name)
        versions[name] = getattr(m, "__version__", "unknown")
    except Exception:
        missing.append(name)

if missing:
    print(f"ERROR: Missing Python modules: {missing}")
    print("Install with:")
    print("  pip install -r data/synthesizerv7phase2/requirements.txt")
    sys.exit(1)

try:
    import torch
    print(f"CUDA available: {torch.cuda.is_available()}")
except Exception:
    pass

for k in modules:
    print(f"{k}=={versions.get(k, 'missing')}")
PY

log "STEP 1: Generate balanced labeled synthetic tickets"
python3 "${SRC_DIR}/generate_balanced_phi4.py" \
  --rows "${ROWS}" \
  --output "${SYNTH_CSV}" \
  --seed "${SEED}" \
  2>&1 | tee "${OUTPUT_DIR}/logs/generate.log"

if [[ ! -f "${SYNTH_CSV}" ]]; then
  echo "ERROR: synthetic file not created: ${SYNTH_CSV}"
  exit 1
fi

log "STEP 2: Train multitask NLI model"
python3 "${SRC_DIR}/train.py" \
  --input "${SYNTH_CSV}" \
  --output-dir "${MODELS_DIR}" \
  --base-model "${BASE_MODEL}" \
  --epochs "${EPOCHS}" \
  --batch-size "${BATCH_SIZE}" \
  --lr "${LR}" \
  2>&1 | tee "${OUTPUT_DIR}/logs/train.log"

if [[ ! -f "${MODELS_DIR}/deberta_multitask/model.pt" ]]; then
  echo "ERROR: model checkpoint missing at ${MODELS_DIR}/deberta_multitask/model.pt"
  exit 1
fi

log "STEP 3: Evaluate checkpoint on external test set"
python3 "${SRC_DIR}/evaluate_checkpoint.py" \
  --test "${TEST_CSV}" \
  --text-col issue_text \
  --model-dir "${MODELS_DIR}/deberta_multitask" \
  --output-report "${EVAL_REPORT}" \
  --output-preds "${EVAL_PREDS}" \
  2>&1 | tee "${OUTPUT_DIR}/logs/eval.log"

log "DONE"
log "Synthetic CSV  : ${SYNTH_CSV}"
log "Model dir      : ${MODELS_DIR}/deberta_multitask"
log "Eval report    : ${EVAL_REPORT}"
log "Eval preds     : ${EVAL_PREDS}"
