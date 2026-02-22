import re
from pathlib import Path

import pandas as pd
from sklearn.model_selection import train_test_split

RAW_DATASET_PATH = Path("data/raw/dataset.csv")
PROCESSED_DIR = Path("data/processed")
FULL_OUTPUT_PATH = PROCESSED_DIR / "dataset_tenant_only.csv"
TRAIN_OUTPUT_PATH = PROCESSED_DIR / "train.csv"
VAL_OUTPUT_PATH = PROCESSED_DIR / "val.csv"
TEST_OUTPUT_PATH = PROCESSED_DIR / "test.csv"

REQUIRED_COLUMNS = [
    "transcript",
    "business_impact",
    "issue_urgency",
    "issue_severity",
    "safety_concern",
]
TENANT_LINE_RE = re.compile(r"^\s*tenant\s*:\s*(.*)$", re.IGNORECASE)
RANDOM_STATE = 42
NA_MARKERS = {"", "unknown", "n/a", "na", "none", "null", "nan"}


def tenant_only_paragraph(transcript: str) -> str:
    if not isinstance(transcript, str):
        return ""

    parts = []
    for line in transcript.splitlines():
        match = TENANT_LINE_RE.match(line)
        if match:
            text = match.group(1).strip()
            if text:
                parts.append(text)

    if not parts:
        return " ".join(transcript.split())
    return " ".join(parts)


def normalize_label(value) -> str:
    text = "" if pd.isna(value) else str(value).strip()
    if text.lower() in NA_MARKERS:
        return "N/A"
    return text


def main() -> None:
    if not RAW_DATASET_PATH.exists():
        raise FileNotFoundError(f"Raw dataset not found: {RAW_DATASET_PATH}")

    df = pd.read_csv(RAW_DATASET_PATH)
    missing = [col for col in REQUIRED_COLUMNS if col not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    processed = df[REQUIRED_COLUMNS].copy()
    processed["transcript"] = processed["transcript"].apply(tenant_only_paragraph)
    processed = processed[processed["transcript"].str.strip() != ""].reset_index(drop=True)
    label_cols = ["business_impact", "issue_urgency", "issue_severity", "safety_concern"]
    for label_col in label_cols:
        processed[label_col] = processed[label_col].apply(normalize_label)

    # Keep N/A as explicit missing marker, then drop from training dataset.
    before_drop = len(processed)
    for label_col in label_cols:
        processed = processed[processed[label_col] != "N/A"]
    removed_na_rows = before_drop - len(processed)

    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    processed.to_csv(FULL_OUTPUT_PATH, index=False)

    # 70% train, 30% temp (stratified on business_impact)
    train_df, temp_df = train_test_split(
        processed,
        test_size=0.30,
        stratify=processed["business_impact"],
        random_state=RANDOM_STATE,
    )

    # 15% validation, 15% test (split temp equally, stratified)
    val_df, test_df = train_test_split(
        temp_df,
        test_size=0.50,
        stratify=temp_df["business_impact"],
        random_state=RANDOM_STATE,
    )

    train_df.to_csv(TRAIN_OUTPUT_PATH, index=False)
    val_df.to_csv(VAL_OUTPUT_PATH, index=False)
    test_df.to_csv(TEST_OUTPUT_PATH, index=False)

    print(f"Saved full dataset: {FULL_OUTPUT_PATH} ({len(processed)} rows)")
    print(f"Removed rows with N/A labels: {removed_na_rows}")
    print(f"Saved train split: {TRAIN_OUTPUT_PATH} ({len(train_df)} rows)")
    print(f"Saved val split: {VAL_OUTPUT_PATH} ({len(val_df)} rows)")
    print(f"Saved test split: {TEST_OUTPUT_PATH} ({len(test_df)} rows)")

    print("\nStratification check (business_impact):")
    print("Full:")
    print(processed["business_impact"].value_counts(normalize=True).round(4))
    print("\nTrain:")
    print(train_df["business_impact"].value_counts(normalize=True).round(4))
    print("\nVal:")
    print(val_df["business_impact"].value_counts(normalize=True).round(4))
    print("\nTest:")
    print(test_df["business_impact"].value_counts(normalize=True).round(4))


if __name__ == "__main__":
    main()
