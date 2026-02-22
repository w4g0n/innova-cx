import json
import os

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, f1_score
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder
from sklearn.svm import LinearSVC

try:
    from sentence_transformers import SentenceTransformer
except ModuleNotFoundError:
    SentenceTransformer = None

DATASET_PATH = "data/processed/dataset_tenant_only.csv"
BASE_MODEL_PATH = "models/"
TEXT_COLUMN = "transcript"
EMBED_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"

TARGETS = [
    "business_impact",
    "safety_concern",
    "issue_severity",
    "issue_urgency",
]

RANDOM_STATE = 42
TRAIN_RATIO = 0.70
VAL_RATIO = 0.15
TEST_RATIO = 0.15
NA_MARKERS = {"", "unknown", "n/a", "na", "none", "null", "nan"}


def _metrics(y_true, y_pred):
    return {
        "macro_f1": round(float(f1_score(y_true, y_pred, average="macro")), 4),
        "accuracy": round(float(accuracy_score(y_true, y_pred)), 4),
    }


def _build_embeddings(train_texts, val_texts, test_texts):
    if SentenceTransformer is not None:
        embedder = SentenceTransformer(EMBED_MODEL_NAME)
        X_train = embedder.encode(train_texts, batch_size=8, show_progress_bar=True, convert_to_numpy=True)
        X_val = embedder.encode(val_texts, batch_size=8, show_progress_bar=True, convert_to_numpy=True)
        X_test = embedder.encode(test_texts, batch_size=8, show_progress_bar=True, convert_to_numpy=True)
        return X_train, X_val, X_test, None, EMBED_MODEL_NAME

    vectorizer = TfidfVectorizer(max_features=1024, ngram_range=(1, 2))
    X_train = vectorizer.fit_transform(train_texts).toarray().astype(np.float32)
    X_val = vectorizer.transform(val_texts).toarray().astype(np.float32)
    X_test = vectorizer.transform(test_texts).toarray().astype(np.float32)
    return X_train, X_val, X_test, vectorizer, "tfidf"


def _can_stratify(labels: pd.Series) -> bool:
    counts = labels.value_counts(dropna=False)
    return len(counts) > 1 and counts.min() >= 2


def _normalize_target_label(value):
    text = "" if pd.isna(value) else str(value).strip()
    if text.lower() in NA_MARKERS:
        return "N/A"
    return text


def _split_for_target(df: pd.DataFrame, target_name: str):
    work = df[[TEXT_COLUMN, target_name]].copy()
    work[target_name] = work[target_name].apply(_normalize_target_label)
    work[TEXT_COLUMN] = work[TEXT_COLUMN].fillna("").astype(str)
    work = work[work[TEXT_COLUMN].str.strip() != ""].reset_index(drop=True)
    work = work[work[target_name] != "N/A"].reset_index(drop=True)

    stratify_labels = work[target_name] if _can_stratify(work[target_name]) else None

    # 70% train, 30% temp
    train_df, temp_df = train_test_split(
        work,
        test_size=(1.0 - TRAIN_RATIO),
        random_state=RANDOM_STATE,
        stratify=stratify_labels,
    )

    # Split temp into val/test (50/50 => 15% / 15%)
    temp_stratify = temp_df[target_name] if _can_stratify(temp_df[target_name]) else None
    val_df, test_df = train_test_split(
        temp_df,
        test_size=0.50,
        random_state=RANDOM_STATE,
        stratify=temp_stratify,
    )

    return train_df, val_df, test_df


def train_target(df: pd.DataFrame, target_name: str):
    print(f"\n===== {target_name.upper()} =====")
    target_path = os.path.join(BASE_MODEL_PATH, target_name)
    os.makedirs(target_path, exist_ok=True)

    train_df, val_df, test_df = _split_for_target(df, target_name)

    train_texts = train_df[TEXT_COLUMN].tolist()
    val_texts = val_df[TEXT_COLUMN].tolist()
    test_texts = test_df[TEXT_COLUMN].tolist()

    X_train, X_val, X_test, vectorizer, embed_backend = _build_embeddings(
        train_texts, val_texts, test_texts
    )
    print(f"Embedding backend: {embed_backend}")

    if vectorizer is not None:
        joblib.dump(vectorizer, os.path.join(target_path, "tfidf_vectorizer.pkl"))

    y_train_raw = train_df[target_name].to_numpy()
    y_val_raw = val_df[target_name].to_numpy()
    y_test_raw = test_df[target_name].to_numpy()

    le = LabelEncoder()
    le.fit(np.concatenate([y_train_raw, y_val_raw, y_test_raw], axis=0))
    y_train = le.transform(y_train_raw)
    y_val = le.transform(y_val_raw)
    y_test = le.transform(y_test_raw)

    print("Classes:", le.classes_)
    print("Samples (train/val/test):", len(y_train), len(y_val), len(y_test))

    models = {
        "logistic": LogisticRegression(max_iter=1000, random_state=RANDOM_STATE),
        "svm": LinearSVC(),
        "rf": RandomForestClassifier(n_estimators=200, random_state=RANDOM_STATE),
    }

    metrics = {}
    print("\nValidation/Test Results:")
    for model_name, model in models.items():
        model.fit(X_train, y_train)
        val_pred = model.predict(X_val)
        test_pred = model.predict(X_test)

        val_metrics = _metrics(y_val, val_pred)
        test_metrics = _metrics(y_test, test_pred)
        metrics[model_name] = {
            "val": val_metrics,
            "test": test_metrics,
        }

        print(
            f"{model_name}: "
            f"Val F1={val_metrics['macro_f1']}, Val Acc={val_metrics['accuracy']} | "
            f"Test F1={test_metrics['macro_f1']}, Test Acc={test_metrics['accuracy']}"
        )

        joblib.dump(model, os.path.join(target_path, f"{model_name}.pkl"))

    joblib.dump(le, os.path.join(target_path, "label_encoder.pkl"))
    with open(os.path.join(target_path, "metrics.json"), "w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=2)

    split_info = {
        "train_size": len(train_df),
        "val_size": len(val_df),
        "test_size": len(test_df),
        "ratios": {"train": TRAIN_RATIO, "val": VAL_RATIO, "test": TEST_RATIO},
        "stratified_by": target_name,
    }
    with open(os.path.join(target_path, "split_info.json"), "w", encoding="utf-8") as f:
        json.dump(split_info, f, indent=2)


def main():
    df = pd.read_csv(DATASET_PATH)
    if TEXT_COLUMN not in df.columns:
        raise ValueError(f"Missing '{TEXT_COLUMN}' column in dataset.")

    os.makedirs(BASE_MODEL_PATH, exist_ok=True)
    for target_name in TARGETS:
        if target_name not in df.columns:
            print(f"Skipping {target_name}: column missing in dataset.")
            continue
        train_target(df, target_name)


if __name__ == "__main__":
    main()
