"""
Local TF-IDF retriever for the SuggestedResolutionAgent.
Searches knowledge_base.csv for the k most relevant call transcripts
and returns them as a single formatted context string.

This is self-contained — does NOT import from the chatbot service.
"""

import pandas as pd
from pathlib import Path
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
DATA_PATH = Path(__file__).parent / "data" / "knowledge_base.csv"
TEXT_COL = "transcript"
CATEGORY_COL = "call_category"

INQUIRY_LABEL = "leasing inquiry"
COMPLAINT_LABEL = "support"

# ---------------------------------------------------------------------------
# Load & split once at import time
# ---------------------------------------------------------------------------
_df = pd.read_csv(DATA_PATH)
_df[TEXT_COL] = _df[TEXT_COL].fillna("").astype(str)
_df[CATEGORY_COL] = _df[CATEGORY_COL].fillna("").astype(str)

_inquiry_df = _df[_df[CATEGORY_COL].str.lower() == INQUIRY_LABEL]
_complaint_df = _df[_df[CATEGORY_COL].str.lower() == COMPLAINT_LABEL]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _retrieve_top_k(query: str, df: pd.DataFrame, k: int = 3) -> list[str]:
    """Return the k most relevant transcript chunks via TF-IDF cosine similarity."""
    if df.empty:
        return []
    texts = df[TEXT_COL].tolist()
    vectorizer = TfidfVectorizer(stop_words="english")
    tfidf_matrix = vectorizer.fit_transform(texts + [query])
    similarities = cosine_similarity(
        tfidf_matrix[-1],
        tfidf_matrix[:-1],
    ).flatten()
    top_indices = similarities.argsort()[-k:][::-1]
    return [texts[i] for i in top_indices]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def retrieve_context(query: str, mode: str, k: int = 3) -> str:
    """
    Return a single formatted context string for prompt injection.

    Args:
        query: Ticket text to match against.
        mode:  "inquiry" or "complaint".
        k:     Number of results to return (default 3).
    """
    if mode == "inquiry":
        chunks = _retrieve_top_k(query, _inquiry_df, k)
    elif mode == "complaint":
        chunks = _retrieve_top_k(query, _complaint_df, k)
    else:
        chunks = []

    if not chunks:
        return ""

    return "\n\n".join(f"- {chunk}" for chunk in chunks)
