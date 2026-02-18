import pandas as pd
import numpy as np

# -------------------------------------
# LOAD
# -------------------------------------
df = pd.read_csv("synthetic_dataset_augmented.csv")

print("\n=== BASIC INFO ===")
print("Total rows:", len(df))
print(df.info())

# -------------------------------------
# CLASS DISTRIBUTION
# -------------------------------------
print("\n=== TICKET TYPE DISTRIBUTION ===")
print(df["ticket_type"].value_counts(normalize=True))

print("\n=== BUSINESS IMPACT DISTRIBUTION ===")
print(df["business_impact"].value_counts(normalize=True, dropna=False))

print("\n=== SAFETY DISTRIBUTION ===")
print(df["safety_concern"].value_counts(normalize=True, dropna=False))

# -------------------------------------
# TEXT LENGTH ANALYSIS
# -------------------------------------
df["char_length"] = df["ticket_details"].str.len()
df["word_count"] = df["ticket_details"].str.split().apply(len)

print("\n=== TEXT LENGTH STATS ===")
print(df["char_length"].describe())
print(df["word_count"].describe())

print("\n=== LENGTH BY TICKET TYPE ===")
print(df.groupby("ticket_type")["word_count"].describe())

# -------------------------------------
# IMPACT vs SAFETY CROSS-TAB
# -------------------------------------
print("\n=== IMPACT vs SAFETY (COMPLAINTS ONLY) ===")
complaints = df[df["ticket_type"] == "Complaint"]
print(pd.crosstab(complaints["business_impact"],
                  complaints["safety_concern"],
                  normalize="index"))

# -------------------------------------
# ISSUE CATEGORY BALANCE
# -------------------------------------
print("\n=== ISSUE CATEGORY DISTRIBUTION (COMPLAINTS) ===")
print(complaints["issue_category"].value_counts(normalize=True))

print("\n=== ISSUE CATEGORY DISTRIBUTION (INQUIRIES) ===")
inquiries = df[df["ticket_type"] == "Inquiry"]
print(inquiries["issue_category"].value_counts(normalize=True))

# -------------------------------------
# ISSUE → IMPACT DOMINANCE CHECK
# -------------------------------------
print("\n=== ISSUE → IMPACT DOMINANCE CHECK ===")

issue_impact_table = pd.crosstab(
    complaints["issue_category"],
    complaints["business_impact"],
    normalize="index"
)

print(issue_impact_table)

# Flag suspicious dominance (>80% single impact)
print("\n=== POTENTIAL SHORTCUT PATTERNS ===")
for issue, row in issue_impact_table.iterrows():
    if row.max() > 0.8:
        print(f"WARNING: {issue} heavily dominated by {row.idxmax()} ({row.max():.2f})")

# -------------------------------------
# DUPLICATE CHECK
# -------------------------------------
print("\n=== DUPLICATE CHECK ===")
duplicate_count = df.duplicated(subset=["ticket_details"]).sum()
print("Exact duplicates remaining:", duplicate_count)

# -------------------------------------
# VOCABULARY DIVERSITY CHECK
# -------------------------------------
all_text = " ".join(df["ticket_details"])
tokens = all_text.lower().split()
unique_tokens = set(tokens)

print("\n=== VOCABULARY DIVERSITY ===")
print("Total tokens:", len(tokens))
print("Unique tokens:", len(unique_tokens))
print("Type-Token Ratio:", len(unique_tokens) / len(tokens))

# -------------------------------------
# HIGH IMPACT WITHOUT SAFETY CHECK
# -------------------------------------
print("\n=== HIGH IMPACT WITHOUT SAFETY ===")
high_no_safety = complaints[
    (complaints["business_impact"] == "high") &
    (complaints["safety_concern"] == False)
]
print("Count:", len(high_no_safety))
print("Percentage of high impact:", len(high_no_safety) / len(complaints[complaints["business_impact"] == "high"]))

print("\n=== DONE ===")