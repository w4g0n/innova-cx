#!/usr/bin/env python3
"""
Phase 4: Deduplicate generated/classified tickets.

This phase removes:
1. Exact duplicates (normalized transcript text)
2. Near duplicates (TF-IDF cosine similarity)

Default flow:
    input:  output/labeled.csv
    output: output/labeled_deduplicated.csv
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from tqdm import tqdm


def require_columns(df: pd.DataFrame, required: list[str]) -> None:
    missing = [column for column in required if column not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")


def normalize_text(value: str) -> str:
    text = str(value).lower().strip()
    text = re.sub(r"\s+", " ", text)
    return text


def remove_exact_duplicates(df: pd.DataFrame, text_column: str) -> tuple[pd.DataFrame, int]:
    working = df.copy()
    working["_normalized_text"] = working[text_column].astype(str).map(normalize_text)
    before = len(working)
    working = working.drop_duplicates(subset="_normalized_text", keep="first")
    working = working.drop(columns=["_normalized_text"]).reset_index(drop=True)
    removed = before - len(working)
    return working, removed


def remove_near_duplicates(
    df: pd.DataFrame,
    text_column: str,
    threshold: float,
) -> tuple[pd.DataFrame, int, int]:
    if len(df) == 0:
        return df.copy(), 0, 0

    transcripts = df[text_column].astype(str).tolist()
    vectorizer = TfidfVectorizer(
        max_features=10_000,
        ngram_range=(1, 2),
        min_df=2,
        sublinear_tf=True,
        strip_accents="unicode",
        lowercase=True,
    )
    tfidf = vectorizer.fit_transform(transcripts)

    cluster_labels = [-1] * len(df)
    clusters: list[list[int]] = []
    cluster_id = 0

    for i in tqdm(range(len(df)), desc="Phase 4 near-dedup"):
        if cluster_labels[i] != -1:
            continue

        cluster_labels[i] = cluster_id
        cluster_members = [i]

        if i + 1 < len(df):
            similarities = cosine_similarity(tfidf[i : i + 1], tfidf[i + 1 :])[0]
            for offset, sim in enumerate(similarities):
                j = i + 1 + offset
                if cluster_labels[j] == -1 and sim >= threshold:
                    cluster_labels[j] = cluster_id
                    cluster_members.append(j)

        clusters.append(cluster_members)
        cluster_id += 1

    keep_indices: list[int] = []
    multi_member_clusters = 0

    for cluster in clusters:
        if len(cluster) == 1:
            keep_indices.append(cluster[0])
            continue
        multi_member_clusters += 1
        lengths = [len(str(df.iloc[idx][text_column])) for idx in cluster]
        keep_indices.append(cluster[int(np.argmax(lengths))])

    result = df.iloc[sorted(keep_indices)].reset_index(drop=True)
    removed = len(df) - len(result)
    return result, removed, multi_member_clusters


def main() -> None:
    parser = argparse.ArgumentParser(description="Phase 4 deduplication (exact + near duplicates)")
    parser.add_argument("--input", default="output/labeled.csv", help="Input CSV path")
    parser.add_argument(
        "--output",
        default="output/labeled_deduplicated.csv",
        help="Output CSV path",
    )
    parser.add_argument(
        "--text-column",
        default="text",
        help="Column used for deduplication comparisons",
    )
    parser.add_argument(
        "--similarity-threshold",
        type=float,
        default=0.92,
        help="Cosine similarity threshold for near duplicates",
    )
    parser.add_argument(
        "--skip-exact",
        action="store_true",
        help="Skip exact duplicate pass and do near-duplicate pass only",
    )
    args = parser.parse_args()

    if not 0.5 <= args.similarity_threshold <= 0.99:
        raise ValueError("--similarity-threshold must be between 0.5 and 0.99")

    input_path = Path(args.input)
    output_path = Path(args.output)

    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")

    df = pd.read_csv(input_path)
    require_columns(df, [args.text_column])

    print(f"Loaded {len(df)} rows from: {input_path}")

    exact_removed = 0
    if not args.skip_exact:
        df, exact_removed = remove_exact_duplicates(df, args.text_column)
        print(f"Phase 4A exact duplicates removed: {exact_removed}")

    before_near = len(df)
    df, near_removed, multi_member_clusters = remove_near_duplicates(
        df,
        args.text_column,
        args.similarity_threshold,
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path, index=False)

    print(f"Phase 4B near duplicates removed: {near_removed}")
    print(f"Phase 4B multi-member clusters: {multi_member_clusters}")
    print(f"Rows before near-dedup: {before_near}")
    print(f"Final rows: {len(df)}")
    print(f"Saved deduplicated CSV to: {output_path}")


if __name__ == "__main__":
    main()
