"""
Phase 2 — Label Derivation using Zero-Shot NLI (DeBERTa)
=========================================================
Reads deduplicated synthetic tickets and derives:
    - issue_severity  (low / medium / high)        — complaints only
    - issue_urgency   (low / medium / high)        — complaints only
    - safety_concern  (True / False)               — complaints only
    - business_impact (low / medium / high)        — complaints only

Inquiries are passed through with null labels.
"""

from __future__ import annotations

import argparse
import importlib
import hashlib
import json
import platform
from pathlib import Path
from typing import Any

import pandas as pd
import torch
from tqdm import tqdm
from transformers import (
    AutoModelForSequenceClassification,
    AutoTokenizer,
    __version__ as transformers_version,
    pipeline,
)

# ─────────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────────

BASE_DIR = Path(__file__).resolve().parent
CLASSIFIER_MODEL_DIR = BASE_DIR / "models" / "classifier" / "deberta-v3-base-mnli-fever-anli"
REMOTE_MODEL_NAME = "MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli"
MODEL_NAME = str(CLASSIFIER_MODEL_DIR) if CLASSIFIER_MODEL_DIR.exists() else REMOTE_MODEL_NAME
LABEL_COLUMNS = ("issue_severity", "issue_urgency", "safety_concern", "business_impact")
CHECKPOINT_EVERY = 100
DEFAULT_MANIFEST_PATH = "output/phase2_model_manifest.json"
MIN_TRANSFORMERS = (4, 55, 0)
MIN_ACCELERATE = (0, 34, 0)
MIN_TOKENIZERS = (0, 21, 0)

# Candidate labels for each classification task.
LABEL_CONFIGS = {
    "issue_severity": {
        "low": [
            "the issue is minor and mostly cosmetic with no impact on operations",
            "the complaint describes a small inconvenience that does not affect work",
            "core building systems are fully functional and unaffected",
        ],
        "medium": [
            "the issue partially disrupts operations but work can continue",
            "some systems are degraded but not completely failed",
            "the complaint describes a moderate problem requiring attention",
        ],
        "high": [
            "core building systems have completely failed",
            "the issue has made the premises unusable or unsafe",
            "operations have been fully halted due to this problem",
        ],
    },
    "issue_urgency": {
        "low": [
            "the issue is minor and can wait for a scheduled maintenance visit",
            "there is no time pressure mentioned in this complaint",
            "the problem has existed for a while without major consequence",
        ],
        "medium": [
            "the issue needs to be resolved within the next few days",
            "the complaint implies growing frustration but no immediate crisis",
            "action is needed soon but the situation is not yet critical",
        ],
        "high": [
            "the complaint explicitly demands same-day or immediate resolution",
            "the situation is described as an emergency requiring instant response",
            "every hour of delay causes direct measurable harm to operations",
        ],
    },
    "safety_concern": {
        True: [
            "the complaint explicitly describes a physical danger or injury risk",
            "someone could be directly harmed by this issue if left unresolved",
            "the problem involves fire, flooding, electrical hazard, or structural danger",
        ],
        False: [
            "the complaint is about a service, billing, or administrative issue",
            "the issue is an inconvenience or operational problem with no physical danger",
            "there is no mention of injury risk, hazardous conditions, or physical harm",
        ],
    },
    "business_impact": {
        "low": [
            "the issue is a minor annoyance that does not affect productivity",
            "staff can work normally and the complaint has negligible business impact",
            "the problem affects a small cosmetic or non-essential aspect of the office",
        ],
        "medium": [
            "the issue is reducing team productivity but work is still happening",
            "some workflows are disrupted but the business is partially operational",
            "the complaint describes a meaningful but not critical operational disruption",
        ],
        "high": [
            "the complaint states that business operations have stopped or cannot continue",
            "staff are unable to work due to this issue",
            "the problem is causing significant financial loss or client-facing disruption",
        ],
    },
}


# ─────────────────────────────────────────────
# CLASSIFIER
# ─────────────────────────────────────────────

def _build_quantized_classifier(model_name: str):
    from transformers import BitsAndBytesConfig

    tokenizer = AutoTokenizer.from_pretrained(model_name)
    model = AutoModelForSequenceClassification.from_pretrained(
        model_name,
        quantization_config=BitsAndBytesConfig(load_in_8bit=True),
        dtype=torch.float16 if torch.cuda.is_available() else torch.float32,
    )
    return pipeline(
        task="zero-shot-classification",
        model=model,
        tokenizer=tokenizer,
    )


def load_classifier(model_name: str, quantization: str = "auto", force_cpu: bool = False):
    device = -1 if force_cpu else (0 if torch.cuda.is_available() else -1)
    device_label = "GPU" if device == 0 else "CPU"
    print(f"\nLoading {model_name} on {device_label}...")

    use_8bit = (not force_cpu) and (
        quantization == "8bit" or (quantization == "auto" and torch.cuda.is_available())
    )

    if use_8bit:
        try:
            print("Using 8-bit quantization (bitsandbytes)")
            clf = _build_quantized_classifier(model_name)
            print("Classifier ready (8-bit)")
            return clf
        except Exception as exc:
            print(f"[WARN] 8-bit classifier load failed: {exc}")
            print("[WARN] Falling back to standard precision loader")

    clf = pipeline(
        task="zero-shot-classification",
        model=model_name,
        tokenizer=model_name,
        device=device,
    )
    print("Classifier ready")
    return clf


def validate_runtime_dependencies() -> None:
    def _parse_version(value: str) -> tuple[int, ...]:
        parts = []
        for token in value.replace("+", ".").split("."):
            if token.isdigit():
                parts.append(int(token))
            else:
                break
        return tuple(parts)

    def _check_min_version(pkg: str, minimum: tuple[int, ...]) -> None:
        module = importlib.import_module(pkg)
        got_raw = getattr(module, "__version__", "0")
        got = _parse_version(got_raw)
        if got < minimum:
            required = ".".join(str(v) for v in minimum)
            raise RuntimeError(
                f"{pkg}=={got_raw} is too old. Required >= {required}. "
                "Run: pip install -U \"transformers>=4.55.0\" "
                "\"accelerate>=0.34.0\" \"tokenizers>=0.21.0\""
            )

    _check_min_version("transformers", MIN_TRANSFORMERS)
    _check_min_version("accelerate", MIN_ACCELERATE)
    _check_min_version("tokenizers", MIN_TOKENIZERS)


def average_hypothesis_scores(
    score_map: dict[str, float], class_hypotheses: dict[Any, list[str]]
) -> dict[Any, float]:
    return {
        class_label: sum(score_map[hypothesis] for hypothesis in hypotheses) / len(hypotheses)
        for class_label, hypotheses in class_hypotheses.items()
    }


def classify_ticket(classifier, text: str) -> dict[str, Any]:
    results: dict[str, Any] = {}
    for label_name, class_hypotheses in LABEL_CONFIGS.items():
        all_hypotheses = []
        for hypotheses in class_hypotheses.values():
            all_hypotheses.extend(hypotheses)

        # Make hypotheses compete for probability mass per label group.
        output = classifier(text, candidate_labels=all_hypotheses, multi_label=False)
        score_map = dict(zip(output["labels"], output["scores"]))
        class_scores = average_hypothesis_scores(score_map, class_hypotheses)
        results[label_name] = max(class_scores, key=class_scores.get)
    return results


# ─────────────────────────────────────────────
# METADATA / AUDIT
# ─────────────────────────────────────────────

def print_distribution(df: pd.DataFrame) -> None:
    complaints = df[df["ticket_type"] == "complaint"]
    print(f"\n{'='*50}")
    print(f"LABEL DISTRIBUTION AUDIT ({len(complaints)} complaints)")
    print(f"{'='*50}")
    for column in LABEL_COLUMNS:
        counts = complaints[column].value_counts()
        total = counts.sum()
        print(f"\n{column}:")
        for value, count in counts.items():
            bar = "█" * int((count / total) * 30)
            pct = count / total * 100
            flag = "  ⚠️  UNDERREPRESENTED" if pct < 10 else ""
            print(f"  {str(value):<10} {count:>5}  ({pct:4.1f}%)  {bar}{flag}")


def validate_input_columns(df: pd.DataFrame) -> None:
    required = {"ticket_type", "subject", "text"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Input CSV is missing required columns: {sorted(missing)}")


def _hash_label_configs() -> str:
    payload = json.dumps(LABEL_CONFIGS, sort_keys=True, default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def write_model_manifest(model_name: str, manifest_path: Path) -> None:
    manifest = {
        "phase": "phase2-classify",
        "model_name": model_name,
        "classifier_model_dir": str(CLASSIFIER_MODEL_DIR.resolve()),
        "tokenizer_dir": str(CLASSIFIER_MODEL_DIR.resolve()),
        "label_columns": list(LABEL_COLUMNS),
        "hypothesis_set_hash": _hash_label_configs(),
        "transformers_version": transformers_version,
        "torch_version": torch.__version__,
        "python_version": platform.python_version(),
    }
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"Saved model manifest to: {manifest_path}")


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────

def main():
    validate_runtime_dependencies()
    parser = argparse.ArgumentParser(description="Phase 2: Zero-shot NLI label derivation")
    parser.add_argument(
        "--input",
        default="output/unlabeled_deduplicated.csv",
        help="Path to deduplicated unlabeled CSV from Phase 4",
    )
    parser.add_argument("--output", default="output/labeled.csv", help="Path to save labeled CSV")
    parser.add_argument("--model", default=MODEL_NAME, help="HuggingFace NLI model name/path")
    parser.add_argument(
        "--manifest-output",
        default=DEFAULT_MANIFEST_PATH,
        help="Path to save reusable model manifest metadata JSON",
    )
    parser.add_argument(
        "--quantization",
        choices=["auto", "none", "8bit"],
        default="auto",
        help="Model quantization mode (default: auto; uses 8bit on CUDA)",
    )
    parser.add_argument("--dry-run", action="store_true", help="Classify first 10 complaints only")
    args = parser.parse_args()

    print(f"Loading: {args.input}")
    df = pd.read_csv(args.input)
    validate_input_columns(df)
    print(
        f"Loaded {len(df)} rows — "
        f"{(df.ticket_type == 'complaint').sum()} complaints, "
        f"{(df.ticket_type == 'inquiry').sum()} inquiries"
    )

    if args.dry_run:
        complaints_idx = df[df["ticket_type"] == "complaint"].head(10).index
        df = df.loc[complaints_idx].copy()
        print(f"\n[DRY RUN] Classifying {len(df)} complaints only")

    classifier = load_classifier(args.model, args.quantization)
    cpu_fallback_classifier = None

    complaint_mask = df["ticket_type"] == "complaint"
    complaint_df = df[complaint_mask].copy()
    inquiry_df = df[~complaint_mask].copy()
    for column in LABEL_COLUMNS:
        inquiry_df[column] = None

    labeled_rows = []
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    for row in tqdm(
        complaint_df.itertuples(index=False),
        total=len(complaint_df),
        desc="Classifying complaints",
    ):
        row_dict = row._asdict()
        try:
            labels = classify_ticket(classifier, row_dict["text"])
        except torch.OutOfMemoryError:
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            print("  [WARN] CUDA OOM during Phase 2 classification")
            if cpu_fallback_classifier is None:
                print("  [WARN] Loading CPU fallback classifier for remaining rows")
                cpu_fallback_classifier = load_classifier(
                    args.model,
                    quantization="none",
                    force_cpu=True,
                )
            classifier = cpu_fallback_classifier
            labels = classify_ticket(classifier, row_dict["text"])

        labeled_rows.append({**row_dict, **labels})

        if len(labeled_rows) % CHECKPOINT_EVERY == 0:
            pd.DataFrame(labeled_rows).to_csv(output_path, index=False)

    labeled_complaints = pd.DataFrame(labeled_rows)
    final_df = pd.concat([labeled_complaints, inquiry_df], ignore_index=True)
    column_order = ["ticket_type", "subject", "text", "domain", *LABEL_COLUMNS]
    final_df = final_df[[column for column in column_order if column in final_df.columns]]
    final_df.to_csv(output_path, index=False)

    print(f"\nSaved {len(final_df)} rows to: {output_path}")
    print_distribution(final_df)

    write_model_manifest(args.model, Path(args.manifest_output))

    print(f"\n{'='*50}")
    print("Phase 2 complete. Review the distribution above.")
    print("If any label is marked ⚠️  UNDERREPRESENTED (< 10%),")
    print("consider a targeted top-up generation pass in Phase 1.")
    print(f"{'='*50}\n")


if __name__ == "__main__":
    main()
