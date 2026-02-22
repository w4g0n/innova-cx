import argparse
import csv
from collections import Counter
from datetime import datetime
from itertools import product
from pathlib import Path

from src.inference import prioritize


SEVERITY_LEVELS = ["low", "medium", "high", "critical"]
URGENCY_LEVELS = ["low", "medium", "high", "critical"]
IMPACT_LEVELS = ["low", "medium", "high"]
TICKET_TYPES = ["complaint", "inquiry"]
BOOL_VALUES = [False, True]


def _parse_bool(value: str) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "y"}


def _sentiment_values(mode: str) -> list[float]:
    # Exactly one representative value per sentiment class:
    # negative, neutral, positive
    return [-0.5, 0.0, 0.5]


def _sentiment_bucket(value: float) -> str:
    if value < -0.25:
        return "negative"
    if value > 0.25:
        return "positive"
    return "neutral"


def _timestamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _resolve_output_path(path_arg: str, default_name: str) -> Path:
    """
    If `path_arg` points to a directory (or has no suffix), write a new labeled file
    inside it. If it points to a .csv file, use it as-is.
    """
    p = Path(path_arg)
    if p.suffix.lower() == ".csv":
        p.parent.mkdir(parents=True, exist_ok=True)
        return p
    p.mkdir(parents=True, exist_ok=True)
    return p / f"{default_name}_{_timestamp()}.csv"


def run_exhaustive(sentiment_mode: str, output_csv: Path) -> None:
    sentiments = _sentiment_values(sentiment_mode)
    rows = []
    counts = Counter()

    for (
        sentiment_score,
        issue_severity_val,
        issue_urgency_val,
        business_impact_val,
        safety_concern,
        is_recurring,
        ticket_type,
    ) in product(
        sentiments,
        SEVERITY_LEVELS,
        URGENCY_LEVELS,
        IMPACT_LEVELS,
        BOOL_VALUES,
        BOOL_VALUES,
        TICKET_TYPES,
    ):
        sentiment_bucket = _sentiment_bucket(sentiment_score)
        result = prioritize(
            sentiment_score=sentiment_score,
            issue_severity_val=issue_severity_val,
            issue_urgency_val=issue_urgency_val,
            business_impact_val=business_impact_val,
            safety_concern=safety_concern,
            is_recurring=is_recurring,
            ticket_type=ticket_type,
        )
        counts[result["final_priority"]] += 1
        rows.append(
            {
                "sentiment_score": sentiment_score,
                "sentiment_bucket": sentiment_bucket,
                "issue_severity_val": issue_severity_val,
                "issue_urgency_val": issue_urgency_val,
                "business_impact_val": business_impact_val,
                "safety_concern": safety_concern,
                "is_recurring": is_recurring,
                "ticket_type": ticket_type,
                "raw_score": result["raw_score"],
                "base_priority": result["base_priority"],
                "final_priority": result["final_priority"],
                "modifiers_applied": "; ".join(result["modifiers_applied"]),
            }
        )

    output_csv.parent.mkdir(parents=True, exist_ok=True)
    with output_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    print(f"Exhaustive test complete: {len(rows)} combinations")
    print(f"Saved results: {output_csv}")
    print("Final priority distribution:")
    for level in ["low", "medium", "high", "critical"]:
        print(f"  {level}: {counts[level]}")


def run_csv_validation(input_csv: Path, mismatch_csv: Path | None) -> None:
    if not input_csv.exists():
        raise FileNotFoundError(f"CSV not found: {input_csv}")

    required = {
        "sentiment_score",
        "issue_severity_val",
        "issue_urgency_val",
        "business_impact_val",
        "safety_concern",
        "is_recurring",
        "ticket_type",
    }

    with input_csv.open("r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        cols = set(reader.fieldnames or [])
        missing = required - cols
        if missing:
            raise ValueError(f"Missing required columns in CSV: {sorted(missing)}")

        has_expected = "expected_final_priority" in cols
        total = 0
        mismatches = 0

        for row in reader:
            total += 1
            result = prioritize(
                sentiment_score=float(row["sentiment_score"]),
                issue_severity_val=row["issue_severity_val"],
                issue_urgency_val=row["issue_urgency_val"],
                business_impact_val=row["business_impact_val"],
                safety_concern=_parse_bool(row["safety_concern"]),
                is_recurring=_parse_bool(row["is_recurring"]),
                ticket_type=row["ticket_type"],
            )

            actual = result["final_priority"]
            expected = row.get("expected_final_priority", "").strip().lower()

            if has_expected and expected and actual != expected:
                mismatches += 1

    if has_expected:
        passed = total - mismatches
        print(f"CSV validation complete: {passed}/{total} matched expected_final_priority")
        print(f"Mismatches: {mismatches}")
    else:
        print(f"CSV run complete: {total} rows processed (no expected_final_priority column found)")


def main() -> None:
    parser = argparse.ArgumentParser(description="PrioritizationAgent test runner")
    parser.add_argument(
        "--mode",
        choices=["exhaustive", "csv"],
        default="exhaustive",
        help="Run exhaustive combinations or CSV validation.",
    )
    parser.add_argument(
        "--sentiment-mode",
        choices=["categories"],
        default="categories",
        help="Sentiment permutations for exhaustive mode.",
    )
    parser.add_argument(
        "--output-csv",
        default="test_outputs",
        help="Output CSV file or directory for exhaustive results. Directory creates a timestamped labeled file.",
    )
    parser.add_argument(
        "--input-csv",
        default="",
        help="Input CSV path for csv mode.",
    )
    args = parser.parse_args()

    if args.mode == "exhaustive":
        exhaustive_path = _resolve_output_path(
            args.output_csv,
            default_name=f"exhaustive_{args.sentiment_mode}",
        )
        run_exhaustive(args.sentiment_mode, exhaustive_path)

    if args.mode == "csv":
        if not args.input_csv:
            raise ValueError("--input-csv is required for mode=csv")
        run_csv_validation(Path(args.input_csv), None)


if __name__ == "__main__":
    main()
