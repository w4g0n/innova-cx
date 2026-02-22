import pandas as pd
import numpy as np
import os
from sklearn.feature_extraction.text import TfidfVectorizer

try:
    from sentence_transformers import SentenceTransformer
except ModuleNotFoundError:  # optional in local env
    SentenceTransformer = None

MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"

DATA_PATH = "data/processed/dataset_tenant_only.csv"
EMBED_PATH = "data/processed/embeddings/"
TARGET_COLUMNS = [
    "business_impact",
    "safety_concern",
    "issue_severity",
    "issue_urgency",
]


def main():
    print("Loading dataset...")
    df = pd.read_csv(DATA_PATH)

    texts = df["transcript"].fillna("").astype(str).tolist()
    labels_by_target = {}
    missing_targets = []
    for target in TARGET_COLUMNS:
        if target in df.columns:
            labels_by_target[target] = df[target].tolist()
        else:
            missing_targets.append(target)

    if SentenceTransformer is not None:
        model = SentenceTransformer(MODEL_NAME)
        embeddings = model.encode(
            texts,
            batch_size=8,
            show_progress_bar=True,
            convert_to_numpy=True
        )
        print(f"Embedding backend: {MODEL_NAME}")
    else:
        vectorizer = TfidfVectorizer(max_features=1024, ngram_range=(1, 2))
        embeddings = vectorizer.fit_transform(texts).toarray().astype(np.float32)
        print("Embedding backend: TF-IDF fallback (sentence-transformers not installed)")

    os.makedirs(EMBED_PATH, exist_ok=True)

    np.save(EMBED_PATH + "X.npy", embeddings)
    for target_name, labels in labels_by_target.items():
        np.save(EMBED_PATH + f"y_{target_name}.npy", np.array(labels))

    print("Embeddings saved.")
    print("Embedding shape:", embeddings.shape)
    if missing_targets:
        print("Skipped targets (missing columns):", ", ".join(missing_targets))

if __name__ == "__main__":
    main()
