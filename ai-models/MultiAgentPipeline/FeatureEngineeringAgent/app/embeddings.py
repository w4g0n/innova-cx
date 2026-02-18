import pandas as pd
import numpy as np
import os
from sentence_transformers import SentenceTransformer

MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"

DATA_PATH = "data/raw/dataset.csv"
EMBED_PATH = "data/processed/embeddings/"


def main():
    print("Loading dataset...")
    df = pd.read_csv(DATA_PATH)

    # Filter complaints only
    df = df[df["call_category"] == "complaint"].reset_index(drop=True)

    texts = df["user_text"].tolist()
    impact_labels = df["business_impact"].tolist()
    safety_labels = df["safety_concern"].tolist()

    model = SentenceTransformer(MODEL_NAME)

    embeddings = model.encode(
        texts,
        batch_size=8,
        show_progress_bar=True,
        convert_to_numpy=True
    )

    os.makedirs(EMBED_PATH, exist_ok=True)

    np.save(EMBED_PATH + "X.npy", embeddings)
    np.save(EMBED_PATH + "y_business_impact.npy", np.array(impact_labels))
    np.save(EMBED_PATH + "y_safety_concern.npy", np.array(safety_labels))

    print("Embeddings saved.")
    print("Embedding shape:", embeddings.shape)

if __name__ == "__main__":
    main()