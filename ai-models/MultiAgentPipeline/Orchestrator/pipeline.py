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
        -> [9] DepartmentRoutingAgent / router_step
        -> [10] SuggestedResolutionAgent / suggested_resolution_step
            : final-context complaint suggestion or inquiry KB answer
        -> [11] ReviewAgent / review_pipeline
"""

from langchain_core.runnables import RunnableLambda, RunnableSequence

from agents.step01_subjectgeneration.step import generate_subject
from agents.step02_suggestedresolution.step import generate_suggested_resolution
from agents.step03_classifier.step import classify
from agents.step04_sentimentanalysis.step import analyze_sentiment
from agents.step05_audioanalysis.step import analyze_audio
from agents.step06_sentimentcombiner.step import combine_sentiment
from agents.step01_recurrence.step import check_recurrence
from agents.step08_featureengineering.step import engineer_features
from agents.step09_priority.step import score_priority
from agents.step10_router.step import route_and_store
from agents.step11_reviewagent.step import review_pipeline

try:
    from execution_logger import logged_step
except Exception:  # pragma: no cover - optional dependency for backward compatibility
    logged_step = None


def _step(name: str, fn, order: int):
    if logged_step:
        return logged_step(name, fn, order)
    return RunnableLambda(fn)


pipeline: RunnableSequence = (
    _step("RecurrenceAgent", check_recurrence, 1)
    | _step("SubjectGenerationAgent", generate_subject, 2)
    | _step("ClassificationAgent", classify, 3)
    | _step("SentimentAgent", analyze_sentiment, 4)
    | _step("AudioAnalysisAgent", analyze_audio, 5)
    | _step("SentimentCombinerAgent", combine_sentiment, 6)
    | _step("FeatureEngineeringAgent", engineer_features, 7)
    | _step("PrioritizationAgent", score_priority, 8)
    | _step("DepartmentRoutingAgent", route_and_store, 9)
    | _step("SuggestedResolutionAgent", generate_suggested_resolution, 10)
    | _step("ReviewAgent", review_pipeline, 11)
)
