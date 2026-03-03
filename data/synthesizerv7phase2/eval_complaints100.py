"""
eval_complaints100.py

One-shot utility for:
1) Predicting on unlabeled complaints_100 text.
2) Comparing predictions to a reference CSV.
3) Printing accuracy + macro F1 for all four tasks.
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path

import pandas as pd
from sklearn.metrics import accuracy_score, f1_score

TASKS = [
    ("issue_severity", "pred_issue_severity"),
    ("issue_urgency", "pred_issue_urgency"),
    ("safety_concern", "pred_safety_concern"),
    ("business_impact", "pred_business_impact"),
]


def _normalise_series(s: pd.Series) -> pd.Series:
    return s.astype(str).str.strip().str.lower()


def main():
    parser = argparse.ArgumentParser(description="Predict + score on complaints_100 files")
    parser.add_argument("--input", default="test/complaints_100.csv", help="Unlabeled input CSV")
    parser.add_argument(
        "--reference",
        default="test/complaints_100_predictions.csv",
        help="Reference CSV containing ground-truth labels or pred_* labels",
    )
    parser.add_argument(
        "--model-dir",
        default="output/models_2500/deberta_multitask",
        help="Directory containing model.pt/model_config.json/label_classes.json",
    )
    parser.add_argument("--text-col", default="issue_text")
    parser.add_argument("--safety-threshold", type=float, default=0.20)
    parser.add_argument("--uncertainty-margin", type=float, default=0.12)
    parser.add_argument("--pred-output", default="test/complaints_100_model_preds.csv")
    parser.add_argument("--report-output", default="test/complaints_100_accuracy.json")
    args = parser.parse_args()

    input_path = Path(args.input)
    ref_path = Path(args.reference)
    pred_path = Path(args.pred_output)
    report_path = Path(args.report_output)

    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")
    if not ref_path.exists():
        raise FileNotFoundError(f"Reference file not found: {ref_path}")

    # Predict from unlabeled text file.
    cmd = [
        sys.executable,
        "predict_guarded.py",
        "--input",
        str(input_path),
        "--output",
        str(pred_path),
        "--model-dir",
        args.model_dir,
        "--text-col",
        args.text_col,
        "--safety-threshold",
        str(args.safety_threshold),
        "--uncertainty-margin",
        str(args.uncertainty_margin),
    ]
    subprocess.run(cmd, check=True)

    ref_df = pd.read_csv(ref_path)
    pred_df = pd.read_csv(pred_path)
    if len(ref_df) != len(pred_df):
        raise ValueError(f"Row count mismatch: reference={len(ref_df)} predictions={len(pred_df)}")

    metrics = {}
    for base_col, pred_col in TASKS:
        # Reference may store either true labels (base_col) or previous predictions (pred_base_col).
        ref_col = base_col if base_col in ref_df.columns else pred_col
        if ref_col not in ref_df.columns:
            raise ValueError(f"Missing reference column for '{base_col}': expected '{base_col}' or '{pred_col}'")
        if pred_col not in pred_df.columns:
            raise ValueError(f"Missing prediction column in output: {pred_col}")

        y_true = _normalise_series(ref_df[ref_col])
        y_pred = _normalise_series(pred_df[pred_col])
        metrics[base_col] = {
            "reference_column": ref_col,
            "accuracy": round(float(accuracy_score(y_true, y_pred)), 4),
            "f1_macro": round(float(f1_score(y_true, y_pred, average="macro", zero_division=0)), 4),
        }

    report = {
        "input": str(input_path),
        "reference": str(ref_path),
        "predictions": str(pred_path),
        "model_dir": args.model_dir,
        "rows_evaluated": len(ref_df),
        "metrics": metrics,
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2))

    print(f"Rows evaluated: {len(ref_df)}")
    for base_col, _ in TASKS:
        m = metrics[base_col]
        print(
            f"{base_col}: acc={m['accuracy']:.4f}, "
            f"f1_macro={m['f1_macro']:.4f} "
            f"(ref_col={m['reference_column']})"
        )
    print(f"Saved predictions: {pred_path}")
    print(f"Saved report: {report_path}")


if __name__ == "__main__":
    main()
