# signals.py
from dataclasses import dataclass
from typing import List

@dataclass
class PrioritySignals:
    text_sentiment: float
    audio_sentiment: float
    urgency: float
    department: str
    keywords: List[str]


def clamp(value, min_val, max_val):
    return max(min_val, min(max_val, value))


def normalize_text_sentiment(score):
    return clamp(score, -1.0, 1.0)


def normalize_audio_sentiment(score):
    return clamp(score, -1.0, 1.0)


def normalize_urgency(score):
    return clamp(score, 0.0, 1.0)


def build_priority_signals(
    text_sentiment_raw,
    audio_sentiment_raw,
    urgency_raw,
    department,
    keywords
):
    return PrioritySignals(
        text_sentiment=normalize_text_sentiment(text_sentiment_raw),
        audio_sentiment=normalize_audio_sentiment(audio_sentiment_raw),
        urgency=normalize_urgency(urgency_raw),
        department=department,
        keywords=keywords
    )