"""
One-time prioritization bootstrap training
=========================================

- Generates synthetic labels by running all combinations through fuzzy logic.
- Trains XGBoost on the generated dataset.
- Exports model + metadata + base training dataset.

Output artifacts are meant to be copied to runtime PRIORITY_MODEL_DIR.
"""

from __future__ import annotations

import argparse
import csv
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from itertools import product
from pathlib import Path

import numpy as np
import skfuzzy as fuzz
from skfuzzy import control as ctrl
from xgboost import XGBClassifier
from sklearn.metrics import accuracy_score


SENTIMENT_LEVELS = ["negative", "neutral", "positive"]
SEVERITY_LEVELS = ["low", "medium", "high"]
URGENCY_LEVELS = ["low", "medium", "high"]
IMPACT_LEVELS = ["low", "medium", "high"]
BOOL_VALUES = [False, True]
TICKET_TYPES = ["complaint", "inquiry"]
PRIORITY_LEVELS = ["low", "medium", "high", "critical"]

SENTIMENT_NUM = {"negative": -0.7, "neutral": 0.0, "positive": 0.7}
SENTIMENT_MAP = {"negative": 0, "neutral": 1, "positive": 2}
SEVERITY_MAP = {"low": 0, "medium": 1, "high": 2}
URGENCY_MAP = {"low": 0, "medium": 1, "high": 2}
IMPACT_MAP = {"low": 0, "medium": 1, "high": 2}
TICKET_TYPE_MAP = {"complaint": 0, "inquiry": 1}
PRIORITY_MAP = {"low": 0, "medium": 1, "high": 2, "critical": 3}


@dataclass
class TrainingArtifacts:
    output_dir: Path
    synthetic_csv: Path
    model_file: Path
    metadata_file: Path
    test_report_file: Path


def build_fuzzy_system() -> ctrl.ControlSystem:
    sentiment_universe = np.arange(-1, 1.05, 0.05)
    severity_universe = np.arange(0, 3, 1)
    urgency_universe = np.arange(0, 3, 1)
    impact_universe = np.arange(0, 3, 1)
    priority_universe = np.arange(0, 4, 1)

    sentiment = ctrl.Antecedent(sentiment_universe, "sentiment")
    issue_severity = ctrl.Antecedent(severity_universe, "issue_severity")
    issue_urgency = ctrl.Antecedent(urgency_universe, "issue_urgency")
    business_impact = ctrl.Antecedent(impact_universe, "business_impact")
    priority = ctrl.Consequent(priority_universe, "priority", defuzzify_method="centroid")

    sentiment["negative"] = fuzz.trapmf(sentiment_universe, [-1, -1, -0.25, 0.0])
    sentiment["neutral"] = fuzz.trimf(sentiment_universe, [-0.25, 0.0, 0.25])
    sentiment["positive"] = fuzz.trapmf(sentiment_universe, [0.0, 0.25, 1.0, 1.0])

    issue_severity["low"] = fuzz.trimf(severity_universe, [0, 0, 1])
    issue_severity["medium"] = fuzz.trimf(severity_universe, [0, 1, 2])
    issue_severity["high"] = fuzz.trimf(severity_universe, [1, 2, 2])

    issue_urgency["low"] = fuzz.trimf(urgency_universe, [0, 0, 1])
    issue_urgency["medium"] = fuzz.trimf(urgency_universe, [0, 1, 2])
    issue_urgency["high"] = fuzz.trimf(urgency_universe, [1, 2, 2])

    business_impact["low"] = fuzz.trimf(impact_universe, [0, 0, 1])
    business_impact["medium"] = fuzz.trimf(impact_universe, [0, 1, 2])
    business_impact["high"] = fuzz.trimf(impact_universe, [1, 2, 2])

    priority["low"] = fuzz.trimf(priority_universe, [0, 0, 1])
    priority["medium"] = fuzz.trimf(priority_universe, [0, 1, 2])
    priority["high"] = fuzz.trimf(priority_universe, [1, 2, 3])
    priority["critical"] = fuzz.trimf(priority_universe, [2, 3, 3])

    rules = [
        ctrl.Rule(issue_severity["high"] & issue_urgency["high"], priority["high"]),
        ctrl.Rule(issue_severity["high"] & issue_urgency["medium"], priority["high"]),
        ctrl.Rule(issue_severity["medium"] & issue_urgency["high"], priority["high"]),
        ctrl.Rule(issue_severity["high"] & issue_urgency["low"], priority["medium"]),
        ctrl.Rule(issue_severity["low"] & issue_urgency["high"], priority["medium"]),
        ctrl.Rule(issue_severity["medium"] & issue_urgency["medium"], priority["medium"]),
        ctrl.Rule(issue_severity["medium"] & issue_urgency["low"], priority["medium"]),
        ctrl.Rule(issue_severity["low"] & issue_urgency["medium"], priority["medium"]),
        ctrl.Rule(issue_severity["low"] & issue_urgency["low"], priority["low"]),

        ctrl.Rule(business_impact["high"] & issue_severity["high"] & issue_urgency["high"], priority["critical"]),
        ctrl.Rule(business_impact["high"] & issue_severity["medium"] & issue_urgency["high"], priority["high"]),

        ctrl.Rule(sentiment["negative"], priority["high"]),
        ctrl.Rule(sentiment["positive"], priority["low"]),
    ]

    return ctrl.ControlSystem(rules)


def clamp_priority(index: int) -> str:
    max_idx = len(PRIORITY_LEVELS) - 1
    return PRIORITY_LEVELS[max(0, min(max_idx, int(index)))]


def fuzzy_label(
    fuzzy_ctrl: ctrl.ControlSystem,
    *,
    sentiment_score: str,
    issue_severity_val: str,
    issue_urgency_val: str,
    business_impact_val: str,
    safety_concern: bool,
    is_recurring: bool,
    ticket_type: str,
) -> str:
    sim = ctrl.ControlSystemSimulation(fuzzy_ctrl)
    sim.input["sentiment"] = SENTIMENT_NUM[sentiment_score]
    sim.input["issue_severity"] = SEVERITY_MAP[issue_severity_val]
    sim.input["issue_urgency"] = URGENCY_MAP[issue_urgency_val]
    sim.input["business_impact"] = IMPACT_MAP[business_impact_val]
    sim.compute()

    base = int(round(float(sim.output["priority"])))

    modifier = 0
    if is_recurring:
        modifier += 1
    if ticket_type == "inquiry":
        modifier -= 1
    if sentiment_score == "negative":
        modifier += 1
    elif sentiment_score == "positive":
        modifier -= 1

    final = base + modifier
    final_label = clamp_priority(final)

    if safety_concern and PRIORITY_MAP[final_label] < PRIORITY_MAP["high"]:
        final_label = "high"

    return final_label


def build_dataset() -> list[dict[str, object]]:
    fuzzy_ctrl = build_fuzzy_system()
    rows: list[dict[str, object]] = []

    for (
        ticket_type,
        is_recurring,
        business_impact,
        safety_concern,
        sentiment_score,
        issue_severity,
        issue_urgency,
    ) in product(
        TICKET_TYPES,
        BOOL_VALUES,
        IMPACT_LEVELS,
        BOOL_VALUES,
        SENTIMENT_LEVELS,
        SEVERITY_LEVELS,
        URGENCY_LEVELS,
    ):
        label = fuzzy_label(
            fuzzy_ctrl,
            sentiment_score=sentiment_score,
            issue_severity_val=issue_severity,
            issue_urgency_val=issue_urgency,
            business_impact_val=business_impact,
            safety_concern=safety_concern,
            is_recurring=is_recurring,
            ticket_type=ticket_type,
        )

        rows.append(
            {
                "ticket_type": ticket_type,
                "is_recurring": bool(is_recurring),
                "business_impact_val": business_impact,
                "safety_concern": bool(safety_concern),
                "sentiment_score": sentiment_score,
                "issue_severity_val": issue_severity,
                "issue_urgency_val": issue_urgency,
                "label_priority": label,
                "label_source": "fuzzy_synthetic",
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
        )
    return rows


def encode_rows(rows: list[dict[str, object]]) -> tuple[np.ndarray, np.ndarray]:
    X = []
    y = []
    for row in rows:
        X.append(
            [
                float(SENTIMENT_MAP[str(row["sentiment_score"])]),
                float(SEVERITY_MAP[str(row["issue_severity_val"])]),
                float(URGENCY_MAP[str(row["issue_urgency_val"])]),
                float(IMPACT_MAP[str(row["business_impact_val"])]),
                1.0 if bool(row["safety_concern"]) else 0.0,
                1.0 if bool(row["is_recurring"]) else 0.0,
                float(TICKET_TYPE_MAP[str(row["ticket_type"])]),
            ]
        )
        y.append(PRIORITY_MAP[str(row["label_priority"])])

    return np.asarray(X, dtype=np.float32), np.asarray(y, dtype=np.int32)


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def evaluate_on_training_dataset(
    model: XGBClassifier,
    X: np.ndarray,
    y: np.ndarray,
) -> dict[str, object]:
    pred = model.predict(X)
    acc = float(accuracy_score(y, pred))
    correct = int((pred == y).sum())
    total = int(len(y))
    return {
        "accuracy": round(acc, 6),
        "correct": correct,
        "total": total,
    }


def run_training(output_dir: Path, epochs: int) -> TrainingArtifacts:
    output_dir.mkdir(parents=True, exist_ok=True)
    artifacts = TrainingArtifacts(
        output_dir=output_dir,
        synthetic_csv=output_dir / "synthetic_training_data.csv",
        model_file=output_dir / "priority_xgb_model.json",
        metadata_file=output_dir / "priority_xgb_metadata.json",
        test_report_file=output_dir / "train_set_eval.json",
    )

    rows = build_dataset()
    X, y = encode_rows(rows)

    model = XGBClassifier(
        objective="multi:softprob",
        num_class=4,
        n_estimators=max(50, int(epochs)),
        max_depth=10,
        learning_rate=0.2,
        subsample=1.0,
        colsample_bytree=1.0,
        reg_lambda=0.0,
        reg_alpha=0.0,
        min_child_weight=1,
        gamma=0.0,
        random_state=42,
        eval_metric="mlogloss",
        n_jobs=1,
    )
    model.fit(X, y)
    eval_report = evaluate_on_training_dataset(model, X, y)

    write_csv(artifacts.synthetic_csv, rows)
    model.save_model(str(artifacts.model_file))

    metadata = {
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "synthetic_rows": len(rows),
        "combinations_formula": "2*2*3*2*3*3*3",
        "expected_rows": 648,
        "epochs": int(epochs),
        "train_set_evaluation": eval_report,
        "feature_order": [
            "sentiment_score",
            "issue_severity",
            "issue_urgency",
            "business_impact",
            "safety_concern",
            "is_recurring",
            "ticket_type",
        ],
        "artifacts": {
            "model_file": str(artifacts.model_file),
            "synthetic_csv": str(artifacts.synthetic_csv),
        },
    }
    artifacts.metadata_file.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    artifacts.test_report_file.write_text(json.dumps(eval_report, indent=2), encoding="utf-8")

    print(json.dumps(metadata, indent=2))
    return artifacts


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output-dir",
        default="ai-models/MultiAgentPipeline/PrioritzationAgentTraining/output",
        help="Directory for trained model state and synthetic dataset",
    )
    parser.add_argument(
        "--epochs",
        type=int,
        default=600,
        help="Boosting rounds (high value helps memorization on synthetic data)",
    )
    args = parser.parse_args()

    run_training(Path(args.output_dir).resolve(), epochs=args.epochs)


if __name__ == "__main__":
    main()
