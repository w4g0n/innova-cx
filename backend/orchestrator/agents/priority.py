"""
Step 5 — DSPy Priority Scoring
================================
Uses DSPy + DummyLM to score complaint priority from 1 (lowest) to 5 (highest).
Only runs for the complaint path.

In production, swap DummyLM for a real LM (e.g. dspy.LM("openai/gpt-4o-mini")).
"""

import sys
import logging

# Must be first so that local DSPy files are importable
sys.path.insert(0, "/app/dspy")

import dspy  # noqa: E402
from langchain_core.runnables import RunnableLambda  # noqa: E402
from signals import build_priority_signals  # noqa: E402
from priority_signature import PriorityDecision  # noqa: E402

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# DSPy configuration
# DummyLM always returns the configured answers — replace for production.
# ---------------------------------------------------------------------------
try:
    dummy_lm = dspy.utils.DummyLM([{"priority": "3"}])
    dspy.configure(lm=dummy_lm)
except Exception as exc:
    logger.warning("Could not configure DSPy DummyLM: %s", exc)

predictor = dspy.Predict(PriorityDecision)


def _safe_priority(value) -> int:
    """Convert DSPy output to a valid int in [1, 5]."""
    try:
        p = int(value)
        return max(1, min(5, p))
    except (TypeError, ValueError):
        return 3  # Default mid-priority


async def score_priority(state: dict) -> dict:
    """
    Builds PrioritySignals from the state, runs DSPy predictor,
    and stores result in state["priority_score"].

    Only runs for the complaint path.
    """
    if state["label"] != "complaint":
        return state

    signals = build_priority_signals(
        text_sentiment_raw=state.get("text_sentiment", 0.0),
        audio_sentiment_raw=state.get("audio_sentiment", 0.0),
        urgency_raw=state.get("urgency", 0.5),
        department=state.get("department", "general"),
        keywords=state.get("keywords", []),
    )

    result = predictor(
        text_sentiment=signals.text_sentiment,
        audio_sentiment=signals.audio_sentiment,
        urgency=signals.urgency,
        department=signals.department,
        keywords=signals.keywords,
    )

    state["priority_score"] = _safe_priority(result.priority)
    return state


priority_step = RunnableLambda(score_priority)
