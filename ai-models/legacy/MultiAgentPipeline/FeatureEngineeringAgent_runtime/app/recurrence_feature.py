"""Recurrence feature for ticket creation.

Given a user and a new ticket text, mark the ticket as recurring when it is
similar enough to that user's past tickets.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from difflib import SequenceMatcher
from typing import List

import psycopg2
from psycopg2.extras import RealDictCursor


TOKEN_RE = re.compile(r"[a-z0-9]+")
DEFAULT_SIMILARITY_THRESHOLD = 0.62
DEFAULT_HISTORY_LIMIT = 50


def _normalize_text(text: str) -> List[str]:
    return TOKEN_RE.findall((text or "").lower())


def _cosine_similarity(tokens_a: List[str], tokens_b: List[str]) -> float:
    if not tokens_a or not tokens_b:
        return 0.0

    freq_a = Counter(tokens_a)
    freq_b = Counter(tokens_b)
    shared = set(freq_a.keys()) & set(freq_b.keys())
    dot = sum(freq_a[token] * freq_b[token] for token in shared)

    norm_a = math.sqrt(sum(value * value for value in freq_a.values()))
    norm_b = math.sqrt(sum(value * value for value in freq_b.values()))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def _similarity_score(text_a: str, text_b: str) -> float:
    tokens_a = _normalize_text(text_a)
    tokens_b = _normalize_text(text_b)
    bow_cosine = _cosine_similarity(tokens_a, tokens_b)
    seq_ratio = SequenceMatcher(None, text_a.lower(), text_b.lower()).ratio()
    return max(bow_cosine, seq_ratio)


def _fetch_user_ticket_texts(dsn: str, user_id: str, max_history: int) -> List[str]:
    with psycopg2.connect(dsn) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT subject, details
                FROM tickets
                WHERE created_by_user_id = %s
                ORDER BY created_at DESC
                LIMIT %s
                """,
                (user_id, max_history),
            )

            ticket_texts: List[str] = []
            for row in cur.fetchall():
                subject = (row.get("subject") or "").strip()
                details = (row.get("details") or "").strip()
                ticket_texts.append(f"{subject}\n{details}".strip())

            return ticket_texts


def compute_is_recurring_from_db(
    *,
    dsn: str,
    user_id: str,
    subject: str,
    details: str,
    threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
    max_history: int = DEFAULT_HISTORY_LIMIT,
) -> bool:
    """Compute `is_recurring` for a new ticket using same-user history."""
    incoming_text = f"{subject or ''}\n{details or ''}".strip()
    if not incoming_text:
        return False

    history = _fetch_user_ticket_texts(dsn=dsn, user_id=user_id, max_history=max_history)
    if not history:
        return False

    for historical_text in history:
        score = _similarity_score(incoming_text, historical_text)
        if score >= threshold:
            return True
    return False
