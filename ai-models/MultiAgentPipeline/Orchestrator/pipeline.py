"""
LangChain Pipeline
==================
Defines the full RunnableSequence that chains all agents in order.
Each step receives the full state dict and returns an updated state dict.
Execution logging is enabled when `execution_logger.logged_step` is available;
otherwise the pipeline falls back to the standard runnable wrappers.

Flow:
    submitted ticket details (text + optional audio features)
        -> [1] ClassificationAgent / classifier_step
            : in-process heuristic; skip if type provided
        -> [2] AudioAnalysisAgent / audio_analysis_step
            : complaint + audio ticket path
        -> [3] SentimentAgent / sentiment_step
        -> [4] SentimentCombinerAgent / sentiment_combiner_step
        -> [5] FeatureEngineeringAgent / feature_engineering_step
            : recurrence check then feature labeling/modeling
        -> [6] PrioritizationAgent / priority_step (Fuzzy Logic)
        -> [7] DepartmentRoutingAgent / router_step (Backend/Chatbot)
"""

from langchain_core.runnables import RunnableLambda, RunnableSequence

from agents.classifier.step import classify
from agents.audioanalysis.step import analyze_audio
from agents.sentimentanalysis.step import analyze_sentiment
from agents.sentimentcombiner.step import combine_sentiment
from agents.featureengineering.step import engineer_features
from agents.priority.step import score_priority
from agents.router.step import route_and_store

try:
    from execution_logger import logged_step
except Exception:  # pragma: no cover - optional dependency for backward compatibility
    logged_step = None


def _step(name: str, fn, order: int):
    if logged_step:
        return logged_step(name, fn, order)
    return RunnableLambda(fn)


pipeline: RunnableSequence = (
    _step("ClassificationAgent", classify, 1)
    | _step("AudioAnalysisAgent", analyze_audio, 2)
    | _step("SentimentAgent", analyze_sentiment, 3)
    | _step("SentimentCombinerAgent", combine_sentiment, 4)
    | _step("FeatureEngineeringAgent", engineer_features, 5)
    | _step("PrioritizationAgent", score_priority, 6)
    | _step("DepartmentRoutingAgent", route_and_store, 7)
)