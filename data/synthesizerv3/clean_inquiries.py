import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

# =========================
# CONFIG
# =========================
INPUT_PATH = "Synth_DataSet_Labeled_Final.csv"
OUTPUT_PATH = "Synth_DataSet_Cleaned.csv"
SIM_THRESHOLD = 0.92

# =========================
# LOAD
# =========================
df = pd.read_csv(INPUT_PATH)
df.columns = df.columns.str.strip()

# Rename column
if "call_category" in df.columns:
    df = df.rename(columns={"call_category": "ticket_type"})

# =========================
# SPLIT
# =========================
inquiries = df[df["ticket_type"] == "inquiry"].copy()
complaints = df[df["ticket_type"] == "complaint"].copy()

print("Inquiries before cleaning:", len(inquiries))

# =========================
# REMOVE EXACT DUPLICATES
# =========================
inquiries = inquiries.drop_duplicates(subset=["transcript"]).reset_index(drop=True)
print("After exact dedup:", len(inquiries))

# =========================
# REMOVE NEAR DUPLICATES
# =========================
if len(inquiries) > 1:
    vectorizer = TfidfVectorizer(stop_words="english")
    tfidf_matrix = vectorizer.fit_transform(inquiries["transcript"])

    similarity_matrix = cosine_similarity(tfidf_matrix)

    to_remove = set()

    for i in range(len(similarity_matrix)):
        if i in to_remove:
            continue
        for j in range(i + 1, len(similarity_matrix)):
            if similarity_matrix[i, j] > SIM_THRESHOLD:
                to_remove.add(j)

    inquiries = inquiries.drop(inquiries.index[list(to_remove)]).reset_index(drop=True)

print("After near-duplicate removal:", len(inquiries))

# =========================
# MERGE BACK
# =========================
df_cleaned = pd.concat([complaints, inquiries], ignore_index=True)

print("Final dataset size:", len(df_cleaned))

# =========================
# SAVE NEW FILE
# =========================
df_cleaned.to_csv(OUTPUT_PATH, index=False)

print("Saved cleaned dataset to:", OUTPUT_PATH)