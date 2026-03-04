"""Mock evaluator for smoke tests (uses gold labels as predictions)."""

import argparse
import json
from pathlib import Path

import pandas as pd

LABEL_COLS = ["safety_concern", "business_impact", "issue_severity", "issue_urgency"]
THRESHOLDS = {
    "safety_concern": {"accuracy": 0.80, "f1_macro": 0.78},
    "business_impact": {"accuracy": 0.75, "f1_macro": 0.72},
    "issue_severity": {"accuracy": 0.75, "f1_macro": 0.72},
    "issue_urgency": {"accuracy": 0.75, "f1_macro": 0.72},
}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--test", default="test/test.csv")
    parser.add_argument("--model-dir", default="models/deberta_multitask")
    parser.add_argument("--output-report", default="output/eval_external_report.json")
    parser.add_argument("--output-preds", default="output/eval_external_predictions.csv")
    parser.add_argument("--text-col", default="text")
    args = parser.parse_args()

    df = pd.read_csv(args.test)
    required = [args.text_col] + LABEL_COLS
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"Test CSV missing columns: {missing}")

    pred_df = df.copy()
    metrics = {}

    for col in LABEL_COLS:
        pred_df[f"pred_{col}"] = pred_df[col]
        pred_df[f"pred_{col}_conf"] = 0.9999
        metrics[col] = {
            "accuracy": 1.0,
            "f1_macro": 1.0,
            "meets_threshold": {"accuracy": True, "f1_macro": True},
            "threshold": THRESHOLDS[col],
            "per_class": {},
        }

    payload = {
        "rows_evaluated": len(pred_df),
        "meets_all_thresholds": True,
        "metrics": metrics,
        "mock": True,
    }

    out_report = Path(args.output_report)
    out_preds = Path(args.output_preds)
    out_report.parent.mkdir(parents=True, exist_ok=True)
    out_preds.parent.mkdir(parents=True, exist_ok=True)

    out_report.write_text(json.dumps(payload, indent=2))
    pred_df.to_csv(out_preds, index=False)

    print(f"Saved report: {out_report}")
    print(f"Saved preds : {out_preds}")
    print(f"Rows eval   : {len(pred_df)}")


if __name__ == "__main__":
    main()
