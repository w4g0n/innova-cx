"""
Phase 2 — Label Derivation using Zero-Shot NLI (DeBERTa)
=========================================================
Reads the unlabeled.csv produced by Phase 1 and derives:
    - issue_severity  (low / medium / high)        — complaints only
    - issue_urgency   (low / medium / high)         — complaints only
    - safety_concern  (True / False)                — complaints only
    - business_impact (low / medium / high)         — complaints only

Inquiries are passed through with null labels.

Requirements:
    pip install -r data/synthesizerv7/requirements.txt

Usage:
    python phase2_classify.py --input output/unlabeled.csv --output output/labeled.csv

    # Dry run (classifies first 10 complaints only)
    python phase2_classify.py --input output/unlabeled.csv --output output/labeled.csv --dry-run
"""

import argparse
from pathlib import Path
from typing import Any

import pandas as pd
import torch
from tqdm import tqdm
from transformers import pipeline

# ─────────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────────

BASE_DIR = Path(__file__).resolve().parent
CLASSIFIER_MODEL_DIR = BASE_DIR / "models" / "classifier" / "deberta-v3-base-mnli-fever-anli"
REMOTE_MODEL_NAME = "MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli"
MODEL_NAME = str(CLASSIFIER_MODEL_DIR) if CLASSIFIER_MODEL_DIR.exists() else REMOTE_MODEL_NAME
LABEL_COLUMNS = ("issue_severity", "issue_urgency", "safety_concern", "business_impact")
CHECKPOINT_EVERY = 100

# Candidate labels for each classification task
# Wording is deliberate — clear, unambiguous hypothesis statements
# Each label has multiple hypothesis statements per class.
# The classifier scores all of them and averages per class — this is more
# robust than a single hypothesis and reduces sensitivity to wording.
LABEL_CONFIGS = {
    "issue_severity": {
        "low": [
            "the technical problem described is minor and does not affect core facility systems",
            "this is a small defect or inconvenience within the tenant space",
            "the issue is localized and does not impact building infrastructure",
        ],
        "medium": [
            "the problem affects part of the facility but not the entire operation",
            "this issue impacts important systems but does not cause full service failure",
            "the fault disrupts some building functions but operations can continue",
        ],
        "high": [
            "the issue represents a critical failure of core facility infrastructure",
            "this problem involves major system breakdown affecting the facility",
            "the complaint describes a severe technical failure within the building",
        ],
    },
    "issue_urgency": {
        "low": [
            "this issue can be scheduled for routine maintenance without immediate action",
            "the problem does not require urgent intervention",
            "the situation can be resolved in normal service timelines",
        ],
        "medium": [
            "this issue should be addressed soon to prevent escalation",
            "the problem requires timely action but is not an emergency",
            "delayed resolution may cause additional complications",
        ],
        "high": [
            "this issue requires immediate intervention",
            "the problem demands urgent action to prevent serious consequences",
            "failure to act quickly could cause significant damage or escalation",
        ],
    },
    "safety_concern": {
        True: [
            "the issue involves a risk to human health or physical safety",
            "this complaint describes a hazardous situation for tenants or staff",
            "the problem poses potential injury or health danger within the facility",
        ],
        False: [
            "the issue does not involve any risk to human safety",
            "this complaint concerns operational matters without safety hazards",
            "there is no indication of health or physical danger in this issue",
        ],
    },
    "business_impact": {
        "low": [
            "the issue causes minimal disruption to tenant business operations",
            "business activities can continue normally despite this problem",
            "the operational impact on the tenant is negligible",
        ],
        "medium": [
            "the issue is causing noticeable disruption to tenant operations",
            "business productivity is partially affected by this problem",
            "the complaint indicates moderate operational disturbance",
        ],
        "high": [
            "the issue is significantly disrupting tenant business operations",
            "this problem is preventing normal business continuity",
            "the complaint describes major operational or financial impact",
        ],
    },
}

# ─────────────────────────────────────────────
# CLASSIFIER
# ─────────────────────────────────────────────

def load_classifier(model_name: str, quantization: str = "auto", force_cpu: bool = False):
    device = -1 if force_cpu else (0 if torch.cuda.is_available() else -1)
    device_label = "GPU" if device == 0 else "CPU"
    print(f"\nLoading {model_name} on {device_label}...")

    use_8bit = (not force_cpu) and (
        quantization == "8bit" or (quantization == "auto" and torch.cuda.is_available())
    )
    pipe_kwargs: dict[str, Any] = {
        "task": "zero-shot-classification",
        "model": model_name,
    }

    if use_8bit:
        try:
            from transformers import BitsAndBytesConfig

            pipe_kwargs["model_kwargs"] = {
                "quantization_config": BitsAndBytesConfig(load_in_8bit=True),
                "device_map": "auto",
            }
            print("Using 8-bit quantization (bitsandbytes)")
        except Exception as exc:
            print(f"[WARN] Could not enable 8-bit quantization: {exc}")
            print("[WARN] Falling back to standard precision load")
            pipe_kwargs["device"] = device
    else:
        pipe_kwargs["device"] = device

    try:
        classifier = pipeline(**pipe_kwargs)
    except ValueError as exc:
        if "load_in_8bit_fp32_cpu_offload" in str(exc):
            print("[WARN] VRAM insufficient for pure 8-bit placement; retrying with CPU offload")
            try:
                from transformers import BitsAndBytesConfig

                offload_kwargs = {
                    "task": "zero-shot-classification",
                    "model": model_name,
                    "model_kwargs": {
                        "quantization_config": BitsAndBytesConfig(
                            load_in_8bit=True,
                            llm_int8_enable_fp32_cpu_offload=True,
                        ),
                        "device_map": "auto",
                    },
                }
                classifier = pipeline(**offload_kwargs)
            except Exception as offload_exc:
                print(f"[WARN] 8-bit offload retry failed: {offload_exc}")
                print("[WARN] Falling back to compatibility loader")
                fallback_kwargs: dict[str, Any] = {
                    "task": "zero-shot-classification",
                    "model": model_name,
                    "device": device,
                }
                classifier = pipeline(**fallback_kwargs)
        else:
            raise
    except TypeError as exc:
        print(f"[WARN] Pipeline args not accepted ({exc}); retrying with compatibility fallback")
        fallback_kwargs: dict[str, Any] = {
            "task": "zero-shot-classification",
            "model": model_name,
            "device": device,
        }
        classifier = pipeline(**fallback_kwargs)
    print("Classifier ready")
    return classifier


def average_hypothesis_scores(
    score_map: dict[str, float], class_hypotheses: dict[Any, list[str]]
) -> dict[Any, float]:
    return {
        class_label: sum(score_map[h] for h in hypotheses) / len(hypotheses)
        for class_label, hypotheses in class_hypotheses.items()
    }


def classify_ticket(classifier, text: str) -> dict:
    """
    Runs all four classification tasks on a single ticket text.
    For each label, scores all hypotheses across all classes, then
    averages the scores per class — the class with the highest
    average score wins. This is more robust than a single hypothesis.
    """
    results = {}

    for label_name, class_hypotheses in LABEL_CONFIGS.items():
        # Flatten all hypotheses across all classes
        all_hypotheses = [
            hypothesis
            for hypotheses in class_hypotheses.values()
            for hypothesis in hypotheses
        ]

        output = classifier(
            text,
            candidate_labels=all_hypotheses,
            multi_label=True,  # Score each hypothesis independently
        )

        # Map scores back to hypotheses
        score_map = dict(zip(output["labels"], output["scores"]))

        class_scores = average_hypothesis_scores(score_map, class_hypotheses)

        # Pick the class with the highest average score
        results[label_name] = max(class_scores, key=class_scores.get)

    return results


# ─────────────────────────────────────────────
# DISTRIBUTION AUDIT
# ─────────────────────────────────────────────

def print_distribution(df: pd.DataFrame):
    complaints = df[df["ticket_type"] == "complaint"]
    print(f"\n{'='*50}")
    print(f"LABEL DISTRIBUTION AUDIT ({len(complaints)} complaints)")
    print(f"{'='*50}")
    for col in LABEL_COLUMNS:
        counts = complaints[col].value_counts()
        total = counts.sum()
        print(f"\n{col}:")
        for val, count in counts.items():
            bar = "█" * int((count / total) * 30)
            pct = count / total * 100
            flag = "  ⚠️  UNDERREPRESENTED" if pct < 10 else ""
            print(f"  {str(val):<10} {count:>5}  ({pct:4.1f}%)  {bar}{flag}")


def validate_input_columns(df: pd.DataFrame) -> None:
    required = {"ticket_type", "subject", "text"}
    if not required.issubset(df.columns):
        raise ValueError(f"Input CSV must have columns: {required}")


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Phase 2: Zero-shot NLI label derivation")
    parser.add_argument("--input",   default="output/unlabeled.csv", help="Path to unlabeled.csv from Phase 1")
    parser.add_argument("--output",  default="output/labeled.csv",   help="Path to save labeled CSV")
    parser.add_argument("--model",   default=MODEL_NAME,             help="HuggingFace NLI model name")
    parser.add_argument(
        "--quantization",
        choices=["auto", "none", "8bit"],
        default="auto",
        help="Model quantization mode (default: auto; uses 8bit on CUDA)",
    )
    parser.add_argument("--dry-run", action="store_true",            help="Classify first 10 complaints only")
    args = parser.parse_args()

    # ── Load input ──
    print(f"Loading: {args.input}")
    df = pd.read_csv(args.input)
    validate_input_columns(df)

    print(f"Loaded {len(df)} rows — {(df.ticket_type == 'complaint').sum()} complaints, {(df.ticket_type == 'inquiry').sum()} inquiries")

    # ── Dry run override ──
    if args.dry_run:
        complaints_idx = df[df["ticket_type"] == "complaint"].head(10).index
        df = df.loc[complaints_idx].copy()
        print(f"\n[DRY RUN] Classifying {len(df)} complaints only")

    # ── Load classifier ──
    classifier = load_classifier(args.model, args.quantization)
    cpu_fallback_classifier = None

    # ── Classify complaints only ──
    complaint_mask = df["ticket_type"] == "complaint"
    complaint_df = df[complaint_mask].copy()
    inquiry_df   = df[~complaint_mask].copy()

    # Ensure label columns exist on inquiries with null values
    for col in LABEL_COLUMNS:
        inquiry_df[col] = None

    labeled_rows = []
    checkpoint_path = Path(args.output)
    checkpoint_path.parent.mkdir(parents=True, exist_ok=True)

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

        # Checkpoint every 100 rows
        if len(labeled_rows) % CHECKPOINT_EVERY == 0:
            checkpoint_df = pd.DataFrame(labeled_rows)
            checkpoint_df.to_csv(checkpoint_path, index=False)

    # ── Combine and save ──
    labeled_complaints = pd.DataFrame(labeled_rows)
    final_df = pd.concat([labeled_complaints, inquiry_df], ignore_index=True)

    # Restore original column order
    col_order = ["ticket_type", "subject", "text", "domain", *LABEL_COLUMNS]
    final_df = final_df[[c for c in col_order if c in final_df.columns]]

    final_df.to_csv(checkpoint_path, index=False)

    print(f"\nSaved {len(final_df)} rows to: {checkpoint_path}")

    # ── Audit distribution ──
    print_distribution(final_df)

    print(f"\n{'='*50}")
    print("Phase 2 complete. Review the distribution above.")
    print("If any label is marked ⚠️  UNDERREPRESENTED (< 10%),")
    print("consider a targeted top-up generation pass in Phase 1.")
    print(f"{'='*50}\n")


if __name__ == "__main__":
    main()
