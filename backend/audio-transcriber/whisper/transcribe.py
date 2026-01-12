from faster_whisper import WhisperModel
import sys

audio_path = sys.argv[1]

model = WhisperModel(
    "base",
    device="cpu",       # change to "cuda" on GCP GPU
    compute_type="int8"
)

segments, info = model.transcribe(audio_path)

for segment in segments:
    print(segment.text, end=" ")
