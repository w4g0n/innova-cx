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
from dspy.utils import DummyLM  # noqa: E402
from langchain_core.runnables import RunnableLambda  # noqa: E402
from signals import build_priority_signals  # noqa: E402
from priority_signature import PriorityDecision  # noqa: E402

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# DSPy configuration — matches project convention in ai-models/DSPY/runPriority.py
# DummyLM returns the configured answer for every call.
# Replace with a real LM for production priority scoring.
# ---------------------------------------------------------------------------
dspy.settings.configure(lm=DummyLM(answers={"priority": "3"}))

predictor = dspy.Predict(PriorityDecision)


def _safe_priority(value) -> int:
    """Convert DSPy output to a valid int in [1, 5], default 3 on any error."""
    try:
        p = int(str(value).strip())
        return max(1, min(5, p))
    except (TypeError, ValueError, AttributeError):
        return 3


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

    try:
        result = predictor(
            text_sentiment=signals.text_sentiment,
            audio_sentiment=signals.audio_sentiment,
            urgency=signals.urgency,
            department=signals.department,
            keywords=signals.keywords,
        )
        state["priority_score"] = _safe_priority(result.priority)
    except Exception as exc:
        logger.warning("DSPy predictor failed (%s) — defaulting priority to 3", exc)
        state["priority_score"] = 3

    return state


priority_step = RunnableLambda(score_priority)
