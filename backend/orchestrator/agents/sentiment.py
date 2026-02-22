"""
Step 3 — Sentiment Analysis
============================
Calls the sentiment service (port 8002) for the complaint path only.
Inquiries skip this step.
"""

import httpx
from langchain_core.runnables import RunnableLambda

SENTIMENT_URL = "http://sentiment:8002"


async def analyze_sentiment(state: dict) -> dict:
    """
    Calls /analyze on the sentiment service.

    Service response: {text_sentiment, text_urgency, keywords, category, ...}
    Only runs for complaint path.
    """
    if state["label"] != "complaint":
        return state

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            f"{SENTIMENT_URL}/analyze",
            json={"text": state["text"]},
        )
        response.raise_for_status()
        data = response.json()

    state["text_sentiment"] = data["text_sentiment"]    # float [-1, 1]
    state["sentiment_category"] = data["category"]      # e.g. "very_negative"
    state["urgency"] = data.get("text_urgency", 0.5)
    state["keywords"] = data.get("keywords", [])

    return state


sentiment_step = RunnableLambda(analyze_sentiment)
