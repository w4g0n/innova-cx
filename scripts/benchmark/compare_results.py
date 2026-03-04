"""
Benchmark Comparison Report Generator
=======================================
Reads Tier 1 (LLM classification) and Tier 2 (E2E smoke) result files for
two models and prints a side-by-side comparison report.

Usage:
    python scripts/benchmark/compare_results.py \
        --tier1-a  scripts/benchmark/results_current.json \
        --tier1-b  scripts/benchmark/results_qwen.json \
        --tier2-a  scripts/benchmark/e2e_current.json \
        --tier2-b  scripts/benchmark/e2e_qwen.json \
        --labels   current  "qwen2.5-1.5b" \
        [--output  scripts/benchmark/comparison_report.txt]
"""

import argparse
import json
import sys
from pathlib import Path


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load(path: str) -> dict:
    p = Path(path)
    if not p.exists():
        print(f"[ERROR] File not found: {path}", file=sys.stderr)
        sys.exit(1)
    with p.open() as f:
        return json.load(f)


def _fmt(val, suffix="", width=7) -> str:
    return f"{val:{width}}{suffix}"


def _delta_str(a: float, b: float, invert: bool = False) -> str:
    """Return coloured delta string. invert=True means lower is better."""
    d = b - a
    if invert:
        d = -d
    sign = "+" if d >= 0 else ""
    return f"{sign}{d:+.1f}"


# ---------------------------------------------------------------------------
# Tier 1 comparison
# ---------------------------------------------------------------------------

TIER1_TASKS = ["primary_intent", "secondary_intent", "aggression"]

def _compare_tier1(data_a: dict, data_b: dict, label_a: str, label_b: str) -> list[str]:
    lines = []
    w = 16
    col_w = 10

    lines.append("")
    lines.append("  TIER 1 — LLM CLASSIFICATION BENCHMARK")
    lines.append(f"  {'Task':<{w}}  {label_a:>{col_w}}  {label_b:>{col_w}}  {'Delta':>8}")
    lines.append("  " + "-" * (w + 2 * col_w + 14))

    sum_a = data_a.get("summary", {})
    sum_b = data_b.get("summary", {})

    for task in TIER1_TASKS:
        sa = sum_a.get(task, {})
        sb = sum_b.get(task, {})
        if not sa and not sb:
            continue
        acc_a = sa.get("accuracy_pct", 0.0)
        acc_b = sb.get("accuracy_pct", 0.0)
        delta = _delta_str(acc_a, acc_b)
        lines.append(
            f"  {task + ' acc':<{w}}  {acc_a:>{col_w-1}.1f}%  {acc_b:>{col_w-1}.1f}%  {delta:>8}"
        )

    lines.append("")

    # Parse success rate
    for task in TIER1_TASKS:
        sa = sum_a.get(task, {})
        sb = sum_b.get(task, {})
        if not sa and not sb:
            continue
        ps_a = sa.get("parse_success_rate_pct", 0.0)
        ps_b = sb.get("parse_success_rate_pct", 0.0)
        delta = _delta_str(ps_a, ps_b)
        lines.append(
            f"  {task + ' parse%':<{w}}  {ps_a:>{col_w-1}.1f}%  {ps_b:>{col_w-1}.1f}%  {delta:>8}"
        )

    lines.append("")

    # Latency
    for task in TIER1_TASKS:
        sa = sum_a.get(task, {})
        sb = sum_b.get(task, {})
        if not sa and not sb:
            continue
        lat_a = sa.get("latency_mean_ms", 0.0)
        lat_b = sb.get("latency_mean_ms", 0.0)
        delta = _delta_str(lat_a, lat_b, invert=True)  # lower is better
        lines.append(
            f"  {task + ' mean_ms':<{w}}  {lat_a:>{col_w-1}.0f}   {lat_b:>{col_w-1}.0f}   {delta:>8}"
        )

    lines.append("")
    for task in TIER1_TASKS:
        sa = sum_a.get(task, {})
        sb = sum_b.get(task, {})
        if not sa and not sb:
            continue
        p95_a = sa.get("latency_p95_ms", 0.0)
        p95_b = sb.get("latency_p95_ms", 0.0)
        delta = _delta_str(p95_a, p95_b, invert=True)
        lines.append(
            f"  {task + ' p95_ms':<{w}}  {p95_a:>{col_w-1}.0f}   {p95_b:>{col_w-1}.0f}   {delta:>8}"
        )

    # Per-label breakdown for primary and secondary intent
    lines.append("")
    lines.append("  Per-label accuracy:")
    for task in ["primary_intent", "secondary_intent"]:
        sa = sum_a.get(task, {})
        sb = sum_b.get(task, {})
        labels_a = sa.get("per_label", {})
        labels_b = sb.get("per_label", {})
        all_labels = sorted(set(list(labels_a.keys()) + list(labels_b.keys())))
        for lbl in all_labels:
            acc_a = labels_a.get(lbl, {}).get("accuracy", 0.0)
            acc_b = labels_b.get(lbl, {}).get("accuracy", 0.0)
            total_a = labels_a.get(lbl, {}).get("total", 0)
            total_b = labels_b.get(lbl, {}).get("total", 0)
            delta = _delta_str(acc_a, acc_b)
            tag = f"{task}/{lbl}(n={total_a})"
            lines.append(
                f"  {tag:<{w+4}}  {acc_a:>{col_w-1}.1f}%  {acc_b:>{col_w-1}.1f}%  {delta:>8}"
            )

    return lines


# ---------------------------------------------------------------------------
# Tier 2 comparison
# ---------------------------------------------------------------------------

def _compare_tier2(data_a: dict, data_b: dict, label_a: str, label_b: str) -> list[str]:
    lines = []
    w = 18
    col_w = 10

    meta_a = data_a.get("meta", {})
    meta_b = data_b.get("meta", {})
    sum_a = data_a.get("summary", {})
    sum_b = data_b.get("summary", {})
    scen_a = {r["scenario_id"]: r for r in data_a.get("scenarios", [])}
    scen_b = {r["scenario_id"]: r for r in data_b.get("scenarios", [])}

    lines.append("")
    lines.append("  TIER 2 — E2E CONVERSATION SMOKE SUITE")
    lines.append(f"  {'Metric':<{w}}  {label_a:>{col_w}}  {label_b:>{col_w}}  {'Delta':>8}")
    lines.append("  " + "-" * (w + 2 * col_w + 14))

    total_a = meta_a.get("total_scenarios", 0)
    pass_a = meta_a.get("passed", 0)
    total_b = meta_b.get("total_scenarios", 0)
    pass_b = meta_b.get("passed", 0)

    lines.append(
        f"  {'Completion':<{w}}  {pass_a:>{col_w-3}}/{total_a}   {pass_b:>{col_w-3}}/{total_b}   "
    )

    cr_a = sum_a.get("completion_rate_pct", 0.0)
    cr_b = sum_b.get("completion_rate_pct", 0.0)
    delta = _delta_str(cr_a, cr_b)
    lines.append(f"  {'Completion rate':<{w}}  {cr_a:>{col_w-1}.1f}%  {cr_b:>{col_w-1}.1f}%  {delta:>8}")

    avg_a = sum_a.get("avg_scenario_duration_s", 0.0)
    avg_b = sum_b.get("avg_scenario_duration_s", 0.0)
    delta_lat = _delta_str(avg_a, avg_b, invert=True)
    lines.append(f"  {'Avg duration (s)':<{w}}  {avg_a:>{col_w-1}.1f}   {avg_b:>{col_w-1}.1f}   {delta_lat:>8}")

    # Per-scenario breakdown
    all_ids = sorted(set(list(scen_a.keys()) + list(scen_b.keys())))
    if all_ids:
        lines.append("")
        lines.append("  Per-scenario results:")
        for sid in all_ids:
            ra = scen_a.get(sid, {})
            rb = scen_b.get(sid, {})
            name = ra.get("name") or rb.get("name") or f"scenario_{sid}"
            ok_a = "PASS" if ra.get("success") else "FAIL" if ra else "N/A "
            ok_b = "PASS" if rb.get("success") else "FAIL" if rb else "N/A "
            dur_a = f"{ra.get('duration_s', 0):5.1f}s" if ra else "  N/A "
            dur_b = f"{rb.get('duration_s', 0):5.1f}s" if rb else "  N/A "
            lines.append(f"  {sid:02d}. {name[:38]:<38}  {ok_a}({dur_a})  {ok_b}({dur_b})")

    # List failed scenarios
    fail_a = [r for r in data_a.get("scenarios", []) if not r.get("success")]
    fail_b = [r for r in data_b.get("scenarios", []) if not r.get("success")]
    if fail_a:
        lines.append(f"\n  {label_a} failures:")
        for r in fail_a:
            lines.append(f"    - {r['scenario_id']:02d}. {r['name']}: {r.get('error', '')}")
    if fail_b:
        lines.append(f"\n  {label_b} failures:")
        for r in fail_b:
            lines.append(f"    - {r['scenario_id']:02d}. {r['name']}: {r.get('error', '')}")

    return lines


# ---------------------------------------------------------------------------
# Recommendation
# ---------------------------------------------------------------------------

def _recommendation(t1_a: dict, t1_b: dict, t2_a: dict, t2_b: dict,
                    label_a: str, label_b: str) -> list[str]:
    lines = []
    lines.append("")
    lines.append("  RECOMMENDATION")
    lines.append("  " + "-" * 60)

    sum1_a = t1_a.get("summary", {})
    sum1_b = t1_b.get("summary", {})
    sum2_a = t2_a.get("summary", {})
    sum2_b = t2_b.get("summary", {})

    # Score: avg accuracy across tasks, minus latency penalty, plus completion rate
    tasks = [k for k in TIER1_TASKS if k in sum1_a or k in sum1_b]

    acc_a = sum(sum1_a.get(t, {}).get("accuracy_pct", 0.0) for t in tasks) / max(len(tasks), 1)
    acc_b = sum(sum1_b.get(t, {}).get("accuracy_pct", 0.0) for t in tasks) / max(len(tasks), 1)

    cr_a = sum2_a.get("completion_rate_pct", 0.0)
    cr_b = sum2_b.get("completion_rate_pct", 0.0)

    lat_a = sum(sum1_a.get(t, {}).get("latency_mean_ms", 0.0) for t in tasks) / max(len(tasks), 1)
    lat_b = sum(sum1_b.get(t, {}).get("latency_mean_ms", 0.0) for t in tasks) / max(len(tasks), 1)

    # Weighted composite score: accuracy(60%) + completion rate(30%) - latency_penalty(10%)
    # Latency penalty: normalised relative to max
    max_lat = max(lat_a, lat_b, 1.0)
    lat_pen_a = (lat_a / max_lat) * 10
    lat_pen_b = (lat_b / max_lat) * 10

    score_a = acc_a * 0.60 + cr_a * 0.30 - lat_pen_a
    score_b = acc_b * 0.60 + cr_b * 0.30 - lat_pen_b

    lines.append(f"  {label_a:<20}: avg_acc={acc_a:.1f}%  e2e_rate={cr_a:.1f}%  mean_lat={lat_a:.0f}ms  score={score_a:.1f}")
    lines.append(f"  {label_b:<20}: avg_acc={acc_b:.1f}%  e2e_rate={cr_b:.1f}%  mean_lat={lat_b:.0f}ms  score={score_b:.1f}")
    lines.append("")

    margin = abs(score_a - score_b)
    if margin < 2.0:
        rec = f"NO CLEAR WINNER — scores within margin ({margin:.1f} pts). Keep {label_a} (no migration risk)."
    elif score_b > score_a:
        rec = f"SWITCH TO {label_b.upper()} — {label_b} outscores {label_a} by {margin:.1f} pts."
    else:
        rec = f"KEEP {label_a.upper()} — {label_a} outscores {label_b} by {margin:.1f} pts."

    lines.append(f"  >>> {rec}")
    lines.append("")
    lines.append(
        "  Note: This score is computed automatically. Review per-task accuracy deltas and "
        "qualitative responses before making a final decision."
    )

    return lines


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Compare benchmark results for two models")
    parser.add_argument("--tier1-a", required=True, help="Tier 1 results for model A")
    parser.add_argument("--tier1-b", required=True, help="Tier 1 results for model B")
    parser.add_argument("--tier2-a", required=True, help="Tier 2 results for model A")
    parser.add_argument("--tier2-b", required=True, help="Tier 2 results for model B")
    parser.add_argument("--labels", nargs=2, default=["model_a", "model_b"],
                        metavar=("LABEL_A", "LABEL_B"),
                        help="Short labels for the two models")
    parser.add_argument("--output", default=None, help="Optional path to write report text")
    args = parser.parse_args()

    label_a, label_b = args.labels

    t1_a = _load(args.tier1_a)
    t1_b = _load(args.tier1_b)
    t2_a = _load(args.tier2_a)
    t2_b = _load(args.tier2_b)

    meta_a = t1_a.get("meta", {}).get("model_diagnostics", {})
    meta_b = t1_b.get("meta", {}).get("model_diagnostics", {})

    border = "=" * 72
    lines = [
        border,
        f"  CHATBOT LLM BENCHMARK COMPARISON REPORT",
        f"  Generated: {__import__('time').strftime('%Y-%m-%d %H:%M:%S UTC', __import__('time').gmtime())}",
        border,
        f"  Model A ({label_a}): {meta_a.get('chatbot_model_path') or 'N/A'}  "
        f"[mode={meta_a.get('chatbot_mode', '?')}]",
        f"  Model B ({label_b}): {meta_b.get('chatbot_model_path') or 'N/A'}  "
        f"[mode={meta_b.get('chatbot_mode', '?')}]",
        border,
    ]

    lines += _compare_tier1(t1_a, t1_b, label_a, label_b)
    lines.append(border)
    lines += _compare_tier2(t2_a, t2_b, label_a, label_b)
    lines.append(border)
    lines += _recommendation(t1_a, t1_b, t2_a, t2_b, label_a, label_b)
    lines.append(border)

    report = "\n".join(lines) + "\n"
    print(report)

    if args.output:
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        with open(args.output, "w") as f:
            f.write(report)
        print(f"Report written to {args.output}", file=sys.stderr)


if __name__ == "__main__":
    main()
