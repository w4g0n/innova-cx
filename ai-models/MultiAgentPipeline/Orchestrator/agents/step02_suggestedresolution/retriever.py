from pathlib import Path

import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

DATA_PATH = Path(__file__).parent / "data" / "knowledge_base.csv"
TEXT_COL = "transcript"
CATEGORY_COL = "call_category"

INQUIRY_LABEL = "leasing inquiry"
COMPLAINT_LABEL = "support"

_df = pd.read_csv(DATA_PATH)
_df[TEXT_COL] = _df[TEXT_COL].fillna("").astype(str)
_df[CATEGORY_COL] = _df[CATEGORY_COL].fillna("").astype(str)

_inquiry_df = _df[_df[CATEGORY_COL].str.lower() == INQUIRY_LABEL]
_complaint_df = _df[_df[CATEGORY_COL].str.lower() == COMPLAINT_LABEL]


def _retrieve_top_k(query: str, df: pd.DataFrame, k: int = 3) -> list[str]:
    if df.empty:
        return []

    texts = df[TEXT_COL].tolist()
    vectorizer = TfidfVectorizer(stop_words="english")
    tfidf_matrix = vectorizer.fit_transform(texts + [query])
    similarities = cosine_similarity(tfidf_matrix[-1], tfidf_matrix[:-1]).flatten()
    top_indices = similarities.argsort()[-k:][::-1]
    return [texts[i] for i in top_indices]


def retrieve_context(query: str, mode: str, k: int = 3) -> str:
    if mode == "inquiry":
        chunks = _retrieve_top_k(query, _inquiry_df, k)
    elif mode == "complaint":
        chunks = _retrieve_top_k(query, _complaint_df, k)
    else:
        chunks = []

    if not chunks:
        return ""

    return "\n\n".join(f"- {chunk}" for chunk in chunks)
