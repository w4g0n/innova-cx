"""
Phase 4 — Validation and Final Dataset
=======================================
Validates the labeled dataset and produces the canonical final_dataset.csv.

Checks performed:
  1. Row count           >= 9,500 (FAIL) / >= 10,000 (PASS)
  2. Label value coverage  all 3 values present per label (low/medium/high)
  3. Class balance         no class < 8% within any label
  4. Safety rate           safety_concern=True between 15% and 40%
  5. Domain coverage       all 15 domains present (>= 0.5% each)

Outputs:
  output/phase4_report.json   — full stats + PASS/WARN/FAIL per check
  output/final_dataset.csv    — canonical deliverable for feature engineering

Usage:
    python phase4_validate.py
    python phase4_validate.py --input output/phase3_complete.csv
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

BASE_DIR      = Path(__file__).resolve().parent
OUTPUT_DIR    = BASE_DIR / "output"
DEFAULT_INPUT = OUTPUT_DIR / "phase3_complete.csv"
REPORT_PATH   = OUTPUT_DIR / "phase4_report.json"
FINAL_CSV     = OUTPUT_DIR / "final_dataset.csv"

LABEL_COLS        = ["issue_severity", "issue_urgency", "safety_concern", "business_impact"]
THREE_VALUE_COLS  = ["issue_severity", "issue_urgency", "business_impact"]
EXPECTED_VALUES   = {"low", "medium", "high"}

# Thresholds
MIN_ROWS            = 9_500
TARGET_ROWS         = 10_000
MIN_CLASS_PCT       = 8.0
SAFETY_TRUE_MIN_PCT = 15.0
SAFETY_TRUE_MAX_PCT = 40.0
MIN_DOMAIN_PCT      = 0.5


# ── Individual checks ──────────────────────────────────────────────────────────

def check_row_count(df: pd.DataFrame) -> dict:
    n      = len(df)
    status = "PASS" if n >= TARGET_ROWS else ("WARN" if n >= MIN_ROWS else "FAIL")
    return {
        "check":  "row_count",
        "value":  n,
        "status": status,
        "detail": f"{n:,} rows (target: {TARGET_ROWS:,}, minimum: {MIN_ROWS:,})",
    }


def check_label_values(df: pd.DataFrame) -> list[dict]:
    results = []
    for col in THREE_VALUE_COLS:
        present = set(df[col].dropna().astype(str).str.lower().unique())
        missing = EXPECTED_VALUES - present
        status  = "PASS" if not missing else "FAIL"
        results.append({
            "check":   f"{col}_coverage",
            "present": sorted(present),
            "missing": sorted(missing),
            "status":  status,
            "detail":  (
                f"All 3 values present" if not missing
                else f"Missing: {sorted(missing)}"
            ),
        })
    return results


def check_class_balance(df: pd.DataFrame) -> list[dict]:
    results = []
    for col in THREE_VALUE_COLS:
        counts  = df[col].dropna().value_counts(normalize=True) * 100
        if counts.empty:
            results.append({
                "check":  f"{col}_balance",
                "status": "FAIL",
                "detail": "No data",
            })
            continue
        min_pct = float(counts.min())
        status  = "PASS" if min_pct >= MIN_CLASS_PCT else "WARN"
        results.append({
            "check":            f"{col}_balance",
            "distribution_pct": {str(k): round(float(v), 1) for k, v in counts.items()},
            "min_class_pct":    round(min_pct, 1),
            "status":           status,
            "detail":           f"Min class share: {min_pct:.1f}% (threshold: {MIN_CLASS_PCT}%)",
        })
    return results


def check_safety_rate(df: pd.DataFrame) -> dict:
    safety   = df["safety_concern"].astype(str).str.lower()
    n_true   = (safety == "true").sum()
    n_total  = safety.notna().sum()
    pct      = n_true / n_total * 100 if n_total else 0.0
    status   = "PASS" if SAFETY_TRUE_MIN_PCT <= pct <= SAFETY_TRUE_MAX_PCT else "WARN"
    return {
        "check":       "safety_concern_rate",
        "true_count":  int(n_true),
        "total":       int(n_total),
        "true_pct":    round(pct, 1),
        "status":      status,
        "detail":      (
            f"{pct:.1f}% safety=True "
            f"(target: {SAFETY_TRUE_MIN_PCT}%–{SAFETY_TRUE_MAX_PCT}%)"
        ),
    }


def check_domain_distribution(df: pd.DataFrame) -> dict:
    if "domain" not in df.columns:
        return {
            "check":  "domain_distribution",
            "status": "SKIP",
            "detail": "No 'domain' column",
        }
    counts   = df["domain"].value_counts(normalize=True) * 100
    low_doms = counts[counts < MIN_DOMAIN_PCT].index.tolist()
    status   = "PASS" if not low_doms else "WARN"
    return {
        "check":                 "domain_distribution",
        "n_domains":             int(counts.shape[0]),
        "domain_pct":            {str(k): round(float(v), 1) for k, v in counts.items()},
        "low_coverage_domains":  low_doms,
        "status":                status,
        "detail":                (
            f"{counts.shape[0]} domains present"
            + (f" — low coverage: {low_doms}" if low_doms else "")
        ),
    }


def check_null_label_rate(df: pd.DataFrame) -> dict:
    all_null_mask = df[LABEL_COLS].isnull().all(axis=1)
    n_null        = int(all_null_mask.sum())
    pct           = n_null / len(df) * 100 if len(df) else 0
    status        = "PASS" if pct < 5 else ("WARN" if pct < 15 else "FAIL")
    return {
        "check":   "null_label_rate",
        "n_null":  n_null,
        "pct":     round(pct, 1),
        "status":  status,
        "detail":  f"{n_null} rows with all-null labels ({pct:.1f}%)",
    }


# ── Main ───────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="V8 Phase 4: Validation")
    parser.add_argument("--input", default=str(DEFAULT_INPUT))
    args = parser.parse_args()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print(f"Loading: {args.input}")
    df = pd.read_csv(args.input)
    print(f"Loaded {len(df)} rows")

    # ── Run checks ────────────────────────────────────────────────────────────
    checks: list[dict] = []
    checks.append(check_row_count(df))
    checks.append(check_null_label_rate(df))
    checks.extend(check_label_values(df))
    checks.extend(check_class_balance(df))
    checks.append(check_safety_rate(df))
    checks.append(check_domain_distribution(df))

    # ── Summary ───────────────────────────────────────────────────────────────
    statuses = [c["status"] for c in checks]
    n_fail   = statuses.count("FAIL")
    n_warn   = statuses.count("WARN")
    n_pass   = statuses.count("PASS")
    overall  = "FAIL" if n_fail else ("WARN" if n_warn else "PASS")

    ICONS = {"PASS": "✅", "WARN": "⚠ ", "FAIL": "❌", "SKIP": "⏭ "}

    print(f"\n{'='*55}")
    print(f"VALIDATION REPORT — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"{'='*55}")
    for c in checks:
        icon   = ICONS.get(c["status"], " ")
        detail = c.get("detail") or c.get("check")
        print(f"  {icon} [{c['status']}] {detail}")
    print(f"\n  Overall : {overall}  ({n_pass} pass, {n_warn} warn, {n_fail} fail)")
    print(f"  Rows    : {len(df):,}")

    # ── Save report ───────────────────────────────────────────────────────────
    report = {
        "timestamp":      datetime.now().isoformat(),
        "final_row_count": len(df),
        "overall_status": overall,
        "summary":        {"pass": n_pass, "warn": n_warn, "fail": n_fail},
        "checks":         checks,
    }
    with open(REPORT_PATH, "w") as f:
        json.dump(report, f, indent=2)

    # ── Save final dataset ────────────────────────────────────────────────────
    df.to_csv(FINAL_CSV, index=False)
    print(f"\n  Saved : {FINAL_CSV}")
    print(f"  Report: {REPORT_PATH}")

    if n_fail:
        print(
            f"\n❌ {n_fail} check(s) FAILED. "
            f"Review phase4_report.json and re-run earlier phases as needed."
        )
        sys.exit(1)
    elif n_warn:
        print(
            f"\n⚠  {n_warn} warning(s). Dataset is usable but class balance "
            f"is suboptimal — consider re-running phase 1 with more safety hints "
            f"or a higher complaint target."
        )
    else:
        print(
            f"\n✅ All checks passed. "
            f"output/final_dataset.csv is ready for feature engineering training."
        )


if __name__ == "__main__":
    main()
