# priority_signature.py
import dspy
from dspy import InputField, OutputField

class PriorityDecision(dspy.Signature):
    text_sentiment = InputField(desc="Normalized text sentiment [-1,1]")
    audio_sentiment = InputField(desc="Normalized audio sentiment [-1,1]")
    urgency = InputField(desc="Urgency score [0,1]")
    department = InputField(desc="Complaint department")
    keywords = InputField(desc="Extracted keywords")

    priority = OutputField(desc="Integer priority score from 1 (lowest) to 5 (highest)")
