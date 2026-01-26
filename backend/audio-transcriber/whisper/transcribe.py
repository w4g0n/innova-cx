import sys
from faster_whisper import WhisperModel

# -----------------------------------
# Model initialization (once per run)
# -----------------------------------
MODEL_NAME = "base"

model = WhisperModel(
    MODEL_NAME,
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
        print("❌ Usage: python transcribe.py <audio_path>")
        sys.exit(1)

    audio_path = sys.argv[1]

    print("🎙️ Transcribing:", audio_path)
    transcript = transcribe_audio_file(audio_path)

    print("\n📝 TRANSCRIPT:")
    print(transcript)


if __name__ == "__main__":
    main()