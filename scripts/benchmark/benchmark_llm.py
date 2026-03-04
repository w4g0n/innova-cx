"""
Tier 1 — LLM Classification Benchmark
=======================================
Runs inside the chatbot Docker container via docker exec.
Tests intent classification and aggression detection accuracy with 200 labeled cases.
Zero DB writes — calls intent functions directly, no sessions or logs created.

Usage (from VM host):
    docker cp scripts/benchmark/benchmark_llm.py innovacx-chatbot:/tmp/benchmark_llm.py
    docker cp scripts/benchmark/test_cases.json innovacx-chatbot:/tmp/test_cases.json
    docker exec -e PYTHONPATH=/app innovacx-chatbot \
        python /tmp/benchmark_llm.py \
        --test-cases /tmp/test_cases.json \
        --output /tmp/results_MODEL.json
    docker cp innovacx-chatbot:/tmp/results_MODEL.json scripts/benchmark/results_MODEL.json
"""

import argparse
import json
import logging
import sys
import time
from pathlib import Path

# Ensure /app is on the path so core.* imports work inside the container
sys.path.insert(0, "/app")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    stream=sys.stderr,
)
log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    sorted_v = sorted(values)
    idx = int(len(sorted_v) * pct / 100)
    idx = min(idx, len(sorted_v) - 1)
    return round(sorted_v[idx], 1)


def _summary(results: list[dict], label_key: str = "expected") -> dict:
    if not results:
        return {}
    total = len(results)
    correct = sum(1 for r in results if r["correct"])
    parse_ok = sum(1 for r in results if r.get("parse_success", True))
    latencies = [r["latency_ms"] for r in results]
    per_label: dict[str, dict] = {}
    for r in results:
        lbl = str(r[label_key])
        per_label.setdefault(lbl, {"total": 0, "correct": 0})
        per_label[lbl]["total"] += 1
        if r["correct"]:
            per_label[lbl]["correct"] += 1
    for v in per_label.values():
        v["accuracy"] = round(v["correct"] / v["total"] * 100, 1) if v["total"] else 0.0
    return {
        "total": total,
        "correct": correct,
        "accuracy_pct": round(correct / total * 100, 1),
        "parse_success_rate_pct": round(parse_ok / total * 100, 1),
        "latency_mean_ms": round(sum(latencies) / len(latencies), 1),
        "latency_p50_ms": _percentile(latencies, 50),
        "latency_p95_ms": _percentile(latencies, 95),
        "per_label": per_label,
    }


# ---------------------------------------------------------------------------
# Task runners
# ---------------------------------------------------------------------------

def _run_primary_intent(cases: list[dict]) -> list[dict]:
    from core.intent import classify_primary_intent

    results = []
    for i, c in enumerate(cases):
        log.info("primary_intent %d/%d  id=%s", i + 1, len(cases), c["id"])
        user_text = c["input"]["user_text"]
        history = c["input"].get("history", [])
        expected = c["expected"]
        t0 = time.perf_counter()
        try:
            predicted = classify_primary_intent(user_text, history)
            error = None
        except Exception as exc:
            predicted = "unknown"
            error = str(exc)
            log.warning("primary_intent error on %s: %s", c["id"], exc)
        latency_ms = round((time.perf_counter() - t0) * 1000, 1)
        results.append({
            "id": c["id"],
            "user_text": user_text,
            "expected": expected,
            "predicted": predicted,
            "correct": predicted == expected,
            "parse_success": error is None,
            "latency_ms": latency_ms,
            "error": error,
        })
    return results


def _run_secondary_intent(cases: list[dict]) -> list[dict]:
    from core.intent import classify_secondary_intent

    results = []
    for i, c in enumerate(cases):
        log.info("secondary_intent %d/%d  id=%s", i + 1, len(cases), c["id"])
        user_text = c["input"]["user_text"]
        history = c["input"].get("history", [])
        expected = c["expected"]
        t0 = time.perf_counter()
        try:
            predicted = classify_secondary_intent(user_text, history)
            error = None
        except Exception as exc:
            predicted = "unknown"
            error = str(exc)
            log.warning("secondary_intent error on %s: %s", c["id"], exc)
        latency_ms = round((time.perf_counter() - t0) * 1000, 1)
        results.append({
            "id": c["id"],
            "user_text": user_text,
            "expected": expected,
            "predicted": predicted,
            "correct": predicted == expected,
            "parse_success": error is None,
            "latency_ms": latency_ms,
            "error": error,
        })
    return results


def _run_aggression(cases: list[dict]) -> list[dict]:
    from core.intent import detect_aggression

    results = []
    for i, c in enumerate(cases):
        log.info("aggression %d/%d  id=%s", i + 1, len(cases), c["id"])
        user_text = c["input"]["user_text"]
        history = c["input"].get("history", [])
        expected = c["expected"]  # bool
        t0 = time.perf_counter()
        try:
            is_aggressive, score = detect_aggression(user_text, history)
            error = None
        except Exception as exc:
            is_aggressive, score = False, 0.0
            error = str(exc)
            log.warning("aggression error on %s: %s", c["id"], exc)
        latency_ms = round((time.perf_counter() - t0) * 1000, 1)
        results.append({
            "id": c["id"],
            "user_text": user_text,
            "expected": expected,
            "predicted": is_aggressive,
            "score": round(score, 4),
            "correct": is_aggressive == expected,
            "parse_success": error is None,
            "latency_ms": latency_ms,
            "error": error,
        })
    return results


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark LLM classification tasks")
    parser.add_argument("--test-cases", required=True, help="Path to test_cases.json")
    parser.add_argument("--output", required=True, help="Path to write results JSON")
    parser.add_argument(
        "--tasks",
        nargs="+",
        default=["primary_intent", "secondary_intent", "aggression"],
        choices=["primary_intent", "secondary_intent", "aggression"],
        help="Which tasks to run (default: all)",
    )
    args = parser.parse_args()

    # ── Load and verify diagnostics ──────────────────────────────────────────
    try:
        from core.llm import get_llm_diagnostics
        diag = get_llm_diagnostics()
        log.info("LLM diagnostics: %s", json.dumps(diag))
        if diag.get("chatbot_mode") == "mock":
            log.warning(
                "CHATBOT_USE_MOCK=true or no model path configured. "
                "Results will reflect mock responses, not a real LLM. "
                "This is useful for validating the harness but NOT for model comparison."
            )
    except Exception as exc:
        log.error("Could not load LLM diagnostics: %s", exc)
        sys.exit(1)

    # ── Load test cases ───────────────────────────────────────────────────────
    test_cases_path = Path(args.test_cases)
    if not test_cases_path.exists():
        log.error("test_cases.json not found at %s", test_cases_path)
        sys.exit(1)
    with test_cases_path.open() as f:
        data = json.load(f)
    log.info(
        "Loaded test cases: primary_intent=%d, secondary_intent=%d, aggression=%d",
        len(data.get("primary_intent", [])),
        len(data.get("secondary_intent", [])),
        len(data.get("aggression", [])),
    )

    # ── Run tasks ─────────────────────────────────────────────────────────────
    output: dict = {
        "meta": {
            "model_diagnostics": diag,
            "tasks_run": args.tasks,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        },
        "results": {},
        "summary": {},
    }

    task_start = time.perf_counter()

    if "primary_intent" in args.tasks:
        log.info("--- Running primary_intent (%d cases) ---", len(data["primary_intent"]))
        pi_results = _run_primary_intent(data["primary_intent"])
        output["results"]["primary_intent"] = pi_results
        output["summary"]["primary_intent"] = _summary(pi_results)
        log.info(
            "primary_intent done: accuracy=%.1f%%  p95=%.0fms",
            output["summary"]["primary_intent"]["accuracy_pct"],
            output["summary"]["primary_intent"]["latency_p95_ms"],
        )

    if "secondary_intent" in args.tasks:
        log.info("--- Running secondary_intent (%d cases) ---", len(data["secondary_intent"]))
        si_results = _run_secondary_intent(data["secondary_intent"])
        output["results"]["secondary_intent"] = si_results
        output["summary"]["secondary_intent"] = _summary(si_results)
        log.info(
            "secondary_intent done: accuracy=%.1f%%  p95=%.0fms",
            output["summary"]["secondary_intent"]["accuracy_pct"],
            output["summary"]["secondary_intent"]["latency_p95_ms"],
        )

    if "aggression" in args.tasks:
        log.info("--- Running aggression (%d cases) ---", len(data["aggression"]))
        ag_results = _run_aggression(data["aggression"])
        output["results"]["aggression"] = ag_results
        output["summary"]["aggression"] = _summary(ag_results, label_key="expected")
        log.info(
            "aggression done: accuracy=%.1f%%  p95=%.0fms",
            output["summary"]["aggression"]["accuracy_pct"],
            output["summary"]["aggression"]["latency_p95_ms"],
        )

    total_elapsed = round(time.perf_counter() - task_start, 1)
    output["meta"]["total_elapsed_s"] = total_elapsed
    log.info("All tasks complete in %.1fs", total_elapsed)

    # ── Write output ──────────────────────────────────────────────────────────
    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w") as f:
        json.dump(output, f, indent=2)
    log.info("Results written to %s", out_path)

    # ── Print inline summary ──────────────────────────────────────────────────
    print("\n=== BENCHMARK SUMMARY ===")
    print(f"Model mode : {diag.get('chatbot_mode', 'unknown')}")
    print(f"Model path : {diag.get('chatbot_model_path', 'N/A')}")
    print(f"Elapsed    : {total_elapsed}s\n")
    for task, s in output["summary"].items():
        print(
            f"{task:<22} accuracy={s['accuracy_pct']:5.1f}%  "
            f"parse_ok={s['parse_success_rate_pct']:5.1f}%  "
            f"mean={s['latency_mean_ms']:6.0f}ms  "
            f"p95={s['latency_p95_ms']:6.0f}ms"
        )
    print()


if __name__ == "__main__":
    main()
