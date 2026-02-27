"""
Phase 3 — Prediction-Only Labeling on Test Data
================================================
Reads a test CSV and predicts:
    - issue_severity
    - issue_urgency
    - safety_concern
    - business_impact

Expected input schema:
    - issue_text (preferred), OR
    - text (legacy alias)
"""

from __future__ import annotations

import argparse
import importlib
from pathlib import Path
from typing import Any

import pandas as pd
import torch
from tqdm import tqdm
from transformers import (
    AutoModelForSequenceClassification,
    AutoTokenizer,
    pipeline,
)

BASE_DIR = Path(__file__).resolve().parent
CLASSIFIER_MODEL_DIR = BASE_DIR / "models" / "classifier" / "deberta-v3-base-mnli-fever-anli"
REMOTE_MODEL_NAME = "MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli"
MODEL_NAME = str(CLASSIFIER_MODEL_DIR) if CLASSIFIER_MODEL_DIR.exists() else REMOTE_MODEL_NAME
DEFAULT_OUTPUT_PATH = "output/predictions.csv"
LABEL_COLUMNS = ["issue_severity", "issue_urgency", "safety_concern", "business_impact"]
MIN_TRANSFORMERS = (4, 46, 0)
MIN_ACCELERATE = (0, 30, 0)
MIN_TOKENIZERS = (0, 20, 0)

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
                "Run: pip install -U \"transformers>=4.46.0\" "
                "\"accelerate>=0.30.0\" \"tokenizers>=0.20.0\""
            )

    _check_min_version("transformers", MIN_TRANSFORMERS)
    _check_min_version("accelerate", MIN_ACCELERATE)
    _check_min_version("tokenizers", MIN_TOKENIZERS)


def _average_hypothesis_scores(
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
        class_scores = _average_hypothesis_scores(score_map, class_hypotheses)
        results[label_name] = max(class_scores, key=class_scores.get)
    return results


def validate_and_normalize_input(df: pd.DataFrame) -> pd.DataFrame:
    if "issue_text" in df.columns:
        return df
    if "text" in df.columns:
        normalized = df.copy()
        normalized["issue_text"] = normalized["text"]
        return normalized
    raise ValueError("Test CSV must include either 'issue_text' or 'text' column")


def predict_all(classifier, texts: list[str], model_name: str) -> pd.DataFrame:
    predictions = []
    active_classifier = classifier
    cpu_fallback_classifier = None

    for text in tqdm(texts, total=len(texts), desc="Classifying"):
        try:
            pred = classify_ticket(active_classifier, text)
        except torch.OutOfMemoryError:
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            print("  [WARN] CUDA OOM during Phase 3 prediction")
            if cpu_fallback_classifier is None:
                print("  [WARN] Loading CPU fallback classifier for remaining rows")
                cpu_fallback_classifier = load_classifier(
                    model_name=model_name,
                    quantization="none",
                    force_cpu=True,
                )
            active_classifier = cpu_fallback_classifier
            pred = classify_ticket(active_classifier, text)
        predictions.append(pred)

    return pd.DataFrame(predictions)


def main():
    validate_runtime_dependencies()
    parser = argparse.ArgumentParser(
        description="Phase 3: Prediction-only classifier run for issue_text/text CSV"
    )
    parser.add_argument("--test", required=True, help="Path to test CSV")
    parser.add_argument("--output", default=DEFAULT_OUTPUT_PATH, help="Path to save predictions CSV")
    parser.add_argument("--model", default=MODEL_NAME, help="HuggingFace NLI model name/path")
    parser.add_argument(
        "--quantization",
        choices=["auto", "none", "8bit"],
        default="auto",
        help="Model quantization mode (default: auto; uses 8bit on CUDA)",
    )
    args = parser.parse_args()

    print(f"\nLoading test data: {args.test}")
    df = pd.read_csv(args.test)
    df = validate_and_normalize_input(df)
    print(f"Predicting labels for {len(df)} rows")

    classifier = load_classifier(args.model, args.quantization)
    pred_df = predict_all(classifier, df["issue_text"].astype(str).tolist(), model_name=args.model)

    output_df = pd.DataFrame({"issue_text": df["issue_text"]})
    for col in LABEL_COLUMNS:
        output_df[col] = pred_df[col]

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_df.to_csv(output_path, index=False)
    print(f"Predictions saved to: {output_path}")

    print("\nPrediction label distribution:")
    for col in LABEL_COLUMNS:
        print(f"\n{col}:")
        print(output_df[col].value_counts(dropna=False).to_string())


if __name__ == "__main__":
    main()
