import pandas as pd
import random
import re

INPUT_FILE  = "DataSet_SentimentAnalysis.csv"
OUTPUT_FILE = "Synth_DataSet_Labeled_Final.csv"

# ── MANUAL LABELS ─────────────────────────────────────────────────────────────
# All 9 complaints labeled manually.
# Matched against the "issue" column by substring.
# To add a new issue: insert a new entry below.
# ─────────────────────────────────────────────────────────────────────────────
MANUAL_LABELS = {
    "security incident":        {"business_impact": "high",   "safety_concern": True},
    "power outage":             {"business_impact": "high",   "safety_concern": True},
    "parking gate malfunction": {"business_impact": "medium", "safety_concern": False},
    "air conditioning":         {"business_impact": "medium", "safety_concern": False},
    "cleaning services":        {"business_impact": "low",    "safety_concern": False},
    "water leakage":            {"business_impact": "low",    "safety_concern": False},
    "noise disturbance":        {"business_impact": "low",    "safety_concern": False},
    "lost item":                {"business_impact": "low",    "safety_concern": False},
    "access card":              {"business_impact": "low",    "safety_concern": False},
}


# ── HELPERS ───────────────────────────────────────────────────────────────────

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
    return "\n".join(user_lines).lower()


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


def assign_tenant_tier(row):
    if row["call_category"] == "inquiry":
        return "Prospective"
    tiers   = ["Standard", "Premium", "VIP"]
    weights = [0.6, 0.3, 0.1]
    return random.choices(tiers, weights=weights, k=1)[0]


def extract_issue(row):
    if row["call_category"] != "complaint":
        return None
    text = row["user_text"] if isinstance(row["user_text"], str) else ""
    matches = re.findall(r"we are facing[^.\n]*[.\n]?", text, flags=re.IGNORECASE)
    if not matches:
        return None
    return " | ".join(m.strip() for m in matches)


def apply_label(issue):
    if not isinstance(issue, str):
        return {"business_impact": None, "safety_concern": None}
    issue_lower = issue.lower()
    for keyword, label in MANUAL_LABELS.items():
        if keyword in issue_lower:
            return label
    return {"business_impact": None, "safety_concern": None}


# ── MAIN ──────────────────────────────────────────────────────────────────────

df = pd.read_csv(INPUT_FILE)
print(f"Original rows: {len(df)}")

# 1. Frequency count before dedup
frequency_series  = df["transcript"].value_counts()
df["frequency"]   = df["transcript"].map(frequency_series)
print(f"Unique transcripts before dedup: {df['transcript'].nunique()}")

# 2. Remove duplicate transcripts
df = df.drop_duplicates(subset=["transcript"]).reset_index(drop=True)
print(f"Rows after transcript dedup: {len(df)}")

# 3. Extract tenant speech
df["user_text"] = df["transcript"].apply(extract_user_speech)

# 4. Normalize call_category
df["call_category"] = df["call_category"].apply(map_call_category)

# 5. Assign tenant tier
random.seed(42)
df["tenant_tier"] = df.apply(assign_tenant_tier, axis=1)

# 6. Extract issue (complaints only)
df["issue"] = df.apply(extract_issue, axis=1)

# 7. Dedup on issue + recount frequency (complaints only)
complaints = df[df["call_category"] == "complaint"].copy()
inquiries  = df[df["call_category"] == "inquiry"].copy()

issue_frequency       = complaints["issue"].value_counts()
complaints["frequency"] = complaints["issue"].map(issue_frequency)
complaints            = complaints.drop_duplicates(subset=["issue"]).reset_index(drop=True)
print(f"Complaints after issue dedup: {len(complaints)}")

# 8. Apply manual labels (complaints only)
labels = complaints["issue"].apply(apply_label)
complaints["business_impact"] = labels.apply(lambda x: x["business_impact"])
complaints["safety_concern"]  = labels.apply(lambda x: x["safety_concern"])

# Surface unmatched complaints
unmatched = complaints[complaints["business_impact"].isna()]
if len(unmatched) > 0:
    print(f"\nUnmatched complaints — add a label for these in MANUAL_LABELS:")
    for _, row in unmatched.iterrows():
        print(f"  - {row['issue']}")

# 9. Inquiries get null labels
inquiries = inquiries.copy()
inquiries["business_impact"] = None
inquiries["safety_concern"]  = None

# 10. Combine and save
df_final = pd.concat([complaints, inquiries]).reset_index(drop=True)

print(f"\nCall Category Distribution:")
print(df_final["call_category"].value_counts())
print(f"\nTenant Tier Distribution:")
print(df_final["tenant_tier"].value_counts())
print(f"\nBusiness Impact Distribution:")
print(df_final["business_impact"].value_counts(dropna=False))
print(f"\nSafety Distribution:")
print(df_final["safety_concern"].value_counts(dropna=False))
print(f"\nTotal rows: {len(df_final)}")

df_final.to_csv(OUTPUT_FILE, index=False)
print(f"\nSaved to {OUTPUT_FILE}")