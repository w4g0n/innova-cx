"""
merge_training_data.py — Merge base labeled data with additional synthetic rows.
"""

import argparse
from pathlib import Path

import pandas as pd


def normalize_text(s: str) -> str:
    return " ".join(str(s).strip().lower().split())


def main():
    parser = argparse.ArgumentParser(description="Merge training CSVs with de-duplication")
    parser.add_argument("--base", default="labeled.csv", help="Existing labeled training CSV")
    parser.add_argument("--add", required=True, help="Additional rows CSV")
    parser.add_argument("--output", default="labeled_augmented.csv")
    args = parser.parse_args()

    base_df = pd.read_csv(args.base)
    add_df = pd.read_csv(args.add)

    required = [
        "ticket_type", "subject", "text", "domain",
        "issue_severity", "issue_urgency", "safety_concern", "business_impact",
    ]
    missing = [c for c in required if c not in add_df.columns]
    if missing:
        raise ValueError(f"--add CSV missing required columns: {missing}")

    merged = pd.concat([base_df, add_df[required]], ignore_index=True)
    merged["_text_key"] = merged["text"].apply(normalize_text)
    before = len(merged)
    merged = merged.drop_duplicates(subset=["_text_key"], keep="first").drop(columns=["_text_key"])

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    merged.to_csv(output_path, index=False)

    complaints = merged[merged["ticket_type"].astype(str).str.lower().eq("complaint")]
    print(f"Saved: {output_path}")
    print(f"Rows: {len(merged)} (dropped {before - len(merged)} duplicates)")
    print(f"Complaints: {len(complaints)}")
    if "safety_concern" in complaints.columns:
        print(f"safety_concern=True: {int(complaints['safety_concern'].astype(str).str.lower().eq('true').sum())}")
        print(f"safety_concern=False: {int(complaints['safety_concern'].astype(str).str.lower().eq('false').sum())}")


if __name__ == "__main__":
    main()
