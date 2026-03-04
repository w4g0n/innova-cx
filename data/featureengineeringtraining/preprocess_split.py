"""Preprocess and stratified split for feature engineering multitask training."""

import argparse
import json
from pathlib import Path

import pandas as pd
from sklearn.model_selection import train_test_split

REQUIRED_COLS = [
    "text",
    "safety_concern",
    "business_impact",
    "issue_severity",
    "issue_urgency",
]


def normalise_safety(val) -> str:
    return "true" if str(val).strip().lower() in ("true", "1", "yes") else "false"


def normalise_tri(val) -> str:
    return str(val).strip().lower()


def validate_labels(df: pd.DataFrame) -> None:
    tri_valid = {"low", "medium", "high"}
    safety_valid = {"true", "false"}

    if not set(df["business_impact"]).issubset(tri_valid):
        raise ValueError("Invalid labels in business_impact")
    if not set(df["issue_severity"]).issubset(tri_valid):
        raise ValueError("Invalid labels in issue_severity")
    if not set(df["issue_urgency"]).issubset(tri_valid):
        raise ValueError("Invalid labels in issue_urgency")
    if not set(df["safety_concern"]).issubset(safety_valid):
        raise ValueError("Invalid labels in safety_concern")


def write_distribution(df: pd.DataFrame, path: Path, title: str) -> None:
    report = {
        "name": title,
        "rows": len(df),
        "safety_concern": df["safety_concern"].value_counts().to_dict(),
        "business_impact": df["business_impact"].value_counts().to_dict(),
        "issue_severity": df["issue_severity"].value_counts().to_dict(),
        "issue_urgency": df["issue_urgency"].value_counts().to_dict(),
    }
    path.write_text(json.dumps(report, indent=2))


def main():
    parser = argparse.ArgumentParser(description="Split dataset into train/val/test with combined-label stratification")
    parser.add_argument("--input", default="Input/complaints_2500.csv")
    parser.add_argument("--train-output", default="output/train.csv")
    parser.add_argument("--val-output", default="output/val.csv")
    parser.add_argument("--test-output", default="test/test.csv")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    df = pd.read_csv(args.input)

    missing = [c for c in REQUIRED_COLS if c not in df.columns]
    if missing:
        raise ValueError(f"Input CSV missing columns: {missing}")

    df = df[REQUIRED_COLS].dropna().copy()
    df["text"] = df["text"].astype(str).str.strip()
    df = df[df["text"] != ""].reset_index(drop=True)

    df["safety_concern"] = df["safety_concern"].apply(normalise_safety)
    for col in ("business_impact", "issue_severity", "issue_urgency"):
        df[col] = df[col].apply(normalise_tri)

    validate_labels(df)

    df["combined_label"] = (
        df["safety_concern"]
        + "_"
        + df["business_impact"]
        + "_"
        + df["issue_severity"]
        + "_"
        + df["issue_urgency"]
    )

    counts = df["combined_label"].value_counts()
    n_classes = int(counts.shape[0])
    first_test_size = int(round(len(df) * 0.2))
    use_stratify = counts.min() >= 3 and first_test_size >= n_classes
    if not use_stratify:
        print(
            "[WARN] Dataset too small for strict combined-label stratification. "
            "Falling back to random split."
        )

    train_df, temp_df = train_test_split(
        df,
        test_size=0.2,
        stratify=df["combined_label"] if use_stratify else None,
        random_state=args.seed,
    )

    temp_counts = temp_df["combined_label"].value_counts()
    temp_n_classes = int(temp_counts.shape[0])
    second_test_size = int(round(len(temp_df) * 0.5))
    use_second_stratify = temp_counts.min() >= 2 and second_test_size >= temp_n_classes
    if not use_second_stratify:
        print(
            "[WARN] Temp split too small for second stratification step. "
            "Using random val/test split."
        )

    val_df, test_df = train_test_split(
        temp_df,
        test_size=0.5,
        stratify=temp_df["combined_label"] if use_second_stratify else None,
        random_state=args.seed,
    )

    train_df = train_df.drop(columns=["combined_label"]).reset_index(drop=True)
    val_df = val_df.drop(columns=["combined_label"]).reset_index(drop=True)
    test_df = test_df.drop(columns=["combined_label"]).reset_index(drop=True)

    train_path = Path(args.train_output)
    val_path = Path(args.val_output)
    test_path = Path(args.test_output)

    train_path.parent.mkdir(parents=True, exist_ok=True)
    val_path.parent.mkdir(parents=True, exist_ok=True)
    test_path.parent.mkdir(parents=True, exist_ok=True)

    train_df.to_csv(train_path, index=False)
    val_df.to_csv(val_path, index=False)
    test_df.to_csv(test_path, index=False)

    write_distribution(train_df, train_path.parent / "distribution_train.json", "train")
    write_distribution(val_df, val_path.parent / "distribution_val.json", "val")
    write_distribution(test_df, test_path.parent / "distribution_test.json", "test")

    print(f"Saved train: {train_path} ({len(train_df)} rows)")
    print(f"Saved val  : {val_path} ({len(val_df)} rows)")
    print(f"Saved test : {test_path} ({len(test_df)} rows)")


if __name__ == "__main__":
    main()
