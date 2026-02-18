import numpy as np
import pandas as pd

train = pd.read_csv("data/processed/train.csv")
val = pd.read_csv("data/processed/val.csv")

print(len(set(train["clean_text"]).intersection(set(val["clean_text"]))))

X_train = np.load("data/processed/embeddings/X_train.npy")
X_val = np.load("data/processed/embeddings/X_val.npy")

print("Train == Val identical?",
      np.array_equal(X_train[:10], X_val[:10]))

matches = 0
for val_vec in X_val:
    for train_vec in X_train:
        if np.array_equal(val_vec, train_vec):
            matches += 1

print("Exact vector matches:", matches)

train = pd.read_csv("data/processed/train.csv")
val = pd.read_csv("data/processed/val.csv")

overlap = set(train["clean_text"]).intersection(set(val["clean_text"]))

print("Number of overlapping texts:", len(overlap))

for i, text in enumerate(list(overlap)[:5]):
    print(f"\nExample {i+1}:\n{text[:300]}")
