"""Mock training stage for smoke tests (creates expected artifacts)."""

import argparse
import json
from pathlib import Path

import pandas as pd

LABEL_COLS = ["safety_concern", "business_impact", "issue_severity", "issue_urgency"]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--train", default="output/train.csv")
    parser.add_argument("--val", default="output/val.csv")
    parser.add_argument("--output-dir", default="models/deberta_multitask")
    parser.add_argument("--epochs", type=int, default=1)
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--learning-rate", type=float, default=2e-5)
    parser.add_argument("--base-model", default="mock/deberta-v3-small")
    args = parser.parse_args()

    train_df = pd.read_csv(args.train)
    val_df = pd.read_csv(args.val)

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # Placeholder checkpoint artifact expected by run_pipeline.
    (out_dir / "model.pt").write_bytes(b"mock-model")

    label_classes = {
        "safety_concern": ["false", "true"],
        "business_impact": ["low", "medium", "high"],
        "issue_severity": ["low", "medium", "high"],
        "issue_urgency": ["low", "medium", "high"],
    }
    (out_dir / "label_classes.json").write_text(json.dumps(label_classes, indent=2))
    (out_dir / "model_config.json").write_text(
        json.dumps(
            {
                "base_model": args.base_model,
                "max_length": 128,
                "mock": True,
            },
            indent=2,
        )
    )

    # Minimal tokenizer placeholder files so downstream tooling sees a complete directory.
    (out_dir / "tokenizer_config.json").write_text(json.dumps({"mock": True}, indent=2))
    (out_dir / "special_tokens_map.json").write_text(json.dumps({}, indent=2))

    report = {
        "best_val_metrics": {
            col: {"accuracy": 1.0, "f1_macro": 1.0} for col in LABEL_COLS
        },
        "rows": {"train": len(train_df), "val": len(val_df)},
        "mock": True,
    }
    report_path = Path("output/evaluation_report.json")
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2))

    print(f"Saved model: {out_dir / 'model.pt'}")
    print(f"Saved report: {report_path}")


if __name__ == "__main__":
    main()
