import numpy as np

X_train = np.load("data/processed/embeddings/X_train.npy")
y_train = np.load("data/processed/embeddings/y_train.npy")

print(X_train.shape)
print(y_train.shape)
print(set(y_train))