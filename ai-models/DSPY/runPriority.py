# run_priority.py
import dspy
from dspy.utils import DummyLM

from signals import build_priority_signals
from priority_signature import PriorityDecision

dspy.settings.configure(
    lm=DummyLM(answers={"priority": {"priority": "high"}})
)

predictor = dspy.Predict(PriorityDecision)

signals = build_priority_signals(
    text_sentiment_raw=-0.9,
    audio_sentiment_raw=-0.8,
    urgency_raw=0.9,
    department="maintenance",
    keywords=["water leak", "ceiling damage"]
)

result = predictor(
    text_sentiment=signals.text_sentiment,
    audio_sentiment=signals.audio_sentiment,
    urgency=signals.urgency,
    department=signals.department,
    keywords=signals.keywords
)

print(result.priority)