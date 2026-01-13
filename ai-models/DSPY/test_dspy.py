import dspy
from dspy.utils import DummyLM
from dspy import InputField, OutputField

print("DSPy installed:", dspy.__version__)

dummy_answers = {
    "priority": {
        "priority": "high"
    }
}

dspy.settings.configure(lm=DummyLM(answers=dummy_answers))


class PriorityDecision(dspy.Signature):
    text_sentiment = InputField()
    audio_sentiment = InputField()
    urgency = InputField()
    department = InputField()
    keywords = InputField()
    priority = OutputField()


predictor = dspy.Predict(PriorityDecision)

tests = [
    {
        "text_sentiment": -0.9,
        "audio_sentiment": -0.8,
        "urgency": 0.9,
        "department": "maintenance",
        "keywords": "water leak, ceiling damage"
    },
    {
        "text_sentiment": -0.7,
        "audio_sentiment": -0.9,
        "urgency": 0.2,
        "department": "customer service",
        "keywords": "rude staff, bad attitude"
    },
    {
        "text_sentiment": -0.1,
        "audio_sentiment": 0.0,
        "urgency": 0.8,
        "department": "billing",
        "keywords": "overcharged invoice"
    }
]

for t in tests:
    result = predictor(**t)
    print(t["department"], "→", result.priority)
