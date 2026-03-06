import pandas as pd
from pathlib import Path
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import re

# ---- config ----
DATA_PATH = Path(__file__).parent / "data" / "knowledge_base.csv"
TEXT_COL = "transcript"
KB_TEXT_COL = "kb_text"
CATEGORY_COL = "call_category"

INQUIRY_LABEL = "leasing inquiry"
COMPLAINT_LABEL = "support"

# ---- load once ----
_df = pd.read_csv(DATA_PATH)

# basic cleanup
_df[TEXT_COL] = _df[TEXT_COL].fillna("").astype(str)
_df[CATEGORY_COL] = _df[CATEGORY_COL].fillna("").astype(str)


_BOILERPLATE_PATTERNS = [
    r"^agent:\s*industrial park (support|leasing) desk,?.*",
    r"^agent:\s*how may i assist\??",
    r"^agent:\s*may i have your unit information\??",
    r"^agent:\s*i can include all those details in the proposal\.?$",
    r"^agent:\s*you'?re welcome.*",
]

_SIGNAL_TERMS = (
    "rent", "rate", "price", "pricing", "cost", "quote", "proposal",
    "availability", "available", "move in", "parking", "viewing",
    "lease", "terms", "floor plan", "size requirement", "square feet",
    "escalating", "high priority", "on-site", "within the hour",
)


def _normalize_line(line: str) -> str:
    line = re.sub(r"\s+", " ", line).strip()
    return line


def _is_boilerplate(line: str) -> bool:
    low = line.lower()
    return any(re.match(p, low) for p in _BOILERPLATE_PATTERNS)


def _to_kb_text(transcript: str) -> str:
    """
    Convert raw transcript into compact retrieval text by removing greetings
    and prioritizing informative lines.
    """
    if not transcript:
        return ""

    lines = [_normalize_line(x) for x in str(transcript).splitlines() if _normalize_line(x)]
    if not lines:
        return ""

    cleaned = []
    for line in lines:
        if _is_boilerplate(line):
            continue
        cleaned.append(line)

    if not cleaned:
        cleaned = lines[:]

    signal_lines = []
    for line in cleaned:
        low = line.lower()
        if any(term in low for term in _SIGNAL_TERMS):
            signal_lines.append(line)

    picked = signal_lines[:4] if signal_lines else cleaned[:4]

    # Strip speaker labels so responses do not echo transcript formatting.
    final_lines = [re.sub(r"^(agent|tenant|caller):\s*", "", ln, flags=re.IGNORECASE) for ln in picked]
    return " ".join(final_lines).strip()


_df[KB_TEXT_COL] = _df[TEXT_COL].apply(_to_kb_text)

# split by type
_inquiry_df = _df[_df[CATEGORY_COL].str.lower() == INQUIRY_LABEL]
_complaint_df = _df[_df[CATEGORY_COL].str.lower() == COMPLAINT_LABEL]


def _retrieve_top_k(query: str, df: pd.DataFrame, k: int = 3) -> list[str]:
    """
    Return top-k most relevant text chunks using TF-IDF cosine similarity.
    """
    if df.empty:
        return []

    texts = df[KB_TEXT_COL].fillna("").astype(str).tolist()
    texts = [t for t in texts if t.strip()]
    if not texts:
        return []

    vectorizer = TfidfVectorizer(stop_words="english")
    tfidf_matrix = vectorizer.fit_transform(texts + [query])

    similarities = cosine_similarity(
        tfidf_matrix[-1],
        tfidf_matrix[:-1]
    ).flatten()

    top_indices = similarities.argsort()[-k:][::-1]
    return [texts[i] for i in top_indices]


def retrieve_context(query: str, mode: str, k: int = 3) -> str:
    """
    Public API.
    Returns a single string to inject into the prompt.
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
