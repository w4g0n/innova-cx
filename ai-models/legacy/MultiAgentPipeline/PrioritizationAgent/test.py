import argparse
import json
from pathlib import Path

from src.inference import add_manager_feedback_example, prioritize


def run_smoke() -> None:
    result = prioritize(
        sentiment_score="negative",
        issue_severity_val="high",
        issue_urgency_val="high",
        business_impact_val="high",
        safety_concern=True,
        is_recurring=True,
        ticket_type="complaint",
    )
    print("prediction:")
    print(json.dumps(result, indent=2))


def run_feedback() -> None:
    result = add_manager_feedback_example(
        sentiment_score="negative",
        issue_severity_val="high",
        issue_urgency_val="high",
        business_impact_val="high",
        safety_concern=True,
        is_recurring=True,
        ticket_type="complaint",
        approved_priority="critical",
        ticket_id="TEST-TICKET",
        retrain_now=True,
    )
    print("feedback:")
    print(json.dumps(result, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description="Prioritization runtime test")
    parser.add_argument("--mode", choices=["smoke", "feedback"], default="smoke")
    args = parser.parse_args()

    if args.mode == "smoke":
        run_smoke()
    else:
        run_feedback()


if __name__ == "__main__":
    main()
