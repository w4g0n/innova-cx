"""
Complaint / Inquiry Classifier — Training Script
==================================================

Problem with TF-IDF on synthetic data: CV accuracy is 1.0 (memorisation),
but natural-language accuracy is ~0.48 (predicts everything as complaint).
Root cause: TF-IDF learns synthetic template phrases ("I am calling to inquire
about...") that never appear in real chatbot messages.

Solution: linguistic features that work on ANY natural language input + a
small character n-gram TF-IDF for supporting evidence. Combined with heavy
L2 regularisation (C=0.1) so the model learns generalisable signals.

Linguistic features used:
  - has_question_mark       : ? in text (strongest inquiry signal)
  - starts_question_word    : how/what/where/when/why/can/could/... at start
  - question_word_count     : count of question words anywhere in text
  - complaint_keyword_count : broken/not working/leak/fault/outage/...
  - inquiry_keyword_count   : information/status/guide/help/advise/...
  - normalised_length       : word count / 50 (longer = likely detailed complaint)

Datasets:
  - v4 (3,137 rows): synthetic single-sentence messages — OPTIONAL (skipped if missing)
  - v7 (318 rows): natural language chatbot-style messages — REQUIRED
  - v2 (401 rows): dialogue transcripts — skipped (format too different from production)

Note: training on v7 only (natural language) produces better generalisation
for real chatbot input than the v4-dominated combined set.

Output: single model.pkl Pipeline saved to agents/classifier/model/model.pkl

Usage (run from repo root):
    python ai-models/MultiAgentPipeline/Orchestrator/agents/classifier/train_classifier.py

Dependencies:
    pip install scikit-learn pandas joblib numpy
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report, accuracy_score
from sklearn.model_selection import StratifiedKFold, cross_validate, train_test_split
from sklearn.pipeline import FeatureUnion, Pipeline

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
logger = logging.getLogger(__name__)

# ── Paths ──────────────────────────────────────────────────────────────────────
REPO_ROOT = Path(__file__).resolve().parents[5]   # .../innova-cx

# Import LinguisticFeatureExtractor from the shared module so that
# the pickled Pipeline can be unpickled in the subprocess runtime worker.
_STEP03_DIR = REPO_ROOT / "ai-models" / "MultiAgentPipeline" / "Orchestrator" / "agents" / "step03_classifier"
if str(_STEP03_DIR) not in sys.path:
    sys.path.insert(0, str(_STEP03_DIR))
from feature_extractor import LinguisticFeatureExtractor  # noqa: E402

V4_CSV = REPO_ROOT / "data" / "synthesizerv4" / "synthetic_dataset.csv"
V7_CSV = REPO_ROOT / "data" / "synthesizerv7" / "output" / "labeled.csv"

OUTPUT_DIR = Path(__file__).resolve().parent / "model"
OUTPUT_PATH = OUTPUT_DIR / "model.pkl"

VALID_LABELS = {"complaint", "inquiry"}

# LinguisticFeatureExtractor is imported from the shared feature_extractor
# module (step03_classifier/feature_extractor.py) so that the pickled Pipeline
# unpickles correctly in the subprocess runtime worker.

# ── Data loading ───────────────────────────────────────────────────────────────

def _load_v4(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, usecols=["ticket_details", "ticket_type"])
    df = df.rename(columns={"ticket_details": "text", "ticket_type": "label"})
    df["label"] = df["label"].str.strip().str.lower()
    return df


def _load_v7(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, usecols=["text", "ticket_type"])
    df = df.rename(columns={"ticket_type": "label"})
    df["label"] = df["label"].str.strip().str.lower()
    return df


def _clean(df: pd.DataFrame) -> pd.DataFrame:
    df = df.dropna(subset=["text", "label"])
    df = df[df["label"].isin(VALID_LABELS)]
    df["text"] = df["text"].str.strip()
    df = df[df["text"].str.len() > 0]
    return df.reset_index(drop=True)


# ── Main ───────────────────────────────────────────────────────────────────────

def main() -> None:
    if not V7_CSV.exists():
        logger.error("Required dataset not found: %s", V7_CSV)
        sys.exit(1)

    if not V4_CSV.exists():
        logger.warning(
            "Optional v4 synthetic dataset not found at %s — training on v7 only. "
            "This produces better generalisation for natural-language chatbot input.",
            V4_CSV,
        )

    df_v7 = _clean(_load_v7(V7_CSV))
    logger.info("v7 rows=%d  dist:\n%s", len(df_v7), df_v7["label"].value_counts().to_string())

    if V4_CSV.exists():
        df_v4 = _clean(_load_v4(V4_CSV))
        logger.info("v4 rows=%d  dist:\n%s", len(df_v4), df_v4["label"].value_counts().to_string())
        df_all = pd.concat([df_v4, df_v7], ignore_index=True)
        logger.info("Combined v4+v7: %d rows", len(df_all))
    else:
        df_all = df_v7
        logger.info("Training on v7 only: %d rows", len(df_all))

    X_all = df_all["text"].tolist()
    y_all = df_all["label"].tolist()

    # 80/20 stratified split
    X_train, X_test, y_train, y_test = train_test_split(
        X_all, y_all, test_size=0.20, random_state=42, stratify=y_all
    )
    logger.info("Train=%d  Test=%d", len(X_train), len(X_test))

    # Pipeline: linguistic features + character TF-IDF → LogisticRegression
    pipeline = Pipeline([
        ("features", FeatureUnion([
            ("linguistic", LinguisticFeatureExtractor()),
            ("char_tfidf", TfidfVectorizer(
                analyzer="char_wb",
                ngram_range=(3, 5),
                max_features=300,
                min_df=5,
                sublinear_tf=True,
            )),
        ])),
        ("clf", LogisticRegression(
            C=0.1,
            class_weight="balanced",
            max_iter=1000,
            solver="lbfgs",
            random_state=42,
        )),
    ])

    # 5-fold cross-validation
    logger.info("Running 5-fold cross-validation ...")
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    cv_results = cross_validate(
        pipeline, X_all, y_all, cv=cv,
        scoring=["accuracy", "f1_macro"],
        n_jobs=-1,
    )
    logger.info("CV accuracy: %.4f ± %.4f", cv_results["test_accuracy"].mean(), cv_results["test_accuracy"].std())
    logger.info("CV f1_macro: %.4f ± %.4f", cv_results["test_f1_macro"].mean(), cv_results["test_f1_macro"].std())

    if cv_results["test_accuracy"].mean() > 0.98:
        logger.warning(
            "CV accuracy still >0.98 — model may still be over-relying on synthetic patterns. "
            "Check sanity check results below for natural-language generalisation."
        )

    # Fit on training split
    logger.info("Fitting on training split ...")
    pipeline.fit(X_train, y_train)

    # Evaluate on held-out test split
    y_pred = pipeline.predict(X_test)
    logger.info("Test accuracy: %.4f", accuracy_score(y_test, y_pred))
    logger.info("Test report:\n%s", classification_report(y_test, y_pred))

    # Save model
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump(pipeline, OUTPUT_PATH)
    logger.info("Model saved to %s", OUTPUT_PATH)

    # Sanity check on natural-language examples
    loaded = joblib.load(OUTPUT_PATH)
    samples = [
        ("The AC has been broken for three days", "complaint"),
        ("Can you tell me how to pay my rent?", "inquiry"),
        ("Water is leaking from the ceiling", "complaint"),
        ("What are the building's opening hours?", "inquiry"),
        ("The elevator is out of order again", "complaint"),
        ("How do I submit a maintenance request?", "inquiry"),
        ("There is a power outage on the 3rd floor", "complaint"),
        ("Is there parking available for visitors?", "inquiry"),
    ]
    logger.info("Sanity check on natural-language examples:")
    all_correct = True
    for text, expected in samples:
        pred = loaded.predict([text])[0]
        proba = loaded.predict_proba([text])[0]
        conf = max(proba)
        ok = pred == expected
        if not ok:
            all_correct = False
        logger.info("  [%s] pred=%-10s conf=%.3f  %r", "OK" if ok else "!!", pred, conf, text)

    if all_correct:
        logger.info("All sanity checks passed.")
    else:
        logger.warning("Some sanity checks failed — review before deploying.")

    logger.info("Deploy via:")
    logger.info(
        "  scp -i ~/.ssh/google_compute_engine %s "
        "aalmaharif_gmail_com@34.38.76.62:"
        "/opt/innova-cx/ai-models/MultiAgentPipeline/Orchestrator/agents/classifier/model/",
        OUTPUT_PATH,
    )


if __name__ == "__main__":
    main()
