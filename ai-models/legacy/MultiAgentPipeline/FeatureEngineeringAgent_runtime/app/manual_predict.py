import argparse
import csv
import os

import joblib
import numpy as np

BASE_MODEL_PATH = "models/"
TARGETS = [
    ("business_impact", "Business Impact"),
    ("safety_concern", "Safety Concern"),
    ("issue_severity", "Issue Severity"),
    ("issue_urgency", "Issue Urgency"),
]


def load_target_artifacts(target_name):
    target_path = os.path.join(BASE_MODEL_PATH, target_name)
    if not os.path.isdir(target_path):
        raise FileNotFoundError(f"Missing model directory: {target_path}")

    models = {
        "Logistic": joblib.load(os.path.join(target_path, "logistic.pkl")),
        "SVM": joblib.load(os.path.join(target_path, "svm.pkl")),
        "RandomForest": joblib.load(os.path.join(target_path, "rf.pkl")),
    }
    label_encoder = joblib.load(os.path.join(target_path, "label_encoder.pkl"))

    vectorizer_path = os.path.join(target_path, "tfidf_vectorizer.pkl")
    if os.path.exists(vectorizer_path):
        vectorizer = joblib.load(vectorizer_path)
    else:
        global_vec_path = os.path.join(BASE_MODEL_PATH, "tfidf_vectorizer.pkl")
        if os.path.exists(global_vec_path):
            vectorizer = joblib.load(global_vec_path)
        else:
            raise FileNotFoundError(
                f"No TF-IDF vectorizer found for {target_name}. "
                f"Expected {vectorizer_path} or {global_vec_path}."
            )

    return models, label_encoder, vectorizer


def load_all_target_artifacts():
    artifacts = {}
    for target_name, _ in TARGETS:
        target_path = os.path.join(BASE_MODEL_PATH, target_name)
        if not os.path.isdir(target_path):
            continue
        artifacts[target_name] = load_target_artifacts(target_name)
    return artifacts


def read_issue_text(cli_text):
    if cli_text:
        return cli_text.strip()

    print("Paste your issue text. Press Enter on an empty line to finish:\n")
    lines = []
    while True:
        line = input()
        if line.strip() == "":
            break
        lines.append(line.rstrip())

    return "\n".join(lines).strip()


def predict_labels_for_text(text, artifacts_by_target):
    if not text:
        raise ValueError("Issue text is empty.")

    predictions = {}
    for target_name, target_label in TARGETS:
        if target_name not in artifacts_by_target:
            predictions[target_name] = {
                "display": target_label,
                "skipped": True,
                "values": {},
            }
            continue

        models, label_encoder, vectorizer = artifacts_by_target[target_name]
        X = vectorizer.transform([text]).toarray().astype(np.float32)
        values = {}
        for model_name, model in models.items():
            pred = model.predict(X)
            label = label_encoder.inverse_transform(pred)[0]
            values[model_name] = label

        predictions[target_name] = {
            "display": target_label,
            "skipped": False,
            "values": values,
        }

    return predictions


def predict_for_text(text, artifacts_by_target):
    print("\n" + "=" * 70)
    print("INPUT ISSUE")
    print("=" * 70)
    print(text)

    predictions = predict_labels_for_text(text, artifacts_by_target)
    for target_name, target_label in TARGETS:
        target_pred = predictions[target_name]
        if target_pred["skipped"]:
            print(f"\n[{target_label}] skipped: models not found")
            continue

        print("\n" + "-" * 70)
        print(f"{target_label} Predictions")
        print("-" * 70)
        for model_name, label in target_pred["values"].items():
            print(f"{model_name}: {label}")


def predict_for_csv(input_csv_path, output_csv_path, text_column):
    artifacts_by_target = load_all_target_artifacts()
    if not artifacts_by_target:
        raise FileNotFoundError("No model artifacts found under models/<target>/")

    with open(input_csv_path, "r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        if text_column not in (reader.fieldnames or []):
            raise ValueError(
                f"Input CSV must contain '{text_column}' column. "
                f"Columns found: {reader.fieldnames}"
            )
        rows = list(reader)

    output_rows = []
    for idx, row in enumerate(rows, start=1):
        text = (row.get(text_column) or "").strip()
        if not text:
            continue

        preds = predict_labels_for_text(text, artifacts_by_target)
        out = {
            "id": row.get("id", str(idx)),
            text_column: text,
        }
        for target_name, _ in TARGETS:
            target_pred = preds[target_name]
            if target_pred["skipped"]:
                continue
            for model_name, label in target_pred["values"].items():
                key = f"{target_name}_{model_name.lower()}"
                out[key] = label
        output_rows.append(out)

    if not output_rows:
        raise ValueError("No non-empty issue text rows found in input CSV.")

    os.makedirs(os.path.dirname(output_csv_path) or ".", exist_ok=True)
    fieldnames = list(output_rows[0].keys())
    with open(output_csv_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(output_rows)

    print(f"Saved predictions: {output_csv_path}")
    print(f"Rows predicted: {len(output_rows)}")


def main():
    parser = argparse.ArgumentParser(
        description="Manual prediction for FeatureEngineeringAgent classic models."
    )
    parser.add_argument(
        "--text",
        type=str,
        default="",
        help="Issue text to predict. If omitted, interactive input is used.",
    )
    parser.add_argument(
        "--input-csv",
        type=str,
        default="",
        help="Path to CSV file with complaints to batch predict.",
    )
    parser.add_argument(
        "--output-csv",
        type=str,
        default="",
        help="Path to save batch predictions CSV (required with --input-csv).",
    )
    parser.add_argument(
        "--text-column",
        type=str,
        default="issue_text",
        help="Input CSV text column name. Default: issue_text",
    )
    args = parser.parse_args()

    if args.input_csv:
        if not args.output_csv:
            raise ValueError("--output-csv is required when using --input-csv")
        predict_for_csv(args.input_csv, args.output_csv, args.text_column)
        return

    artifacts_by_target = load_all_target_artifacts()
    if not artifacts_by_target:
        raise FileNotFoundError("No model artifacts found under models/<target>/")

    issue_text = read_issue_text(args.text)
    predict_for_text(issue_text, artifacts_by_target)


if __name__ == "__main__":
    main()
