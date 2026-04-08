import sys
import json
import os
from pathlib import Path
from faster_whisper import WhisperModel


# Model initialization (once per run)
TRANSCRIBER_DIR = Path(__file__).resolve().parent
DEFAULT_WHISPER_MODEL_NAME = "base"
DEFAULT_WHISPER_MODEL_PATH = TRANSCRIBER_DIR / "model"


def resolve_whisper_model() -> str:
    configured_path = os.environ.get("WHISPER_MODEL_PATH", str(DEFAULT_WHISPER_MODEL_PATH)).strip()
    if configured_path and Path(configured_path).exists():
        return configured_path
    return os.environ.get("WHISPER_MODEL_NAME", DEFAULT_WHISPER_MODEL_NAME).strip() or DEFAULT_WHISPER_MODEL_NAME

model = WhisperModel(
    resolve_whisper_model(),
    device="cpu",
    compute_type="int8",
)


def transcribe_audio_file(audio_path: str) -> str:
    """
    Transcribe an audio file using Faster-Whisper.

    Args:
        audio_path (str): Path to audio file

    Returns:
        str: Transcribed text
    """
    segments, _ = model.transcribe(audio_path)
    return " ".join(segment.text for segment in segments).strip()


def main():
    if len(sys.argv) < 2:
        print(json.dumps({"error": "Usage: python transcribe.py <audio_path>"}))
        sys.exit(1)

    audio_path = sys.argv[1]
    transcript = transcribe_audio_file(audio_path)
    print(json.dumps({"transcript": transcript}))


if __name__ == "__main__":
    main()
