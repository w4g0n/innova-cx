"""
Shared feature extractor for the classifier pipeline.

Defined here (not in train_classifier.py) so that joblib-pickled Pipelines
can be unpickled in the subprocess runtime worker without a module-not-found
error. Both train_classifier.py and classifier_runtime_worker.py import from
this module.
"""
from sklearn.base import BaseEstimator, TransformerMixin
import numpy as np

_QUESTION_STARTS = frozenset({
    "how", "what", "where", "when", "why", "who", "which",
    "can", "could", "would", "is", "are", "do", "does",
    "will", "should", "may", "might", "has", "have",
})

_COMPLAINT_KWS = [
    "broken", "not working", "doesn't work", "wont work", "won't work",
    "stopped working", "broke down", "out of order",
    "outage", "power cut", "no power", "no electricity",
    "leak", "leaking", "flooding", "flood",
    "fault", "faulty", "defect",
    "issue", "problem", "trouble", "error", "failed", "failure",
    "damaged", "damage",
    "urgent", "emergency", "unacceptable",
    "frustrated", "angry", "disgusted",
    "cannot", "can't", "unable",
    "still not", "not resolved", "not fixed",
]

_INQUIRY_KWS = [
    "how do i", "how can i", "how to",
    "what is", "what are", "what's",
    "where is", "where can i",
    "when is", "when will", "when can",
    "can you", "could you", "would you",
    "please let me know", "please advise", "please help",
    "information", "details", "guide", "procedure", "process",
    "policy", "schedule", "hours", "opening hours",
    "fee", "cost", "price", "charge",
    "deadline", "requirement", "eligibility",
    "how does", "how should",
    "let me know", "wondering", "inquiry",
]


class LinguisticFeatureExtractor(BaseEstimator, TransformerMixin):
    """Extracts hand-crafted linguistic features from raw text strings."""

    def fit(self, X, y=None):
        return self

    def transform(self, X):
        rows = []
        for text in X:
            t = str(text or "").strip().lower()
            words = t.split()
            first = words[0] if words else ""

            rows.append([
                1.0 if "?" in t else 0.0,
                1.0 if first in _QUESTION_STARTS else 0.0,
                float(sum(1 for w in words if w.rstrip(".,;:!?") in _QUESTION_STARTS)),
                float(sum(1 for kw in _COMPLAINT_KWS if kw in t)),
                float(sum(1 for kw in _INQUIRY_KWS if kw in t)),
                min(float(len(words)) / 50.0, 1.0),   # cap at 1.0
            ])
        return np.array(rows, dtype=np.float32)
