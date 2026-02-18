import numpy as np
import joblib
import os
from sklearn.linear_model import LogisticRegression
from sklearn.svm import LinearSVC
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import LeaveOneOut
from sklearn.metrics import f1_score
from sklearn.preprocessing import LabelEncoder

EMBED_PATH = "data/processed/embeddings/"
BASE_MODEL_PATH = "models/"


def evaluate_model(model, X, y):
    loo = LeaveOneOut()
    preds = []

    for train_idx, test_idx in loo.split(X):
        X_train, X_test = X[train_idx], X[test_idx]
        y_train = y[train_idx]

        model.fit(X_train, y_train)
        pred = model.predict(X_test)
        preds.append(pred[0])

    return f1_score(y, preds, average="macro")


def train_target(X, y_raw, target_name):
    print(f"\n===== {target_name.upper()} =====")

    target_path = os.path.join(BASE_MODEL_PATH, target_name)
    os.makedirs(target_path, exist_ok=True)

    le = LabelEncoder()
    y = le.fit_transform(y_raw)

    print("Classes:", le.classes_)
    print("Samples:", len(y))

    models = {
        "logistic": LogisticRegression(max_iter=1000),
        "svm": LinearSVC(),
        "rf": RandomForestClassifier(n_estimators=100, random_state=42)
    }

    print("\nLOOCV Results:")

    for name, model in models.items():
        score = evaluate_model(model, X, y)
        print(f"{name}: Macro F1 = {round(score, 4)}")

    print("\nTraining final models on full dataset...")

    for name, model in models.items():
        model.fit(X, y)
        joblib.dump(model, os.path.join(target_path, f"{name}.pkl"))
        print(f"{name} saved.")

    joblib.dump(le, os.path.join(target_path, "label_encoder.pkl"))
    print("Label encoder saved.")


def main():
    X = np.load(EMBED_PATH + "X.npy")

    y_business = np.load(EMBED_PATH + "y_business_impact.npy")
    y_safety = np.load(EMBED_PATH + "y_safety_concern.npy")

    train_target(X, y_business, "business_impact")
    train_target(X, y_safety, "safety_concern")


if __name__ == "__main__":
    main()