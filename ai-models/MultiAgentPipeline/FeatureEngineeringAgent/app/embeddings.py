import pandas as pd
import numpy as np
import os
from sentence_transformers import SentenceTransformer

MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"

DATA_PATH = "data/processed/"
EMBED_PATH = "data/processed/embeddings/"


def encode_split(model, split_name):
    df = pd.read_csv(DATA_PATH + f"{split_name}.csv")

    texts = df["clean_text"].tolist()
    labels = df["business_impact"].tolist()

    print(f"Encoding {split_name} set ({len(texts)} samples)...")

    embeddings = model.encode(
        texts,
        batch_size=32,
        show_progress_bar=True,
        convert_to_numpy=True
    )

    os.makedirs(EMBED_PATH, exist_ok=True)

    np.save(EMBED_PATH + f"X_{split_name}.npy", embeddings)
    np.save(EMBED_PATH + f"y_{split_name}.npy", np.array(labels))

    print(f"{split_name} saved. Shape: {embeddings.shape}")


def main():
    model = SentenceTransformer(MODEL_NAME)

    encode_split(model, "train")
    encode_split(model, "val")
    encode_split(model, "test")

    print("All embeddings generated and frozen.")


if __name__ == "__main__":
    main()