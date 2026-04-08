"""
LangChain Pipeline
==================
Defines the full RunnableSequence that chains all agents in order.
Each step receives the full state dict and returns an updated state dict.
Execution logging is enabled when `execution_logger.logged_step` is available;
otherwise the pipeline falls back to the standard runnable wrappers.

Flow:
    submitted ticket details (text + optional audio features)
        -> [1] RecurrenceAgent / recurrence_step (CRITICAL)
            : similarity check; branches A/B/C cancel new ticket; branch D continues
        -> [2] SubjectGenerationAgent / subject_generation_step
            : generate subject when ticket subject is empty
        -> [3] ClassificationAgent / classifier_step
            : in-process heuristic; skip if type provided
        -> [4] SentimentAgent / sentiment_step
        -> [5] AudioAnalysisAgent / audio_analysis_step
            : complaint + audio ticket path
        -> [6] SentimentCombinerAgent / sentiment_combiner_step
        -> [7] FeatureEngineeringAgent / feature_engineering_step
        -> [8] PrioritizationAgent / priority_step (XGBoost/mock fallback)
        -> [9] _mark_routing_pending
            : signals ReviewAgent to perform department routing via Qwen
        -> [10] ReviewAgent / review_pipeline
            : quality gate — validates classification, features, priority,
              and performs department routing (replaces DepartmentRoutingAgent)
"""

from langchain_core.runnables import RunnableLambda, RunnableSequence

from agents.step01_recurrence.step import check_recurrence
from agents.step01_subjectgeneration.step import generate_subject
from agents.step03_classifier.step import classify
from agents.step04_sentimentanalysis.step import analyze_sentiment
from agents.step05_audioanalysis.step import analyze_audio
from agents.step06_sentimentcombiner.step import combine_sentiment
from agents.step08_featureengineering.step import engineer_features
from agents.step09_priority.step import score_priority
from agents.step11_reviewagent.step import review_pipeline

try:
    from execution_logger import logged_step
except Exception:  # pragma: no cover - optional dependency for backward compatibility
    logged_step = None


def _step(name: str, fn, order: int):
    if logged_step:
        return logged_step(name, fn, order)
    return RunnableLambda(fn)


async def _mark_routing_pending(state: dict) -> dict:
    """
    Injects department_routing_source = 'mock_fallback' so that ReviewAgent
    knows no upstream routing step ran and it must perform routing via Qwen.
    Only sets the flag if not already set by an upstream step.
    """
    if not state.get("department_routing_source"):
        state["department_routing_source"] = "mock_fallback"
        state["department_selected"] = state.get("department_selected") or "Unknown"
        state["department"] = state.get("department") or "Unknown"
        state["department_confidence"] = state.get("department_confidence") or 0.0
    return state


pipeline: RunnableSequence = (
    _step("RecurrenceAgent", check_recurrence, 1)
    | _step("SubjectGenerationAgent", generate_subject, 2)
    | _step("ClassificationAgent", classify, 3)
    | _step("SentimentAgent", analyze_sentiment, 4)
    | _step("AudioAnalysisAgent", analyze_audio, 5)
    | _step("SentimentCombinerAgent", combine_sentiment, 6)
    | _step("FeatureEngineeringAgent", engineer_features, 7)
    | _step("PrioritizationAgent", score_priority, 8)
    | _step("RoutingPendingMarker", _mark_routing_pending, 9)
    | _step("ReviewAgent", review_pipeline, 10)
)
