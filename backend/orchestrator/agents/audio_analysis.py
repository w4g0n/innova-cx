"""
Step 4 — Audio Analysis
========================
Extracts audio sentiment via the /analyze-combined endpoint on the
sentiment service. Only runs when audio was provided and the complaint
path is active.

For text-only inputs, audio_sentiment defaults to 0.0 (neutral).
"""

import httpx
from langchain_core.runnables import RunnableLambda

SENTIMENT_URL = "http://sentiment:8002"


async def analyze_audio(state: dict) -> dict:
    """
    Calls /analyze-combined on the sentiment service to get audio sentiment.

    Service response: {text_sentiment, audio_sentiment, combined_sentiment, ...}
    """
    if state["label"] != "complaint" or not state.get("audio_bytes"):
        # Text-only path or inquiry — neutral audio sentiment
        state["audio_sentiment"] = 0.0
        state["combined_sentiment"] = state.get("text_sentiment", 0.0)
        return state

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            f"{SENTIMENT_URL}/analyze-combined",
            json={
                "text": state["text"],
                "audio_features": state.get("audio_features") or {},
            },
        )
        response.raise_for_status()
        data = response.json()

    state["audio_sentiment"] = data.get("audio_sentiment", 0.0) or 0.0
    state["combined_sentiment"] = data.get(
        "combined_sentiment", state.get("text_sentiment", 0.0)
    )

    return state


audio_analysis_step = RunnableLambda(analyze_audio)
