"""
Mock Predictor for Demo Mode

Returns realistic sentiment scores based on keyword analysis.
No model loading required - works out of the box.
"""

import time
from typing import Dict, List, Optional

NEGATIVE_KEYWORDS = [
    "broken", "not working", "emergency", "urgent", "terrible",
    "frustrated", "angry", "unacceptable", "worst", "failed",
    "leak", "flooding", "outage", "stuck", "dangerous",
    "horrible", "awful", "disgusting", "useless", "incompetent"
]

POSITIVE_KEYWORDS = [
    "thank", "thanks", "appreciate", "great", "excellent", "good",
    "helpful", "quick", "resolved", "fixed", "working",
    "wonderful", "amazing", "fantastic", "perfect", "satisfied"
]

URGENCY_KEYWORDS = [
    "emergency", "urgent", "immediately", "asap", "now",
    "flooding", "fire", "dangerous", "safety", "stuck",
    "critical", "severe", "life", "death", "hazard"
]

DOMAIN_KEYWORDS = [
    "AC", "air conditioning", "heating", "elevator", "lift",
    "water", "leak", "power", "electricity", "internet",
    "WiFi", "parking", "security", "maintenance", "noise",
    "plumbing", "pipe", "drain", "toilet", "faucet",
    "light", "outlet", "circuit", "breaker", "thermostat"
]


class MockPredictor:
    """Mock predictor using keyword-based heuristics."""

    def predict(self, text: str) -> Dict:
        start = time.time()
        text_lower = text.lower()

        # Calculate sentiment based on keywords
        neg_count = sum(1 for kw in NEGATIVE_KEYWORDS if kw in text_lower)
        pos_count = sum(1 for kw in POSITIVE_KEYWORDS if kw in text_lower)

        # Score between -1 and 1
        total = neg_count + pos_count
        if total == 0:
            sentiment = 0.0
        else:
            sentiment = (pos_count - neg_count) / max(total, 1)
            sentiment = max(-1.0, min(1.0, sentiment * 1.5))

        # Calculate urgency
        urgency_count = sum(1 for kw in URGENCY_KEYWORDS if kw in text_lower)
        urgency = min(1.0, urgency_count * 0.3 + (0.3 if neg_count > 0 else 0))

        # Extract keywords found in text
        keywords = [kw for kw in DOMAIN_KEYWORDS if kw.lower() in text_lower]

        elapsed = (time.time() - start) * 1000

        return {
            "text_sentiment": round(sentiment, 3),
            "text_urgency": round(urgency, 3),
            "keywords": keywords[:5],
            "processing_time_ms": round(elapsed, 1)
        }

    def predict_combined(
        self, text: str, audio_features: Optional[Dict] = None
    ) -> Dict:
        """Predict combined text + audio sentiment."""
        text_result = self.predict(text)

        # Mock audio sentiment based on features or default
        if audio_features:
            energy = audio_features.get("mean_energy", 0.05)
            # Higher energy often correlates with distress
            audio_sentiment = -0.3 if energy > 0.1 else 0.0
        else:
            audio_sentiment = None

        # Combine (70% text, 30% audio if available)
        if audio_sentiment is not None:
            combined = text_result["text_sentiment"] * 0.7 + audio_sentiment * 0.3
        else:
            combined = text_result["text_sentiment"]

        return {
            "text_sentiment": text_result["text_sentiment"],
            "audio_sentiment": audio_sentiment,
            "combined_sentiment": round(combined, 3),
            "urgency": text_result["text_urgency"],
            "keywords": text_result["keywords"],
            "confidence": 0.85
        }
