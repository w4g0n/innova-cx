"""
run_pipeline.py — V8 Synthesizer Orchestrator
==============================================
Runs all 4 phases in sequence:

  Phase 1  Generate     Phi-4-mini complaint generation (10,000 rows)
  Phase 2  Deduplicate  TF-IDF near-duplicate removal
  Phase 3  Label        Phi-4-mini few-shot labeling (4 labels)
  Phase 4  Validate     Class balance check + final_dataset.csv

Usage:
    python run_pipeline.py                      # Full run from scratch
    python run_pipeline.py --resume             # Resume any incomplete phase
    python run_pipeline.py --dry-run            # Quick test: 50 complaints, 10 labeled
    python run_pipeline.py --start-phase 3      # Start from phase 3
    python run_pipeline.py --skip-phase 2       # Skip phase 2 (use existing output)
    python run_pipeline.py --complaints 11000   # Override complaint count

Each phase is detected as complete by the presence of its output file.
If a phase fails, fix the error and re-run with --resume to continue.
"""

import argparse
import subprocess
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

BASE_DIR   = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "output"

# A phase is considered "done" when its marker file exists.
PHASE_MARKERS: dict[int, Path] = {
    1: OUTPUT_DIR / "phase1_complete.csv",
    2: OUTPUT_DIR / "phase2_deduplicated.csv",
    3: OUTPUT_DIR / "phase3_complete.csv",
    4: OUTPUT_DIR / "final_dataset.csv",
}

PHASE_SCRIPTS: dict[int, Path] = {
    1: BASE_DIR / "phase1_generate.py",
    2: BASE_DIR / "phase2_deduplicate.py",
    3: BASE_DIR / "phase3_label.py",
    4: BASE_DIR / "phase4_validate.py",
}

PHASE_NAMES: dict[int, str] = {
    1: "Generate",
    2: "Deduplicate",
    3: "Label",
    4: "Validate",
}

# Rough time estimates per phase (T4 GPU, 10,000 complaints)
PHASE_TIME_ESTIMATES: dict[int, str] = {
    1: "~3.5 hrs",
    2: "~2 mins",
    3: "~4.5 hrs",
    4: "~30 secs",
}


def fmt_elapsed(seconds: float) -> str:
    return str(timedelta(seconds=int(seconds)))


def run_phase(phase: int, extra_args: list[str]) -> bool:
    script = PHASE_SCRIPTS[phase]
    name   = PHASE_NAMES[phase]
    cmd    = [sys.executable, str(script)] + extra_args

    print(f"\n{'='*60}")
    print(f"  Phase {phase}: {name}")
    print(f"  Script    : {script.name}")
    print(f"  Args      : {' '.join(extra_args) if extra_args else '(none)'}")
    print(f"  Estimate  : {PHASE_TIME_ESTIMATES[phase]}")
    print(f"  Start     : {datetime.now().strftime('%H:%M:%S')}")
    print(f"{'='*60}\n")

    start  = time.perf_counter()
    result = subprocess.run(cmd, cwd=str(BASE_DIR))
    elapsed = time.perf_counter() - start

    if result.returncode != 0:
        print(f"\n❌  Phase {phase} ({name}) exited with code {result.returncode}")
        print(f"    Elapsed : {fmt_elapsed(elapsed)}")
        return False

    print(f"\n✅  Phase {phase} ({name}) complete — {fmt_elapsed(elapsed)}")
    return True


def print_status() -> None:
    print("\nCurrent phase status:")
    for phase, marker in PHASE_MARKERS.items():
        exists = marker.exists()
        icon   = "✅" if exists else "⏳"
        print(f"  {icon}  Phase {phase} ({PHASE_NAMES[phase]}): "
              f"{'done' if exists else 'pending'}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="V8 Synthesizer Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python run_pipeline.py                    Full run from scratch
  python run_pipeline.py --resume           Resume any incomplete phase
  python run_pipeline.py --dry-run          Quick test (50 generated, 10 labeled)
  python run_pipeline.py --start-phase 3   Start from Phase 3
  python run_pipeline.py --skip-phase 2    Skip dedup (use existing phase1 output)
        """,
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Skip phases whose output file already exists",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Quick sanity check: 50 complaints generated, 10 labeled",
    )
    parser.add_argument(
        "--start-phase",
        type=int,
        choices=[1, 2, 3, 4],
        default=1,
        metavar="N",
        help="Start from phase N (1–4). Previous phases must have their outputs.",
    )
    parser.add_argument(
        "--skip-phase",
        type=int,
        choices=[1, 2, 3, 4],
        default=None,
        metavar="N",
        help="Skip phase N entirely (use its existing output file).",
    )
    parser.add_argument(
        "--complaints",
        type=int,
        default=None,
        metavar="N",
        help="Override complaint count for Phase 1 (default: 10,000).",
    )
    args = parser.parse_args()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print(f"\n{'='*60}")
    print(f"  V8 SYNTHESIZER PIPELINE")
    print(f"  Start   : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  Resume  : {args.resume}")
    print(f"  Dry-run : {args.dry_run}")
    print(f"  From    : Phase {args.start_phase}")
    print(f"{'='*60}")

    print_status()

    pipeline_start = time.perf_counter()

    for phase in range(args.start_phase, 5):

        # ── Explicit skip ──────────────────────────────────────────────────────
        if phase == args.skip_phase:
            marker = PHASE_MARKERS[phase]
            if not marker.exists():
                print(
                    f"\n⚠   Phase {phase} ({PHASE_NAMES[phase]}) skipped via --skip-phase, "
                    f"but {marker.name} does not exist. "
                    f"Phase {phase + 1} may fail if it needs this file."
                )
            else:
                print(f"\n⏭   Phase {phase} ({PHASE_NAMES[phase]}): skipped (--skip-phase)")
            continue

        # ── Resume: skip completed phases ──────────────────────────────────────
        marker = PHASE_MARKERS[phase]
        if args.resume and marker.exists():
            print(f"\n⏭   Phase {phase} ({PHASE_NAMES[phase]}): skipped (output exists, --resume)")
            continue

        # ── Build per-phase arguments ──────────────────────────────────────────
        phase_args: list[str] = []

        if args.dry_run:
            phase_args.append("--dry-run")

        # Phase 1 and 3 support --resume internally
        if args.resume and phase in (1, 3):
            phase_args.append("--resume")

        if phase == 1 and args.complaints is not None:
            phase_args.extend(["--complaints", str(args.complaints)])

        # ── Run the phase ──────────────────────────────────────────────────────
        success = run_phase(phase, phase_args)

        if not success:
            elapsed = time.perf_counter() - pipeline_start
            print(f"\n{'='*60}")
            print(f"  PIPELINE ABORTED at Phase {phase} ({PHASE_NAMES[phase]})")
            print(f"  Elapsed : {fmt_elapsed(elapsed)}")
            print(f"  Fix the error above, then re-run with --resume to continue.")
            print(f"{'='*60}")
            sys.exit(1)

    # ── Pipeline complete ──────────────────────────────────────────────────────
    elapsed = time.perf_counter() - pipeline_start
    final   = PHASE_MARKERS[4]

    print(f"\n{'='*60}")
    print(f"  PIPELINE COMPLETE")
    print(f"  Total time : {fmt_elapsed(elapsed)}")

    if final.exists():
        try:
            import pandas as pd
            n = len(pd.read_csv(final))
            print(f"  Final rows : {n:,}")
        except Exception:
            pass
        print(f"  Output     : {final}")

    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
