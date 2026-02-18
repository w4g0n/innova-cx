import pandas as pd
import os
import random

RAW_PATH = "data/raw/dataset.csv"
OUTPUT_PATH = "data/processed/cleaned.csv"

random.seed(42)

impact_map = {"low": 0, "medium": 1}
reverse_map = {0: "low", 1: "medium", 2: "high"}


def extract_tenant_speech(transcript):
    if not isinstance(transcript, str):
        return ""

    lines = transcript.split("\n")
    tenant_lines = []

    for line in lines:
        line = line.strip()
        if line.lower().startswith("tenant:"):
            content = line.split(":", 1)[1].strip()
            tenant_lines.append(content)

    return " ".join(tenant_lines).lower()


def adjust_impact(row):
    base_label = row["business_impact"]

    # Flatten original high -> medium
    if base_label == "high":
        base_label = "medium"

    base = impact_map[base_label]

    tier = row["tenant_tier"].strip().lower()
    asset = row["asset_type"].strip().lower()

    # Tier adjustments
    if tier == "vip":
        base += 1
    elif tier == "premium" and random.random() < 0.5:
        base += 1
    elif tier == "prospective" and random.random() < 0.7:
        base -= 1

    base = max(0, min(2, base))

    # Asset adjustment
    if asset == "office" and random.random() < 0.5:
        base += 1

    base = max(0, min(2, base))

    # Controlled noise (5%)
    if random.random() < 0.05:
        base += random.choice([-1, 1])
        base = max(0, min(2, base))

    return reverse_map[base]


def main():
    df = pd.read_csv(RAW_PATH)

    # Keep only Tenant Support
    df["call_category"] = df["call_category"].astype(str).str.strip().str.lower()
    df = df[df["call_category"] == "tenant support"]

    # Clean impact
    df["business_impact"] = df["business_impact"].astype(str).str.strip().str.lower()
    df["business_impact"] = df["business_impact"].replace({
        "medium-high": "medium"
    })

    df = df[df["business_impact"].isin(["low", "medium", "high"])]

    # Extract tenant speech
    df["clean_text"] = df["transcript"].apply(extract_tenant_speech)
    df = df[df["clean_text"].str.strip() != ""]

    # Apply multi-factor impact logic
    df["business_impact"] = df.apply(adjust_impact, axis=1)

    # Remove exact duplicates
    before = len(df)
    df = df.drop_duplicates(subset=["clean_text"])
    after = len(df)

    print(f"Removed {before - after} duplicate rows.")

    os.makedirs("data/processed", exist_ok=True)
    df.to_csv(OUTPUT_PATH, index=False)

    print("Preprocessing complete.")
    print("Total rows:", len(df))
    print("\nClass distribution:")
    print(df["business_impact"].value_counts())


if __name__ == "__main__":
    main()