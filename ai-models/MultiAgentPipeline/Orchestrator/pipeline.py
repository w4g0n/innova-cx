"""
LangChain Pipeline
==================
Defines the full RunnableSequence that chains all agents in order.
Each step receives the full state dict and returns an updated state dict.
Execution logging is enabled when `execution_logger.logged_step` is available;
otherwise the pipeline falls back to the standard runnable wrappers.

Flow:
    submitted ticket details (text + optional audio features)
        -> [2] SubjectGenerationAgent / subject_generation_step
            : generate subject when ticket subject is empty
        -> [3] SuggestedResolutionAgent / suggested_resolution_step
        -> [4] ClassificationAgent / classifier_step
            : in-process heuristic; skip if type provided
        -> [5] SentimentAgent / sentiment_step
        -> [6] AudioAnalysisAgent / audio_analysis_step
            : complaint + audio ticket path
        -> [7] SentimentCombinerAgent / sentiment_combiner_step
        -> [8] RecurrenceAgent / recurrence_step
        -> [9] FeatureEngineeringAgent / feature_engineering_step
        -> [10] PrioritizationAgent / priority_step (XGBoost/mock fallback)
        -> [11] DepartmentRoutingAgent / router_step
"""

from langchain_core.runnables import RunnableLambda, RunnableSequence

from agents.step01_subjectgeneration.step import generate_subject
from agents.step02_suggestedresolution.step import generate_suggested_resolution
from agents.step03_classifier.step import classify
from agents.step04_sentimentanalysis.step import analyze_sentiment
from agents.step05_audioanalysis.step import analyze_audio
from agents.step06_sentimentcombiner.step import combine_sentiment
from agents.step07_recurrence.step import check_recurrence
from agents.step08_featureengineering.step import engineer_features
from agents.step09_priority.step import score_priority
from agents.step10_router.step import route_and_store

try:
    from execution_logger import logged_step
except Exception:  # pragma: no cover - optional dependency for backward compatibility
    logged_step = None


def _step(name: str, fn, order: int):
    if logged_step:
        return logged_step(name, fn, order)
    return RunnableLambda(fn)


pipeline: RunnableSequence = (
    _step("SubjectGenerationAgent", generate_subject, 2)
    | _step("SuggestedResolutionAgent", generate_suggested_resolution, 3)
    | _step("ClassificationAgent", classify, 4)
    | _step("SentimentAgent", analyze_sentiment, 5)
    | _step("AudioAnalysisAgent", analyze_audio, 6)
    | _step("SentimentCombinerAgent", combine_sentiment, 7)
    | _step("RecurrenceAgent", check_recurrence, 8)
    | _step("FeatureEngineeringAgent", engineer_features, 9)
    | _step("PrioritizationAgent", score_priority, 10)
    | _step("DepartmentRoutingAgent", route_and_store, 11)
)
