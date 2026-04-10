#!/usr/bin/env python3
"""
Clean Synthesizer v7 CSV outputs where subject/text may contain JSON wrappers
or malformed generated content.

Usage:
  python3 clean_csv.py --input output/unlabeled.csv --output output/unlabeled_cleaned.csv
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import pandas as pd


def _unescape_json_string(value: str) -> str:
    return json.loads(f"\"{value}\"")


def _extract_subject_text(blob: str) -> tuple[str | None, str | None]:
    cleaned = str(blob).strip().replace("```json", "").replace("```", "").strip()

    obj_match = re.search(r"\{.*\}", cleaned, re.DOTALL)
    if obj_match:
        try:
            parsed = json.loads(obj_match.group(0))
            if "subject" in parsed and "text" in parsed:
                return str(parsed["subject"]).strip(), str(parsed["text"]).strip()
        except json.JSONDecodeError:
            pass

    subject_match = re.search(r'"subject"\s*:\s*"((?:[^"\\]|\\.)*)"', cleaned, re.DOTALL)
    text_match = re.search(r'"text"\s*:\s*"((?:[^"\\]|\\.)*)"', cleaned, re.DOTALL)
    if subject_match and text_match:
        try:
            subject = _unescape_json_string(subject_match.group(1)).strip()
            text = _unescape_json_string(text_match.group(1)).strip()
            return subject, text
        except json.JSONDecodeError:
            pass

    return None, None


def _normalize_whitespace(value: str) -> str:
    return " ".join(str(value).split()).strip()


def clean_frame(df: pd.DataFrame, min_text_len: int = 20) -> tuple[pd.DataFrame, dict[str, int]]:
    required = {"subject", "text"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Missing required columns: {sorted(missing)}")

    fixed_rows = 0
    dropped_rows = 0

    out_rows = []
    for _, row in df.iterrows():
        subject = _normalize_whitespace(row["subject"])
        text = _normalize_whitespace(row["text"])

        maybe_json = (
            subject.lower().startswith("json ")
            or text.lower().startswith("json ")
            or ('"subject"' in subject and '"text"' in subject)
            or ('"subject"' in text and '"text"' in text)
        )

        if maybe_json:
            source_blob = text if ('"subject"' in text and '"text"' in text) else subject
            recovered_subject, recovered_text = _extract_subject_text(source_blob)
            if recovered_subject and recovered_text:
                subject = _normalize_whitespace(recovered_subject)
                text = _normalize_whitespace(recovered_text)
                fixed_rows += 1
            else:
                dropped_rows += 1
                continue

        if len(text) < min_text_len:
            dropped_rows += 1
            continue

        clean_row = dict(row)
        clean_row["subject"] = subject
        clean_row["text"] = text
        out_rows.append(clean_row)

    out_df = pd.DataFrame(out_rows)
    return out_df, {
        "input_rows": len(df),
        "output_rows": len(out_df),
        "fixed_rows": fixed_rows,
        "dropped_rows": dropped_rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Clean malformed subject/text rows in a Synthesizer CSV")
    parser.add_argument("--input", required=True, help="Path to input CSV")
    parser.add_argument("--output", required=True, help="Path to output cleaned CSV")
    parser.add_argument("--min-text-len", type=int, default=20, help="Minimum text length to keep")
    args = parser.parse_args()

    input_path = Path(args.input)
    output_path = Path(args.output)
    if not input_path.exists():
        raise FileNotFoundError(f"Input CSV not found: {input_path}")

    df = pd.read_csv(input_path)
    cleaned_df, stats = clean_frame(df, min_text_len=args.min_text_len)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    cleaned_df.to_csv(output_path, index=False)

    print(f"Saved cleaned CSV to: {output_path}")
    print(
        f"rows: {stats['input_rows']} -> {stats['output_rows']} | "
        f"fixed={stats['fixed_rows']} dropped={stats['dropped_rows']}"
    )


if __name__ == "__main__":
    main()
