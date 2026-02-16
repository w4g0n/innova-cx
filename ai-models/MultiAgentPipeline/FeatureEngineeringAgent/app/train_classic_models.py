import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.svm import LinearSVC
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import LabelEncoder
from sklearn.metrics import classification_report, f1_score


EMBED_PATH = "data/processed/embeddings/"


def load_split(split):
    X = np.load(EMBED_PATH + f"X_{split}.npy")
    y = np.load(EMBED_PATH + f"y_{split}.npy")
    return X, y


def evaluate_model(name, model, X_val, y_val):
    preds = model.predict(X_val)
    macro_f1 = f1_score(y_val, preds, average="macro")

    print(f"\n===== {name} =====")
    print("Macro F1:", round(macro_f1, 4))
    print(classification_report(y_val, preds))


def main():
    # Load embeddings
    X_train, y_train = load_split("train")
    X_val, y_val = load_split("val")

    # Encode labels to integers
    le = LabelEncoder()
    y_train_enc = le.fit_transform(y_train)
    y_val_enc = le.transform(y_val)

    print("Classes:", le.classes_)

    # 1. Logistic Regression
    log_reg = LogisticRegression(max_iter=1000)
    log_reg.fit(X_train, y_train_enc)
    evaluate_model("Logistic Regression", log_reg, X_val, y_val_enc)

    # 2. Linear SVM
    svm = LinearSVC()
    svm.fit(X_train, y_train_enc)
    evaluate_model("Linear SVM", svm, X_val, y_val_enc)

    # 3. Random Forest
    rf = RandomForestClassifier(n_estimators=200, random_state=42)
    rf.fit(X_train, y_train_enc)
    evaluate_model("Random Forest", rf, X_val, y_val_enc)


if __name__ == "__main__":
    main()