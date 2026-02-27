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

# Candidate labels for each classification task.
LABEL_CONFIGS = {
    "issue_severity": {
        "low": [
            "the issue is minor and mostly cosmetic",
            "the complaint describes a small inconvenience with limited impact",
            "core building systems are still functioning normally",
        ],
        "medium": [
            "the issue disrupts normal operations but does not fully stop them",
            "important systems are affected and service quality is reduced",
            "the complaint indicates a moderate infrastructure problem",
        ],
        "high": [
            "the issue is a critical service failure",
            "core infrastructure is broken and operations are seriously affected",
            "the complaint describes a severe and high-risk technical breakdown",
        ],
    },
    "issue_urgency": {
        "low": [
            "this can be handled in routine scheduling",
            "the issue does not require immediate intervention",
            "a short delay is acceptable without major consequences",
        ],
        "medium": [
            "this should be fixed soon to avoid escalation",
            "the issue is time-sensitive but not an immediate emergency",
            "delays are likely to worsen business disruption",
        ],
        "high": [
            "this requires immediate action",
            "the complaint indicates urgent intervention is needed now",
            "delays could cause severe operational or safety consequences",
        ],
    },
    "safety_concern": {
        True: [
            "the issue presents a direct health or physical safety hazard",
            "people in the building could be injured if unresolved",
            "the complaint describes an unsafe environment",
        ],
        False: [
            "the issue is operational and not a direct safety hazard",
            "there is no explicit risk of injury or health harm in this complaint",
            "the complaint does not indicate immediate danger to people",
        ],
    },
    "business_impact": {
        "low": [
            "business operations continue with little disruption",
            "the issue has minor productivity impact",
            "the complaint reflects low operational or financial impact",
        ],
        "medium": [
            "the issue is causing noticeable productivity loss",
            "operations are disrupted but still partially running",
            "the complaint indicates moderate business impact",
        ],
        "high": [
            "the issue significantly disrupts business continuity",
            "operations are heavily blocked or financially impacted",
            "the complaint indicates major business impact",
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
        torch_dtype=torch.float16 if torch.cuda.is_available() else torch.float32,
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
        all_hypotheses = [
            hypothesis
            for hypotheses in class_hypotheses.values()
            for hypothesis in hypotheses
        ]
        output = classifier(text, candidate_labels=all_hypotheses, multi_label=True)
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
