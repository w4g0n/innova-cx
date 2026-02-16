import pandas as pd
import random

INPUT_FILE = "DataSet_SentimentAnalysis.csv"
OUTPUT_FILE = "Synth_DataSet_Preprocessed.csv"

df = pd.read_csv(INPUT_FILE)

print("Original rows:", len(df))

# ============================
# 1. Create frequency column
# ============================

frequency_series = df["transcript"].value_counts()
df["frequency"] = df["transcript"].map(frequency_series)

print("Unique transcripts before:", df["transcript"].nunique())

# ============================
# 2. Remove duplicate transcripts
# ============================

df = df.drop_duplicates(subset=["transcript"]).reset_index(drop=True)

print("Rows after duplicate removal:", len(df))
print("Unique transcripts after:", df["transcript"].nunique())

# ============================
# 3. Extract tenant speech
# ============================

def extract_user_speech(transcript):
    if not isinstance(transcript, str):
        return ""

    user_lines = []

    for line in transcript.split("\n"):
        line = line.strip()

        if ":" not in line:
            continue

        speaker, content = line.split(":", 1)
        speaker = speaker.strip().lower()
        content = content.strip()

        if speaker in ["tenant", "caller", "client"]:
            user_lines.append(content)

    return " ".join(user_lines).lower()

df["user_text"] = df["transcript"].apply(extract_user_speech)

# ============================
# 4. Normalize call_category
# ============================

def map_call_category(value):
    if pd.isna(value):
        return "complaint"

    value = value.lower().strip()

    if "leasing inquiry" in value:
        return "inquiry"
    elif "tenant support" in value:
        return "complaint"
    else:
        return "complaint"

df["call_category"] = df["call_category"].apply(map_call_category)

# ============================
# 5. Assign tenant tier
# ============================

random.seed(42)

def assign_tenant_tier(row):
    if row["call_category"] == "inquiry":
        return "Prospective"
    else:
        tiers = ["Standard", "Premium", "VIP"]
        weights = [0.6, 0.3, 0.1]
        return random.choices(tiers, weights=weights, k=1)[0]

df["tenant_tier"] = df.apply(assign_tenant_tier, axis=1)

# ============================
# 6. Sanity checks
# ============================

print(df["call_category"].value_counts())
print(df["tenant_tier"].value_counts())
print("Total unique rows:", len(df))

# ============================
# 7. Save
# ============================

df.to_csv(OUTPUT_FILE, index=False)

print("Preprocessing complete.")