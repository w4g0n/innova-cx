"""
Step 1 — Whisper Transcriber
============================
Sends audio bytes to the Whisper service (Node/Express on port 3001).
If the state already has text (text-only input path), transcription is skipped.
"""

import httpx
from langchain_core.runnables import RunnableLambda

WHISPER_URL = "http://whisper:3001"


async def transcribe(state: dict) -> dict:
    """
    Sends audio to Whisper and populates state["text"].

    Whisper response shape:
        {transcript, audio_score, audio_features, sentiment}

    Skips if state["text"] is already set (text-only path).
    """
    if state.get("text"):
        # Text was provided directly — transcription not needed
        return state

    if not state.get("audio_bytes"):
        raise ValueError("State must have either 'text' or 'audio_bytes'")

    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            f"{WHISPER_URL}/transcribe",
            files={"audio": ("audio.webm", state["audio_bytes"], "audio/webm")},
        )
        response.raise_for_status()
        data = response.json()

    state["text"] = data.get("transcript", "")
    state["transcription_confidence"] = data.get("confidence", 1.0)
    # Preserve any audio_features returned by Whisper
    if data.get("audio_features"):
        state["audio_features"] = data["audio_features"]

    return state


transcriber_step = RunnableLambda(transcribe)
