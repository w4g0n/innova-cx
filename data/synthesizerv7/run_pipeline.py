#!/usr/bin/env python3
"""
Run Synthesizer v7 end-to-end in fixed order:
    Phase 1 -> Phase 4 -> Phase 2 -> Phase 3
"""

from __future__ import annotations

import argparse
import importlib
import json
import subprocess
import sys
from pathlib import Path

import pandas as pd

MIN_TRANSFORMERS = (4, 55, 0)
MIN_ACCELERATE = (0, 34, 0)
MIN_TOKENIZERS = (0, 21, 0)


def run_stage(name: str, cmd: list[str]) -> None:
    print(f"\n{'=' * 70}")
    print(f"Running {name}")
    print(f"{'=' * 70}")
    print(" ".join(cmd))
    completed = subprocess.run(cmd, check=False)
    if completed.returncode != 0:
        raise RuntimeError(f"{name} failed with exit code {completed.returncode}")


def safe_count_rows(csv_path: Path) -> int | None:
    if not csv_path.exists():
        return None


def validate_runtime_dependencies() -> None:
    def _parse_version(value: str) -> tuple[int, ...]:
        parts = []
        for token in value.replace("+", ".").split("."):
            if token.isdigit():
                parts.append(int(token))
            else:
                break
        return tuple(parts)

    def _check_min_version(pkg: str, minimum: tuple[int, ...]) -> None:
        module = importlib.import_module(pkg)
        got_raw = getattr(module, "__version__", "0")
        got = _parse_version(got_raw)
        if got < minimum:
            required = ".".join(str(v) for v in minimum)
            raise RuntimeError(
                f"{pkg}=={got_raw} is too old. Required >= {required}. "
                "Run: pip install -U \"transformers>=4.55.0\" "
                "\"accelerate>=0.34.0\" \"tokenizers>=0.21.0\""
            )

    _check_min_version("transformers", MIN_TRANSFORMERS)
    _check_min_version("accelerate", MIN_ACCELERATE)
    _check_min_version("tokenizers", MIN_TOKENIZERS)
    try:
        return int(len(pd.read_csv(csv_path)))
    except Exception:
        return None


def main() -> None:
    validate_runtime_dependencies()
    parser = argparse.ArgumentParser(description="Run Synthesizer v7 full pipeline")
    parser.add_argument("--dataset", default="input.csv", help="Phase 1 reference dataset (must include transcript)")
    parser.add_argument("--test", default="test.csv", help="Phase 3 test/prediction input (issue_text or text)")
    parser.add_argument("--output-dir", default="output", help="Output directory")
    parser.add_argument("--model", default=None, help="Optional Phase 1 model override")
    parser.add_argument(
        "--quantization",
        choices=["auto", "none", "8bit"],
        default="auto",
        help="Quantization mode for phases 1/2/3",
    )
    parser.add_argument("--complaints", type=int, default=7500, help="Phase 1 complaint count")
    parser.add_argument("--inquiries", type=int, default=2500, help="Phase 1 inquiry count")
    parser.add_argument("--max-new-tokens", type=int, default=64, help="Phase 1 max new tokens")
    parser.add_argument("--retries", type=int, default=2, help="Phase 1 retries")
    parser.add_argument("--temperature", type=float, default=0.3, help="Phase 1 temperature")
    parser.add_argument("--top-p", type=float, default=0.8, help="Phase 1 top-p")
    parser.add_argument("--similarity-threshold", type=float, default=0.92, help="Phase 4 near dedup threshold")
    parser.add_argument("--summary-output", default="output/pipeline_summary.json", help="Run summary JSON path")
    args = parser.parse_args()

    base_dir = Path(__file__).resolve().parent
    output_dir = (base_dir / args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    phase1_out = output_dir / "unlabeled.csv"
    phase4_out = output_dir / "unlabeled_deduplicated.csv"
    phase4_stats = output_dir / "deduplication_stats.json"
    phase2_out = output_dir / "labeled.csv"
    phase2_manifest = output_dir / "phase2_model_manifest.json"
    phase3_out = output_dir / "predictions.csv"
    summary_out = (base_dir / args.summary_output).resolve()

    phase1_cmd = [
        sys.executable,
        str(base_dir / "phase1-generate.py"),
        "--dataset",
        str((base_dir / args.dataset).resolve()),
        "--output",
        str(phase1_out),
        "--quantization",
        args.quantization,
        "--complaints",
        str(args.complaints),
        "--inquiries",
        str(args.inquiries),
        "--max-new-tokens",
        str(args.max_new_tokens),
        "--retries",
        str(args.retries),
        "--temperature",
        str(args.temperature),
        "--top-p",
        str(args.top_p),
    ]
    if args.model:
        phase1_cmd.extend(["--model", args.model])

    phase4_cmd = [
        sys.executable,
        str(base_dir / "phase4-deduplicate.py"),
        "--input",
        str(phase1_out),
        "--output",
        str(phase4_out),
        "--stats-output",
        str(phase4_stats),
        "--similarity-threshold",
        str(args.similarity_threshold),
    ]

    phase2_cmd = [
        sys.executable,
        str(base_dir / "phase2-classify.py"),
        "--input",
        str(phase4_out),
        "--output",
        str(phase2_out),
        "--manifest-output",
        str(phase2_manifest),
        "--quantization",
        args.quantization,
    ]

    phase3_cmd = [
        sys.executable,
        str(base_dir / "phase3-evaluate.py"),
        "--test",
        str((base_dir / args.test).resolve()),
        "--output",
        str(phase3_out),
        "--quantization",
        args.quantization,
    ]

    run_stage("Phase 1 (generate)", phase1_cmd)
    run_stage("Phase 4 (deduplicate)", phase4_cmd)
    run_stage("Phase 2 (classify)", phase2_cmd)
    run_stage("Phase 3 (predict)", phase3_cmd)

    summary = {
        "pipeline_order": ["phase1-generate", "phase4-deduplicate", "phase2-classify", "phase3-evaluate"],
        "artifacts": {
            "phase1_output": str(phase1_out),
            "phase4_output": str(phase4_out),
            "phase4_stats": str(phase4_stats),
            "phase2_output": str(phase2_out),
            "phase2_manifest": str(phase2_manifest),
            "phase3_output": str(phase3_out),
        },
        "row_counts": {
            "phase1_output_rows": safe_count_rows(phase1_out),
            "phase4_output_rows": safe_count_rows(phase4_out),
            "phase2_output_rows": safe_count_rows(phase2_out),
            "phase3_output_rows": safe_count_rows(phase3_out),
        },
    }
    summary_out.parent.mkdir(parents=True, exist_ok=True)
    summary_out.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print(f"\nPipeline complete. Summary saved to: {summary_out}")


if __name__ == "__main__":
    main()
