"""
LangChain Pipeline
==================
Defines the full RunnableSequence that chains all agents in order.
Each step receives the full state dict and returns an updated state dict.
Every step is wrapped with execution logging that records input/output
as JSON to the database for explainability and analysis.

Flow:
    submitted ticket details (text + optional audio features)
        → [1] ClassificationAgent       (in-process heuristic; skip if type provided)
        → [2] AudioAnalysisAgent        (audio sentiment extraction)
        → [3] SentimentAgent            (text sentiment + keywords)
        → [4] SentimentCombinerAgent    (merge text + audio sentiment)
        → [5] FeatureEngineeringAgent   (RF models for impact/severity/urgency)
        → [6] PrioritizationAgent       (Fuzzy Logic priority scoring)
        → [7] DepartmentRoutingAgent    (create/update ticket via backend)
"""

from langchain_core.runnables import RunnableSequence

from agents.classifier.step import classify
from agents.audioanalysis.step import analyze_audio
from agents.sentimentanalysis.step import analyze_sentiment
from agents.sentimentcombiner.step import combine_sentiment
from agents.featureengineering.step import engineer_features
from agents.priority.step import score_priority
from agents.router.step import route_and_store

from execution_logger import logged_step

pipeline: RunnableSequence = (
    logged_step("ClassificationAgent",       classify,           1)
    | logged_step("AudioAnalysisAgent",      analyze_audio,      2)
    | logged_step("SentimentAgent",          analyze_sentiment,  3)
    | logged_step("SentimentCombinerAgent",  combine_sentiment,  4)
    | logged_step("FeatureEngineeringAgent", engineer_features,  5)
    | logged_step("PrioritizationAgent",     score_priority,     6)
    | logged_step("DepartmentRoutingAgent",  route_and_store,    7)
)
