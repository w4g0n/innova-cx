"""
Unit tests for the Sentiment Combiner Agent.

Run from the Orchestrator directory:
    python -m pytest agents/step06_sentimentcombiner/test_combiner.py -v
"""
import asyncio
import os
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock

import pytest

# Stub langchain_core so the module loads without the full orchestrator stack
_lc_stub = types.ModuleType("langchain_core")
_lc_runnables = types.ModuleType("langchain_core.runnables")
_lc_runnables.RunnableLambda = MagicMock(side_effect=lambda f: f)
_lc_stub.runnables = _lc_runnables
sys.modules.setdefault("langchain_core", _lc_stub)
sys.modules.setdefault("langchain_core.runnables", _lc_runnables)

# Ensure the combiner module is importable
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

# Allow overriding thresholds via env before import
os.environ.setdefault("SENTIMENT_BUCKET_NEG_THRESHOLD", "-0.15")
os.environ.setdefault("SENTIMENT_BUCKET_POS_THRESHOLD", "0.15")

from agents.step06_sentimentcombiner.step import combine_sentiment, _bucket, _normalize_unit  # noqa: E402


def run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


# ── _normalize_unit ────────────────────────────────────────────────────────────

def test_normalize_clamps_above_one():
    assert _normalize_unit(2.5) == 1.0

def test_normalize_clamps_below_neg_one():
    assert _normalize_unit(-3.0) == -1.0

def test_normalize_none_returns_zero():
    assert _normalize_unit(None) == 0.0

def test_normalize_passthrough():
    assert _normalize_unit(0.5) == pytest.approx(0.5)


# ── _bucket ────────────────────────────────────────────────────────────────────

def test_bucket_negative():
    assert _bucket(-0.5) == "negative"

def test_bucket_positive():
    assert _bucket(0.5) == "positive"

def test_bucket_neutral_zero():
    assert _bucket(0.0) == "neutral"

def test_bucket_boundary_neg():
    # exactly at threshold → neutral
    assert _bucket(-0.15) == "neutral"

def test_bucket_just_below_neg_threshold():
    assert _bucket(-0.16) == "negative"

def test_bucket_boundary_pos():
    assert _bucket(0.15) == "neutral"

def test_bucket_just_above_pos_threshold():
    assert _bucket(0.16) == "positive"


# ── combine_sentiment — text only ─────────────────────────────────────────────

def test_text_only_no_audio():
    state = {"text_sentiment": 0.6, "has_audio": False}
    result = run(combine_sentiment(state))
    assert result["sentiment_score_numeric"] == pytest.approx(0.6)
    assert result["sentiment_score"] == "positive"
    assert result["sentiment_combiner_mode"] == "text_only"

def test_text_only_audio_none():
    state = {"text_sentiment": -0.5, "has_audio": True, "audio_sentiment": None}
    result = run(combine_sentiment(state))
    assert result["sentiment_combiner_mode"] == "text_only"
    assert result["sentiment_score_numeric"] == pytest.approx(-0.5)

def test_text_only_negative_bucket():
    state = {"text_sentiment": -0.4, "has_audio": False}
    result = run(combine_sentiment(state))
    assert result["sentiment_score"] == "negative"

def test_text_only_neutral_bucket():
    state = {"text_sentiment": 0.05, "has_audio": False}
    result = run(combine_sentiment(state))
    assert result["sentiment_score"] == "neutral"


# ── combine_sentiment — text + good audio ─────────────────────────────────────

def test_audio_with_high_quality_weights_audio_more():
    # audio_score=1.0 → audio_weight=0.5, text_weight=0.5
    state = {
        "text_sentiment": 0.8,
        "has_audio": True,
        "audio_sentiment": -0.8,
        "audio_score": 1.0,
    }
    result = run(combine_sentiment(state))
    expected = 0.5 * 0.8 + 0.5 * (-0.8)
    assert result["sentiment_score_numeric"] == pytest.approx(expected, abs=1e-4)
    assert result["sentiment_combiner_mode"] == "text_audio_quality_weighted"

def test_audio_with_mid_quality():
    # audio_score=0.5 → audio_weight=0.25, text_weight=0.75
    state = {
        "text_sentiment": 0.6,
        "has_audio": True,
        "audio_sentiment": -0.4,
        "audio_score": 0.5,
    }
    result = run(combine_sentiment(state))
    expected = 0.75 * 0.6 + 0.25 * (-0.4)
    assert result["sentiment_score_numeric"] == pytest.approx(expected, abs=1e-4)

def test_audio_with_zero_quality_text_dominates():
    # audio_score=0.0 → audio_weight=0.0, text_weight=1.0
    state = {
        "text_sentiment": 0.7,
        "has_audio": True,
        "audio_sentiment": -0.9,
        "audio_score": 0.0,
    }
    result = run(combine_sentiment(state))
    assert result["sentiment_score_numeric"] == pytest.approx(0.7, abs=1e-4)


# ── combine_sentiment — text + audio without quality score ────────────────────

def test_audio_no_quality_falls_back_to_70_30():
    # no audio_score → 70/30 text-dominant
    state = {
        "text_sentiment": 1.0,
        "has_audio": True,
        "audio_sentiment": -1.0,
    }
    result = run(combine_sentiment(state))
    expected = 0.7 * 1.0 + 0.3 * (-1.0)
    assert result["sentiment_score_numeric"] == pytest.approx(expected, abs=1e-4)
    assert result["sentiment_combiner_mode"] == "text_audio_default_weighted"


# ── combine_sentiment — display score ─────────────────────────────────────────

def test_display_score_positive_one():
    state = {"text_sentiment": 1.0, "has_audio": False}
    result = run(combine_sentiment(state))
    assert result["sentiment_score_display"] == pytest.approx(1.0)

def test_display_score_negative_one():
    state = {"text_sentiment": -1.0, "has_audio": False}
    result = run(combine_sentiment(state))
    assert result["sentiment_score_display"] == pytest.approx(0.0)

def test_display_score_zero():
    state = {"text_sentiment": 0.0, "has_audio": False}
    result = run(combine_sentiment(state))
    assert result["sentiment_score_display"] == pytest.approx(0.5)


# ── combine_sentiment — out-of-range inputs ───────────────────────────────────

def test_out_of_range_text_clamped():
    state = {"text_sentiment": 3.0, "has_audio": False}
    result = run(combine_sentiment(state))
    assert result["sentiment_score_numeric"] == pytest.approx(1.0)

def test_out_of_range_audio_clamped():
    state = {
        "text_sentiment": 0.5,
        "has_audio": True,
        "audio_sentiment": 99.0,
        "audio_score": 1.0,
    }
    result = run(combine_sentiment(state))
    # audio clamped to 1.0: 0.5*0.5 + 0.5*1.0 = 0.75
    assert result["sentiment_score_numeric"] == pytest.approx(0.75, abs=1e-4)

def test_missing_text_sentiment_defaults_zero():
    state = {"has_audio": False}
    result = run(combine_sentiment(state))
    assert result["sentiment_score_numeric"] == pytest.approx(0.0)
