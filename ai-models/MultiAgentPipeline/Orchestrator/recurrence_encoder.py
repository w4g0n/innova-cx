"""
Recurrence Encoder
==================
Transformer-based semantic similarity for the RecurrenceAgent.

Loads a sentence embedding model (default: sentence-transformers/all-MiniLM-L6-v2)
via HuggingFace transformers + torch. Mean-pools the last hidden state to produce
fixed-size embeddings, then scores candidates via cosine similarity.

Falls back to the heuristic _find_similar_ticket() from step01_recurrence if the model
cannot be loaded (no GPU required; model runs on CPU fine).

Environment variables:
  RECURRENCE_ENCODER_MODEL       HuggingFace model id or local path
                                 Default: sentence-transformers/all-MiniLM-L6-v2
  RECURRENCE_SIMILARITY_THRESHOLD Cosine threshold for a match (0-1)
                                 Default: 0.70
"""

from __future__ import annotations

import logging
import os
import threading
from pathlib import Path
from typing import Optional

_LOCAL_MODEL_PATH = str(Path(__file__).parent / "agents" / "step01_recurrence" / "model")
_SHARED_MODEL_PATH = "/app/models/recurrence/all-MiniLM-L6-v2"
_DEFAULT_HF_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"

logger = logging.getLogger(__name__)

RECURRENCE_ENCODER_MODEL: str = os.getenv(
    "RECURRENCE_ENCODER_MODEL",
    _SHARED_MODEL_PATH,
)
RECURRENCE_SIMILARITY_THRESHOLD: float = float(
    os.getenv("RECURRENCE_SIMILARITY_THRESHOLD", "0.70")
)

# Max candidates to pull from DB for comparison
_CANDIDATE_LIMIT = 200
# Max chars of details used per candidate when embedding
_DETAILS_TRUNCATE = 256


# ---------------------------------------------------------------------------
# Model singleton — retries on failure (no permanent None caching)
# ---------------------------------------------------------------------------

_encoder_lock: threading.Lock = threading.Lock()
_encoder_instance: Optional[dict] = None
_encoder_loaded: bool = False  # True only after a successful load


def _is_local_model_dir(path_str: str) -> bool:
    path = Path(path_str)
    if not path.is_dir():
        return False
    return (
        (path / "config.json").exists()
        and (path / "tokenizer_config.json").exists()
        and ((path / "tokenizer.json").exists() or (path / "vocab.txt").exists())
    )


def _resolve_model_name() -> str:
    """
    Prefer a stable host-mounted model path, then the repo-local path, then
    fall back to the upstream Hugging Face model id for manual recovery.
    """
    requested = RECURRENCE_ENCODER_MODEL.strip()
    if requested and _is_local_model_dir(requested):
        return requested

    if _is_local_model_dir(_SHARED_MODEL_PATH):
        logger.info("recurrence_encoder | using shared host model path %s", _SHARED_MODEL_PATH)
        return _SHARED_MODEL_PATH

    if requested and Path(requested).exists():
        logger.warning(
            "recurrence_encoder | requested local model path %s is incomplete; falling back",
            requested,
        )

    if _is_local_model_dir(_LOCAL_MODEL_PATH):
        logger.info("recurrence_encoder | using repo-local model path %s", _LOCAL_MODEL_PATH)
        return _LOCAL_MODEL_PATH

    logger.warning(
        "recurrence_encoder | no complete local model dir found; falling back to HF model id %s",
        _DEFAULT_HF_MODEL_NAME,
    )
    return _DEFAULT_HF_MODEL_NAME

def _load_encoder() -> Optional[dict]:
    """
    Load the tokenizer and model once on success; retry on failure.
    Returns None if unavailable.
    """
    global _encoder_instance, _encoder_loaded

    if _encoder_loaded:
        return _encoder_instance

    with _encoder_lock:
        if _encoder_loaded:
            return _encoder_instance

        model_name = _resolve_model_name()
        if not model_name:
            logger.info("recurrence_encoder | RECURRENCE_ENCODER_MODEL is empty — encoder disabled")
            return None
        try:
            import torch  # type: ignore
            from transformers import AutoTokenizer, AutoModel  # type: ignore

            logger.info("recurrence_encoder | loading model=%s", model_name)
            tokenizer = AutoTokenizer.from_pretrained(model_name)
            model = AutoModel.from_pretrained(model_name)
            model.eval()
            logger.info("recurrence_encoder | model loaded ok")
            _encoder_instance = {"tokenizer": tokenizer, "model": model, "torch": torch}
            _encoder_loaded = True
            return _encoder_instance
        except Exception as exc:
            logger.warning("recurrence_encoder | failed to load model (%s) — will retry next call", exc)
            return None


# ---------------------------------------------------------------------------
# Embedding helpers
# ---------------------------------------------------------------------------

def _mean_pool(last_hidden_state, attention_mask, torch):
    """Mean pool token embeddings, respecting the attention mask."""
    mask = attention_mask.unsqueeze(-1).expand(last_hidden_state.size()).float()
    summed = torch.sum(last_hidden_state * mask, dim=1)
    counts = torch.clamp(mask.sum(dim=1), min=1e-9)
    return summed / counts


def embed(texts: list[str]) -> Optional[object]:
    """
    Embed a list of strings. Returns a (N, dim) tensor or None if encoder unavailable.
    """
    enc = _load_encoder()
    if enc is None:
        return None
    tokenizer = enc["tokenizer"]
    model = enc["model"]
    torch = enc["torch"]
    try:
        encoded = tokenizer(
            texts,
            padding=True,
            truncation=True,
            max_length=128,
            return_tensors="pt",
        )
        with torch.no_grad():
            out = model(**encoded)
        return _mean_pool(out.last_hidden_state, encoded["attention_mask"], torch)
    except Exception as exc:
        logger.warning("recurrence_encoder | embed failed: %s", exc)
        return None


def cosine_sim(a, b, torch) -> float:
    """Cosine similarity between two 1-D tensors."""
    a_norm = a / torch.clamp(a.norm(), min=1e-9)
    b_norm = b / torch.clamp(b.norm(), min=1e-9)
    return float((a_norm * b_norm).sum())


# ---------------------------------------------------------------------------
# DB candidate fetch
# ---------------------------------------------------------------------------

def _fetch_candidates(
    current_ticket_code: Optional[str],
    created_by_user_id: Optional[str] = None,
) -> list[tuple[str, str, str]]:
    """
    Return list of (ticket_code, subject, details) for recent tickets
    belonging to the same user, excluding the current ticket.

    Only tickets that have actually progressed out of the intake/open state
    are eligible for recurrence matching. This prevents two brand-new queued
    tickets from matching each other before either has completed the pipeline.
    """
    try:
        from db import db_connect  # type: ignore
        with db_connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT ticket_code, subject, details
                    FROM tickets
                    WHERE (%s IS NULL OR ticket_code <> %s)
                      AND (%s IS NULL OR created_by_user_id = %s::uuid)
                      AND status NOT IN ('Open'::ticket_status, 'Linked'::ticket_status)
                      AND priority_assigned_at IS NOT NULL
                      AND EXISTS (
                          SELECT 1
                          FROM pipeline_stage_events pse
                          WHERE pse.ticket_code = tickets.ticket_code
                            AND pse.stage_name = 'ReviewAgent'
                            AND pse.step_order = 11
                            AND pse.event_type = 'output'
                            AND pse.status = 'success'
                      )
                    ORDER BY created_at DESC
                    LIMIT %s
                    """,
                    (
                        current_ticket_code, current_ticket_code,
                        created_by_user_id, created_by_user_id,
                        _CANDIDATE_LIMIT,
                    ),
                )
                return cur.fetchall() or []
    except Exception as exc:
        logger.warning("recurrence_encoder | candidate fetch failed: %s", exc)
        return []


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def encoder_is_available() -> bool:
    """Return True if the transformer model loaded successfully."""
    return _load_encoder() is not None


def find_similar_ticket(
    text: str,
    current_ticket_code: Optional[str] = None,
    created_by_user_id: Optional[str] = None,
) -> tuple[Optional[str], Optional[str], float]:
    """
    Find the most semantically similar prior ticket using transformer embeddings.
    Only considers tickets submitted by the same user (created_by_user_id).
    Falls back to the heuristic from step01_recurrence if the model isn't loaded.

    Returns:
        (matched_ticket_code, matched_subject, cosine_score)
        Returns (None, None, 0.0) when no match exceeds the threshold.
    """
    query_text = str(text or "").strip()
    if not query_text:
        return None, None, 0.0

    enc = _load_encoder()

    # --- Transformer path ---
    if enc is not None:
        torch = enc["torch"]
        candidates = _fetch_candidates(current_ticket_code, created_by_user_id)
        if not candidates:
            return None, None, 0.0

        candidate_texts = [
            f"{row[1] or ''} {(row[2] or '')[:_DETAILS_TRUNCATE]}".strip()
            for row in candidates
        ]

        all_texts = [query_text] + candidate_texts
        embeddings = embed(all_texts)
        if embeddings is not None:
            query_vec = embeddings[0]
            best_code: Optional[str] = None
            best_subject: Optional[str] = None
            best_score: float = 0.0

            for i, row in enumerate(candidates):
                code = str(row[0] or "").strip()
                subject = str(row[1] or "").strip()
                if not code:
                    continue
                score = cosine_sim(query_vec, embeddings[i + 1], torch)
                if score > best_score:
                    best_score = score
                    best_code = code
                    best_subject = subject

            if best_score >= RECURRENCE_SIMILARITY_THRESHOLD:
                logger.info(
                    "recurrence_encoder | transformer match code=%s score=%.3f",
                    best_code, best_score,
                )
                return best_code, best_subject, best_score

            logger.info(
                "recurrence_encoder | no match above threshold (best=%.3f threshold=%.2f)",
                best_score, RECURRENCE_SIMILARITY_THRESHOLD,
            )
            return None, None, best_score
        # embed failed mid-way — fall through to heuristic

    # --- Heuristic fallback ---
    logger.info("recurrence_encoder | using heuristic fallback (encoder not loaded)")
    try:
        from agents.step01_recurrence.step import (  # type: ignore
            _find_similar_ticket as _heuristic,
            SIMILARITY_RECURRENCE_THRESHOLD,
        )
        code, subject, score = _heuristic(query_text, current_ticket_code, created_by_user_id)
        if score >= SIMILARITY_RECURRENCE_THRESHOLD:
            return code, subject, score
        return None, None, score
    except Exception as exc:
        logger.warning("recurrence_encoder | heuristic fallback also failed: %s", exc)
        return None, None, 0.0
