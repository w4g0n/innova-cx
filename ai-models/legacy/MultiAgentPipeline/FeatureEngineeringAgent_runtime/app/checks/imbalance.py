import pandas as pd

df = pd.read_csv("data/processed/cleaned.csv")

print("Tenant tier distribution:")
print(df["tenant_tier"].value_counts())

print("\nCross-tab impact vs tier:")
print(pd.crosstab(df["business_impact"], df["tenant_tier"]))

df = pd.read_csv("data/raw/dataset.csv")

# Normalize
df["tenant_tier"] = df["tenant_tier"].astype(str).str.strip()
df["call_category"] = df["call_category"].astype(str).str.strip()

print("Prospective count total:")
print((df["tenant_tier"] == "Prospective").sum())

print("\nProspective by call_category:")
print(pd.crosstab(df["tenant_tier"], df["call_category"]))
