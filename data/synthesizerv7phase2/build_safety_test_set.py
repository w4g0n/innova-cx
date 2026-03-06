"""
build_safety_test_set.py — Build a new safety-focused test set from guarded predictions.
"""

import argparse
import random
from pathlib import Path

import pandas as pd


def main():
    parser = argparse.ArgumentParser(description="Create safety-focused test set candidates")
    parser.add_argument("--predictions", default="output/predictions_guarded.csv")
    parser.add_argument("--output", default="output/safety_test_candidates.csv")
    parser.add_argument("--n", type=int, default=300, help="Total candidate rows")
    parser.add_argument("--n-review", type=int, default=140, help="Rows sampled from needs_review=True")
    parser.add_argument("--n-safety-true", type=int, default=120, help="Rows sampled from pred_safety_concern=True")
    parser.add_argument("--n-random", type=int, default=40, help="Rows sampled randomly for coverage")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    if args.n_review + args.n_safety_true + args.n_random > args.n:
        raise ValueError("n-review + n-safety-true + n-random cannot exceed --n")

    random.seed(args.seed)
    df = pd.read_csv(args.predictions)

    for col in ("needs_review", "pred_safety_concern"):
        if col not in df.columns:
            raise ValueError(f"Missing required column in predictions file: {col}")

    if "ticket_type" in df.columns:
        df = df[df["ticket_type"].astype(str).str.lower().eq("complaint")].copy()

    def sample_block(src: pd.DataFrame, k: int) -> pd.DataFrame:
        if k <= 0 or len(src) == 0:
            return src.head(0).copy()
        return src.sample(n=min(k, len(src)), random_state=args.seed)

    review_block = sample_block(df[df["needs_review"].eq(True)], args.n_review)
    remaining = df.drop(index=review_block.index)

    safety_block = sample_block(remaining[remaining["pred_safety_concern"].eq(True)], args.n_safety_true)
    remaining = remaining.drop(index=safety_block.index)

    random_block = sample_block(remaining, args.n_random)
    selected = pd.concat([review_block, safety_block, random_block], ignore_index=True)

    if len(selected) < args.n:
        rest = df.drop(index=selected.index, errors="ignore")
        if len(rest) > 0:
            topup = rest.sample(n=min(args.n - len(selected), len(rest)), random_state=args.seed)
            selected = pd.concat([selected, topup], ignore_index=True)

    selected = selected.head(args.n).copy()
    selected["gold_issue_severity"] = ""
    selected["gold_issue_urgency"] = ""
    selected["gold_safety_concern"] = ""
    selected["gold_business_impact"] = ""
    selected["annotator_notes"] = ""

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    selected.to_csv(output_path, index=False)

    print(f"Saved: {output_path}")
    print(f"Rows: {len(selected)}")
    print(f"needs_review=True: {int(selected['needs_review'].eq(True).sum())}")
    print(f"pred_safety_concern=True: {int(selected['pred_safety_concern'].eq(True).sum())}")


if __name__ == "__main__":
    main()
