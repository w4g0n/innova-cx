import sys
import json
import os
import subprocess

import librosa
import numpy as np
from faster_whisper import WhisperModel


# ===============================
# Model (loaded once per container)
# ===============================
WHISPER_MODEL_NAME = "base"
TARGET_SAMPLE_RATE = 16000

model = WhisperModel(
    WHISPER_MODEL_NAME,
    device="cpu",
    compute_type="int8"
)


# ===============================
# Audio analysis helpers
# ===============================
def compute_audio_score(audio: np.ndarray) -> float:
    """
    Very lightweight audio signal scoring.
    Placeholder logic – replace with real model later.
    """
    rms = float(np.mean(librosa.feature.rms(y=audio)))
    zcr = float(np.mean(librosa.feature.zero_crossing_rate(audio)))

    return min(1.0, rms * 10 + zcr)

def extract_audio_features(audio: np.ndarray, sr: int) -> dict:
    f0 = librosa.yin(audio, fmin=75, fmax=500, sr=sr)
    f0_valid = f0[f0 > 0]

    rms = librosa.feature.rms(y=audio)[0]

    return {
        "mean_pitch": float(np.mean(f0_valid)) if len(f0_valid) else 0.0,
        "mean_energy": float(np.mean(rms)),
    }

# ===============================
# Audio normalization
# ===============================
def normalize_to_wav(input_path: str) -> str:
    """
    Converts arbitrary audio input to
    mono, 16kHz WAV using ffmpeg.
    """
    wav_path = f"{input_path}.wav"

    subprocess.run(
        [
            "ffmpeg",
            "-y",
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


# ===============================
# Main entrypoint
# ===============================
def main() -> None:
    if len(sys.argv) < 2:
        raise RuntimeError("No audio file path provided")

    input_audio_path = sys.argv[1]
    wav_path = None

    try:
        # Normalize input audio
        wav_path = normalize_to_wav(input_audio_path)

        # Load normalized audio
        audio, _ = librosa.load(wav_path, sr=TARGET_SAMPLE_RATE)

        # Transcription
        segments, _ = model.transcribe(audio, language="en")
        transcript = " ".join(segment.text for segment in segments).strip()

        # Analysis
        audio_score = compute_audio_score(audio)
        audio_features = extract_audio_features(audio, TARGET_SAMPLE_RATE)

        # Output (JSON only – consumed by Node)
        print(json.dumps({
            "transcript": transcript,
            "audio_score": audio_score,
            "audio_features": audio_features,
        }))

    finally:
        # Always clean up temp WAV
        if wav_path and os.path.exists(wav_path):
            os.remove(wav_path)


if __name__ == "__main__":
    main()
