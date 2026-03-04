"""Mock generator for full pipeline smoke tests (no HF/torch required)."""

import argparse
import itertools
import json
import random
from pathlib import Path

import pandas as pd


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--rows", type=int, default=2500)
    parser.add_argument("--output", default="Input/complaints_2500.csv")
    parser.add_argument("--report", default="output/balance_report.json")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    random.seed(args.seed)

    safety = ["true", "false"]
    tri = ["low", "medium", "high"]
    combos = list(itertools.product(safety, tri, tri, tri))

    rows = len(combos) if args.dry_run else args.rows
    per = rows // len(combos)
    rem = rows % len(combos)

    records = []
    for i, combo in enumerate(combos):
        n = per + (1 if i < rem else 0)
        s, bi, sev, urg = combo
        for j in range(n):
            records.append(
                {
                    "text": f"Mock complaint {i}-{j}: tenant reports issue with mixed operational/safety details.",
                    "safety_concern": s,
                    "business_impact": bi,
                    "issue_severity": sev,
                    "issue_urgency": urg,
                }
            )

    random.shuffle(records)
    df = pd.DataFrame(records)

    out = Path(args.output)
    rpt = Path(args.report)
    out.parent.mkdir(parents=True, exist_ok=True)
    rpt.parent.mkdir(parents=True, exist_ok=True)

    df.to_csv(out, index=False)
    summary = {
        "rows": len(df),
        "safety_concern": df["safety_concern"].value_counts().to_dict(),
        "business_impact": df["business_impact"].value_counts().to_dict(),
        "issue_severity": df["issue_severity"].value_counts().to_dict(),
        "issue_urgency": df["issue_urgency"].value_counts().to_dict(),
        "mock": True,
    }
    rpt.write_text(json.dumps(summary, indent=2))

    print(f"Saved dataset: {out}")
    print(f"Saved report : {rpt}")
    print(f"Rows         : {len(df)}")


if __name__ == "__main__":
    main()
