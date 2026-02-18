"""
Whisper Transcription Service — InnovaCX

Transcription only.  Audio feature extraction has been moved to the
separate audio-analyzer service (backend/audio-analyzer/).
"""

import sys
import json
import os
import subprocess

from faster_whisper import WhisperModel


WHISPER_MODEL_NAME = "base"
TARGET_SAMPLE_RATE = 16000

model = WhisperModel(
    WHISPER_MODEL_NAME,
    device="cpu",
    compute_type="int8"
)


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


def main() -> None:
    if len(sys.argv) < 2:
        raise RuntimeError("No audio file path provided")

    input_audio_path = sys.argv[1]
    wav_path = None

    try:
        wav_path = normalize_to_wav(input_audio_path)

        segments, _ = model.transcribe(wav_path, language="en")
        transcript = " ".join(segment.text for segment in segments).strip()

        print(json.dumps({"transcript": transcript}))

    finally:
        if wav_path and os.path.exists(wav_path):
            os.remove(wav_path)


if __name__ == "__main__":
    main()
