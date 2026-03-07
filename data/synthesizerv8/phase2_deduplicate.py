"""
Phase 2 — Deduplication
=======================
Removes exact and near-duplicate complaints from Phase 1 output.

Uses TF-IDF cosine similarity (default threshold: 0.85) to cluster near-duplicates.
From each cluster, the longest text is kept — it contains the most information.

Threshold 0.85 is deliberately more lenient than V5's 0.92: LLM-generated text
is more naturally varied than template-based text, so we only remove genuinely
similar outputs, not topically related but distinctly worded complaints.

Usage:
    python phase2_deduplicate.py
    python phase2_deduplicate.py --input output/phase1_complete.csv
    python phase2_deduplicate.py --threshold 0.90
"""

import argparse
import json
import logging
import time
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

BASE_DIR          = Path(__file__).resolve().parent
OUTPUT_DIR        = BASE_DIR / "output"
DEFAULT_INPUT     = OUTPUT_DIR / "phase1_complete.csv"
DEFAULT_OUTPUT    = OUTPUT_DIR / "phase2_deduplicated.csv"
STATS_PATH        = OUTPUT_DIR / "phase2_stats.json"
DEFAULT_THRESHOLD = 0.85
MIN_TEXT_LENGTH   = 20


# ── Quality filter ─────────────────────────────────────────────────────────────

def filter_short(df: pd.DataFrame, min_len: int) -> tuple[pd.DataFrame, int]:
    original = len(df)
    df       = df[df["text"].astype(str).str.strip().str.len() >= min_len].copy()
    removed  = original - len(df)
    if removed:
        log.info(f"Quality filter: removed {removed} rows (text < {min_len} chars)")
    return df.reset_index(drop=True), removed


# ── Exact deduplication ────────────────────────────────────────────────────────

def remove_exact_duplicates(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    original = len(df)
    # Normalize: lowercase, strip, collapse whitespace — but keep original text.
    df["_norm"] = (
        df["text"].astype(str)
        .str.lower()
        .str.strip()
        .str.replace(r"\s+", " ", regex=True)
    )
    df      = df.drop_duplicates(subset="_norm", keep="first").drop(columns=["_norm"])
    removed = original - len(df)
    log.info(f"Exact dedup: {original} → {len(df)} ({removed} removed)")
    return df.reset_index(drop=True), {"exact_removed": removed}


# ── Near-duplicate removal ─────────────────────────────────────────────────────

def remove_near_duplicates(df: pd.DataFrame, threshold: float) -> tuple[pd.DataFrame, dict]:
    """
    Greedy TF-IDF cosine clustering.

    Process documents sequentially. Each unassigned document starts a new cluster.
    Every subsequent unassigned document whose cosine similarity to the cluster head
    exceeds `threshold` is merged into that cluster.
    From each multi-member cluster, keep the longest text.

    This is O(n²) in the worst case but memory-efficient — only one similarity
    row is computed at a time (no full n×n matrix held in RAM).
    """
    original = len(df)
    if original < 2:
        return df, {"near_removed": 0, "clusters": original}

    log.info(f"Near-dedup (threshold={threshold}): vectorising {original} rows…")

    vectorizer = TfidfVectorizer(
        max_features=10_000,
        ngram_range=(1, 2),
        min_df=2,
        sublinear_tf=True,
        strip_accents="unicode",
        lowercase=True,
    )
    texts  = df["text"].astype(str).tolist()
    matrix = vectorizer.fit_transform(texts)
    log.info(f"TF-IDF matrix: {matrix.shape}")

    n             = matrix.shape[0]
    assigned      = [False] * n
    clusters: list[list[int]] = []

    for i in range(n):
        if assigned[i]:
            continue
        assigned[i] = True
        members     = [i]

        if i + 1 < n:
            sims = cosine_similarity(matrix[i : i + 1], matrix[i + 1 :])[0]
            for offset, sim in enumerate(sims):
                j = i + 1 + offset
                if not assigned[j] and sim >= threshold:
                    assigned[j] = True
                    members.append(j)

        clusters.append(members)

        if (i + 1) % 2_000 == 0:
            log.info(f"  Processed {i + 1}/{n} docs — {len(clusters)} clusters so far")

    # Keep the longest text from each cluster
    keep           = []
    multi_clusters = 0
    for members in clusters:
        if len(members) == 1:
            keep.append(members[0])
        else:
            multi_clusters += 1
            lengths = [len(str(df.iloc[idx]["text"])) for idx in members]
            keep.append(members[int(np.argmax(lengths))])

    df_out  = df.iloc[sorted(keep)].reset_index(drop=True)
    removed = original - len(df_out)
    log.info(
        f"Near-dedup: {original} → {len(df_out)} "
        f"({removed} removed, {multi_clusters} multi-member clusters)"
    )
    return df_out, {
        "near_removed":        removed,
        "total_clusters":      len(clusters),
        "multi_member_clusters": multi_clusters,
        "threshold":           threshold,
    }


# ── Main ───────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="V8 Phase 2: Deduplication")
    parser.add_argument("--input",     default=str(DEFAULT_INPUT),
                        help="Path to phase1_complete.csv")
    parser.add_argument("--output",    default=str(DEFAULT_OUTPUT))
    parser.add_argument("--threshold", type=float, default=DEFAULT_THRESHOLD,
                        help="Cosine similarity threshold for near-dedup (default: 0.85)")
    args = parser.parse_args()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    start = time.perf_counter()

    log.info(f"Loading: {args.input}")
    df = pd.read_csv(args.input)
    log.info(f"Loaded {len(df)} rows")

    if "text" not in df.columns:
        raise ValueError(
            f"Input CSV must have a 'text' column. Found: {list(df.columns)}"
        )

    initial   = len(df)
    all_stats: dict = {"initial_count": initial}

    df, short_removed = filter_short(df, MIN_TEXT_LENGTH)
    all_stats["short_removed"] = short_removed

    df, exact_stats = remove_exact_duplicates(df)
    all_stats.update(exact_stats)

    df, near_stats = remove_near_duplicates(df, args.threshold)
    all_stats.update(near_stats)

    total_removed = initial - len(df)
    all_stats.update({
        "final_count":       len(df),
        "total_removed":     total_removed,
        "total_removed_pct": round(total_removed / initial * 100, 2) if initial else 0,
        "elapsed_s":         round(time.perf_counter() - start, 1),
    })

    df.to_csv(args.output, index=False)
    with open(STATS_PATH, "w") as f:
        json.dump(all_stats, f, indent=2)

    log.info(f"\n{'='*55}")
    log.info(f"Phase 2 complete")
    log.info(f"  Initial  : {initial}")
    log.info(f"  Final    : {len(df)}")
    log.info(f"  Removed  : {total_removed} ({all_stats['total_removed_pct']}%)")
    log.info(f"  Saved    : {args.output}")
    log.info(f"  Stats    : {STATS_PATH}")

    if len(df) < 9_500:
        log.warning(
            f"  ⚠  Only {len(df)} rows remain after dedup. "
            f"Final dataset may fall below 9,500."
        )


if __name__ == "__main__":
    main()
