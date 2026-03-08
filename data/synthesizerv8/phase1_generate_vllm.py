"""
Phase 1 (vLLM) — High-throughput Synthetic Complaint Generation
================================================================
Drop-in replacement for phase1_generate.py using vLLM instead of
HuggingFace generate(). Expected speedup: 5-10x on the same GPU.

HOW IT WORKS
------------
vLLM loads the model once, then uses continuous batching + PagedAttention
to process multiple prompts simultaneously. We submit prompts in chunks,
collect outputs, filter failures, and requeue retries — so the GPU stays
fully occupied the entire time instead of waiting between single generations.

INSTALL (run once in the project venv)
---------------------------------------
    pip install vllm

HOW TO USE INSTEAD OF phase1_generate.py
-----------------------------------------
Option A — Run directly:
    python phase1_generate_vllm.py [same args as phase1_generate.py]

Option B — Use via run_pipeline.py (edit one line):
    In run_pipeline.py, change PHASE_SCRIPTS[1] from:
        "phase1_generate.py"
    to:
        "phase1_generate_vllm.py"

NOTES
------
- No BitsAndBytes quantization: vLLM uses its own memory management.
  Phi-4-mini (3.8B) in fp16 uses ~7.6GB — fits the T4's 16GB with room
  for a large KV cache, enabling bigger effective batch sizes.
- Output format is identical to phase1_generate.py — Phases 2/3/4 are
  unaffected and require no changes.
- Checkpoint/resume logic is preserved: --resume works identically.
- All CLI args are the same as phase1_generate.py.
"""

from __future__ import annotations

import argparse
import collections
import csv
import random
import sys
from pathlib import Path

# ── Import shared logic from phase1_generate.py ───────────────────────────────
# phase1_generate.py defines all constants, helpers, and plan-building logic.
# We import them here so any fix to shared functions automatically applies here.
_here = Path(__file__).resolve().parent
sys.path.insert(0, str(_here))

from phase1_generate import (  # noqa: E402
    MODEL_NAME,
    OUTPUT_DIR,
    CHECKPOINT_PATH,
    COMPLETE_PATH,
    CHECKPOINT_EVERY,
    DEPARTMENTS,
    LABEL_COLS,
    STYLES,
    LENGTH_HINTS,
    PRIMARY_DOMAIN,
    LEASING_ISSUES,
    SAFETY_ISSUES,
    MIN_SUBJECT_LEN,
    MIN_TEXT_LEN,
    _RoundRobinSampler,
    parse_json_response,
    build_system_prompt,
    build_user_prompt,
    build_plan,
)

# ── Phi-4 chat-template formatter ─────────────────────────────────────────────
SYSTEM_PROMPT = build_system_prompt()


def _format_prompt(user_text: str) -> str:
    """Format a single turn using Phi-4-mini's chat template."""
    return (
        f"<|system|>\n{SYSTEM_PROMPT}<|end|>\n"
        f"<|user|>\n{user_text}<|end|>\n"
        f"<|assistant|>\n"
    )


# ── Checkpoint helpers ─────────────────────────────────────────────────────────
_FIELDNAMES = [
    "ticket_id", "subject", "text", "domain", "style", "issue_hint",
    "department", "issue_severity", "issue_urgency",
    "safety_concern", "business_impact",
]


def _load_checkpoint() -> tuple[list[dict], int]:
    if CHECKPOINT_PATH.exists():
        with open(CHECKPOINT_PATH, newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        if rows:
            last_id = rows[-1].get("ticket_id", "V8-00000")
            start_idx = int(last_id.split("-")[1]) + 1
            print(f"Resuming from checkpoint: {len(rows)} rows, next index {start_idx}")
            return rows, start_idx
    return [], 0


def _save_csv(path: Path, rows: list[dict]) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=_FIELDNAMES)
        w.writeheader()
        w.writerows(rows)


# ── Per-item prompt builder ────────────────────────────────────────────────────
def _make_item_data(
    item: dict,
    safety_sampler: _RoundRobinSampler,
    leasing_sampler: _RoundRobinSampler,
) -> dict:
    """Build prompt data for a single plan item with fresh randomness."""
    style       = random.choice(STYLES)
    length_hint = random.choice(LENGTH_HINTS)
    domain      = item["domain"]

    if item["target_safety_concern"]:
        issue_hint = safety_sampler.next()
    elif domain == PRIMARY_DOMAIN:
        issue_hint = leasing_sampler.next()
    else:
        issue_hint = None

    target_labels = {
        "department":      item["target_department"],
        "issue_severity":  item["target_issue_severity"],
        "issue_urgency":   item["target_issue_urgency"],
        "safety_concern":  item["target_safety_concern"],
        "business_impact": item["target_business_impact"],
    }
    user_text = build_user_prompt(domain, style, issue_hint, length_hint, target_labels)
    prompt    = _format_prompt(user_text)

    return {
        "item":          item,
        "style":         style,
        "issue_hint":    issue_hint or "",
        "target_labels": target_labels,
        "prompt":        prompt,
        "retries_used":  0,
    }


# ── Main ───────────────────────────────────────────────────────────────────────
def main() -> None:
    parser = argparse.ArgumentParser(
        description="Phase 1 — vLLM-powered complaint generation (faster drop-in)"
    )
    parser.add_argument("--complaints",     type=int,   default=10_000)
    parser.add_argument("--max-new-tokens", type=int,   default=256)
    parser.add_argument("--temperature",    type=float, default=0.7)
    parser.add_argument("--top-p",          type=float, default=0.9)
    parser.add_argument("--do-sample",      action="store_true")
    parser.add_argument("--retries",        type=int,   default=3,
                        help="Max retry attempts per complaint on failure")
    parser.add_argument("--batch-size",     type=int,   default=64,
                        help="Prompts per vLLM batch. Higher = better GPU "
                             "utilization but more VRAM. Start with 32-64.")
    parser.add_argument("--dry-run",        action="store_true")
    parser.add_argument("--dry-run-count",  type=int,   default=50)
    parser.add_argument("--resume",         action="store_true")
    args = parser.parse_args()

    # ── Setup ──────────────────────────────────────────────────────────────────
    OUTPUT_DIR.mkdir(exist_ok=True)
    n = args.dry_run_count if args.dry_run else args.complaints
    effective_max_tokens = min(args.max_new_tokens, 96) if args.dry_run else args.max_new_tokens

    if args.dry_run:
        print(f"[DRY RUN] Generating {n} complaints via vLLM")

    # ── Load model ─────────────────────────────────────────────────────────────
    try:
        from vllm import LLM, SamplingParams
    except ImportError:
        print(
            "ERROR: vLLM is not installed.\n"
            "Install it with:  pip install vllm\n"
            "Then re-run this script."
        )
        sys.exit(1)

    print(f"Loading {MODEL_NAME} with vLLM (fp16, no quantization)...")
    llm = LLM(
        model=MODEL_NAME,
        dtype="float16",
        gpu_memory_utilization=0.85,
        trust_remote_code=True,
        max_model_len=2048,
    )

    temperature = args.temperature if args.do_sample else 0.0
    top_p       = args.top_p       if args.do_sample else 1.0
    sampling_params = SamplingParams(
        temperature=temperature,
        top_p=top_p,
        max_tokens=effective_max_tokens,
    )
    print(f"Model ready | temperature={temperature} | max_tokens={effective_max_tokens}")

    # ── Checkpoint / resume ────────────────────────────────────────────────────
    if args.resume:
        results, start_idx = _load_checkpoint()
    else:
        results, start_idx = [], 0

    already_done = len(results)
    remaining    = n - already_done
    if remaining <= 0:
        print(f"Already have {already_done}/{n} complaints. Nothing to do.")
        _save_csv(COMPLETE_PATH, results)
        return

    # ── Build plan and initial queue ───────────────────────────────────────────
    plan = build_plan(remaining)

    safety_sampler  = _RoundRobinSampler(SAFETY_ISSUES)
    leasing_sampler = _RoundRobinSampler(LEASING_ISSUES)

    queue = [
        _make_item_data(item, safety_sampler, leasing_sampler)
        for item in plan
    ]

    stats        = {"accepted": 0, "failed": 0}
    BATCH        = args.batch_size
    MAX_RETRIES  = args.retries

    print(
        f"\nStarting generation: {remaining} complaints | "
        f"batch_size={BATCH} | max_retries={MAX_RETRIES}\n"
    )

    # ── Generation loop ────────────────────────────────────────────────────────
    while queue and stats["accepted"] < remaining:
        batch, queue = queue[:BATCH], queue[BATCH:]

        # Submit entire batch to vLLM at once
        outputs = llm.generate(
            [entry["prompt"] for entry in batch],
            sampling_params,
            use_tqdm=False,
        )

        retry_next: list[dict] = []

        for entry, output in zip(batch, outputs):
            raw    = output.outputs[0].text
            parsed = parse_json_response(raw)
            accepted = False

            if parsed is not None:
                got_dept      = parsed.get("department")
                expected_dept = entry["target_labels"]["department"]

                if got_dept == expected_dept:
                    # Force planned labels for all non-department fields
                    for key, val in entry["target_labels"].items():
                        if key != "department":
                            parsed[key] = val

                    ticket_id = f"V8-{start_idx + already_done + stats['accepted']:05d}"
                    results.append({
                        "ticket_id":      ticket_id,
                        "subject":        parsed["subject"],
                        "text":           parsed["text"],
                        "domain":         entry["item"]["domain"],
                        "style":          entry["style"],
                        "issue_hint":     entry["issue_hint"],
                        "department":     parsed["department"],
                        "issue_severity": parsed["issue_severity"],
                        "issue_urgency":  parsed["issue_urgency"],
                        "safety_concern": str(parsed["safety_concern"]),
                        "business_impact": parsed["business_impact"],
                    })
                    stats["accepted"] += 1
                    accepted = True

            if not accepted:
                if entry["retries_used"] < MAX_RETRIES:
                    # Rebuild with fresh randomness for the retry
                    retry_entry = _make_item_data(
                        entry["item"], safety_sampler, leasing_sampler
                    )
                    retry_entry["retries_used"] = entry["retries_used"] + 1
                    retry_next.append(retry_entry)
                else:
                    stats["failed"] += 1

        # Retries go to front of queue so they're resolved quickly
        queue = retry_next + queue

        # Progress line
        total_done = stats["accepted"] + stats["failed"]
        pct        = 100 * stats["accepted"] / remaining if remaining else 0
        print(
            f"  Accepted {stats['accepted']:>5}/{remaining} ({pct:5.1f}%) | "
            f"Failed {stats['failed']:>4} | Queue {len(queue):>5}",
            end="\r",
            flush=True,
        )

        # Checkpoint every N accepted
        if stats["accepted"] > 0 and stats["accepted"] % CHECKPOINT_EVERY == 0:
            _save_csv(CHECKPOINT_PATH, results)

    print()  # newline after progress line

    # ── Save final outputs ─────────────────────────────────────────────────────
    _save_csv(CHECKPOINT_PATH, results)
    _save_csv(COMPLETE_PATH,   results)

    # ── Summary ────────────────────────────────────────────────────────────────
    safety_count = sum(
        1 for r in results if str(r.get("safety_concern", "")).lower() == "true"
    )
    dept_counts  = collections.Counter(r["department"] for r in results)
    domain_counts = collections.Counter(r["domain"] for r in results)

    print("\n" + "=" * 55)
    print("Phase 1 complete (vLLM)")
    print(f"  Accepted  : {stats['accepted']}")
    print(f"  Failed    : {stats['failed']}")
    print(f"  Total     : {len(results)}")
    print(f"  Saved to  : {COMPLETE_PATH}")

    print("\nDomain breakdown:")
    for domain, count in sorted(domain_counts.items(), key=lambda x: -x[1]):
        print(f"  {domain:<45} {count}")

    print("\nDepartment breakdown:")
    for dept, count in sorted(dept_counts.items(), key=lambda x: -x[1]):
        print(f"  {dept:<45} {count}")

    if results:
        pct = 100 * safety_count / len(results)
        print(f"\nSafety-seeded rows: {safety_count} ({pct:.1f}%)")


if __name__ == "__main__":
    main()
