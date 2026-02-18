"""
Audio Analysis Service — InnovaCX

Extracts audio features (pitch, energy, ZCR) and computes an audio
sentiment score.  Accepts any audio format supported by ffmpeg.

Endpoints:
    POST /analyze   — upload audio file, returns {audio_score, audio_features}
    GET  /health    — service health check
"""

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import librosa
import numpy as np
import subprocess
import tempfile
import os
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TARGET_SAMPLE_RATE = 16000

app = FastAPI(title="InnovaCX Audio Analyzer", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Audio helpers
# ---------------------------------------------------------------------------

def normalize_to_wav(input_path: str) -> str:
    """Convert arbitrary audio to mono 16 kHz WAV via ffmpeg."""
    wav_path = f"{input_path}.wav"
    subprocess.run(
        [
            "ffmpeg", "-y",
            "-i", input_path,
            "-ar", str(TARGET_SAMPLE_RATE),
            "-ac", "1",
            wav_path,
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=True,
    )
    return wav_path


def compute_audio_score(audio: np.ndarray) -> float:
    """Lightweight audio-signal score (placeholder — replace with real model)."""
    rms = float(np.mean(librosa.feature.rms(y=audio)))
    zcr = float(np.mean(librosa.feature.zero_crossing_rate(audio)))
    return min(1.0, rms * 10 + zcr)


def extract_audio_features(audio: np.ndarray, sr: int) -> dict:
    """Extract pitch, energy and zero-crossing-rate features."""
    f0 = librosa.yin(audio, fmin=75, fmax=500, sr=sr)
    f0_valid = f0[f0 > 0]

    rms = librosa.feature.rms(y=audio)[0]
    zcr = librosa.feature.zero_crossing_rate(audio)[0]

    return {
        "mean_pitch": float(np.mean(f0_valid)) if len(f0_valid) else 0.0,
        "std_pitch": float(np.std(f0_valid)) if len(f0_valid) else 0.0,
        "mean_energy": float(np.mean(rms)),
        "std_energy": float(np.std(rms)),
        "mean_zero_crossing_rate": float(np.mean(zcr)),
    }


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.post("/analyze")
async def analyze_audio(audio: UploadFile = File(...)):
    """Receive an audio file, extract features and return a score."""
    tmp_path = None
    wav_path = None
    try:
        suffix = os.path.splitext(audio.filename or "audio.webm")[1] or ".webm"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(await audio.read())
            tmp_path = tmp.name

        wav_path = normalize_to_wav(tmp_path)
        audio_data, _ = librosa.load(wav_path, sr=TARGET_SAMPLE_RATE)

        score = compute_audio_score(audio_data)
        features = extract_audio_features(audio_data, TARGET_SAMPLE_RATE)

        logger.info("Audio analysis complete: score=%.3f", score)
        return {"audio_score": score, "audio_features": features}

    except Exception as e:
        logger.error("Audio analysis failed: %s", e)
        raise HTTPException(status_code=500, detail="Audio analysis failed")

    finally:
        for p in [tmp_path, wav_path]:
            if p and os.path.exists(p):
                os.remove(p)


@app.get("/health")
async def health():
    return {"status": "healthy", "service": "audio-analyzer"}
