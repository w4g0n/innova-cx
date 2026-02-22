"""
LangChain Pipeline
==================
Defines the full RunnableSequence that chains all agents in order.
Each step receives the full state dict and returns an updated state dict.

Flow:
    submitted ticket details (text + optional audio features)
        → [1] classifier_step    (DistilRoBERTa, port 8003; skip if type provided)
        → (complaint + audio ticket) [2] audio_analysis_step (audioanalysis module)
        → (complaint) [3] sentiment_step  (sentimentanalysis module)
        → (complaint) [4] sentiment_combiner_step (sentimentcombiner module)
        → (complaint) [5] feature_engineering_step
        → (complaint) [6] priority_step   (Fuzzy Logic)
        → [7] router_step        (Backend/Chatbot)
"""

from langchain_core.runnables import RunnableSequence

from agents.classifier.step import classifier_step
from agents.audioanalysis.step import audio_analysis_step
from agents.sentimentanalysis.step import sentiment_step
from agents.sentimentcombiner.step import sentiment_combiner_step
from agents.featureengineering.step import feature_engineering_step
from agents.priority.step import priority_step
from agents.router.step import router_step

pipeline: RunnableSequence = (
    classifier_step
    | audio_analysis_step
    | sentiment_step
    | sentiment_combiner_step
    | feature_engineering_step
    | priority_step
    | router_step
)
