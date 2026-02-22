"""
LangChain Pipeline
==================
Defines the full RunnableSequence that chains all agents in order.
Each step receives the full state dict and returns an updated state dict.

Flow:
    audio/text input
        → [1] transcriber_step   (Whisper, port 3001)
        → [2] classifier_step    (DistilRoBERTa, port 8003)
        → (complaint) [3] sentiment_step  (RoBERTa, port 8002)
        → (complaint) [4] audio_analysis_step
        → (complaint) [5] priority_step   (DSPy)
        → [6] router_step        (Backend/Chatbot)
"""

from langchain_core.runnables import RunnableSequence

from agents.transcriber import transcriber_step
from agents.classifier import classifier_step
from agents.sentiment import sentiment_step
from agents.audio_analysis import audio_analysis_step
from agents.priority import priority_step
from agents.router import router_step

pipeline: RunnableSequence = (
    transcriber_step
    | classifier_step
    | sentiment_step
    | audio_analysis_step
    | priority_step
    | router_step
)
