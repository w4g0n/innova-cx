import os
from pathlib import Path
from typing import Dict, List, Tuple

import librosa
import numpy as np
import webrtcvad
from faster_whisper import WhisperModel


DEFAULT_SAMPLE_RATE = 16000
DEFAULT_VAD_AGGRESSIVENESS = 2
TRANSCRIBER_DIR = Path(__file__).resolve().parent
DEFAULT_WHISPER_MODEL_NAME = "base"
DEFAULT_WHISPER_MODEL_PATH = TRANSCRIBER_DIR / "model"


def resolve_whisper_model() -> str:
    configured_path = os.environ.get("WHISPER_MODEL_PATH", str(DEFAULT_WHISPER_MODEL_PATH)).strip()
    if configured_path and Path(configured_path).exists():
        return configured_path
    return os.environ.get("WHISPER_MODEL_NAME", DEFAULT_WHISPER_MODEL_NAME).strip() or DEFAULT_WHISPER_MODEL_NAME


class AudioAnalysisPipeline:
    """
    Audio analysis pipeline for complaints.
    Designed to be terminal-friendly and demo-ready.
    """

    def __init__(
        self,
        sample_rate: int = DEFAULT_SAMPLE_RATE,
        vad_aggressiveness: int = DEFAULT_VAD_AGGRESSIVENESS,
        verbose: bool = True,
    ):
        self.sample_rate = sample_rate
        self.verbose = verbose

        self._log("Initializing Voice Activity Detection...")
        self.vad = webrtcvad.Vad(vad_aggressiveness)
        self._log("✓ VAD initialized")

        self._log("Loading Whisper model (this may take a moment)...")
        self.whisper_model = WhisperModel(
            resolve_whisper_model(),
            device="cpu",
            compute_type="int8",
        )
        self._log("✓ Whisper model loaded")


    # Logging helper

    def _log(self, message: str):
        if self.verbose:
            print(message)


    # Audio loading

    def load_audio(self, audio_path: str) -> Tuple[np.ndarray, int]:
        self._log(f"\nLoading audio from: {audio_path}")

        if not os.path.exists(audio_path):
            raise FileNotFoundError(f"Audio file not found: {audio_path}")

        audio, sr = librosa.load(audio_path, sr=self.sample_rate)
        duration = len(audio) / sr

        self._log(f"✓ Audio loaded: {duration:.2f}s @ {sr}Hz")
        return audio, sr


    # Voice Activity Detection

    def apply_vad(self, audio: np.ndarray, sr: int) -> List[bytes]:
        self._log("\nApplying Voice Activity Detection...")

        audio_int16 = (audio * 32767).astype(np.int16)
        audio_bytes = audio_int16.tobytes()

        frame_duration_ms = 30
        frame_size = int((sr * frame_duration_ms / 1000) * 2)

        speech_frames: List[bytes] = []
        total_frames = 0

        for i in range(0, len(audio_bytes), frame_size):
            frame = audio_bytes[i:i + frame_size]
            if len(frame) != frame_size:
                continue

            total_frames += 1
            if self.vad.is_speech(frame, sr):
                speech_frames.append(frame)

        percent = (len(speech_frames) / total_frames * 100) if total_frames else 0
        self._log(f"✓ Speech frames: {len(speech_frames)}/{total_frames} ({percent:.1f}%)")

        if not speech_frames:
            self._log("⚠️ WARNING: No speech detected")

        return speech_frames


    # Transcription

    def transcribe(self, frames: List[bytes]) -> Dict:
        self._log("\nTranscribing audio...")

        if not frames:
            self._log("⚠️ No frames to transcribe")
            return {"text": "", "language": "unknown", "language_probability": 0.0}

        combined = b"".join(frames)
        audio_int16 = np.frombuffer(combined, dtype=np.int16)
        audio_float = audio_int16.astype(np.float32) / 32767.0

        segments, info = self.whisper_model.transcribe(audio_float)
        text = " ".join(segment.text for segment in segments).strip()

        preview = text[:100] + ("..." if len(text) > 100 else "")
        self._log(f"✓ Transcription ({info.language}): \"{preview}\"")

        return {
            "text": text,
            "language": info.language,
            "language_probability": info.language_probability,
        }


    # Feature extraction

    def extract_features(self, audio: np.ndarray, sr: int) -> Dict[str, float]:
        self._log("\nExtracting audio features...")

        features: Dict[str, float] = {}

        f0 = librosa.yin(audio, fmin=75, fmax=500, sr=sr)
        f0_valid = f0[f0 > 0]

        features["mean_pitch"] = float(np.mean(f0_valid)) if len(f0_valid) else 0.0
        features["std_pitch"] = float(np.std(f0_valid)) if len(f0_valid) else 0.0

        rms = librosa.feature.rms(y=audio)[0]
        features["mean_energy"] = float(np.mean(rms))
        features["std_energy"] = float(np.std(rms))

        zcr = librosa.feature.zero_crossing_rate(audio)[0]
        features["mean_zero_crossing_rate"] = float(np.mean(zcr))

        self._log(f"✓ Extracted {len(features)} features")
        return features


    # Main pipeline
    def process(self, audio_path: str, skip_vad: bool = False) -> Dict:
        self._log("\n" + "=" * 60)
        self._log("AUDIO ANALYSIS PIPELINE – InnovaCX")
        self._log("=" * 60)

        audio, sr = self.load_audio(audio_path)

        if skip_vad:
            self._log("\nSkipping VAD (using full audio)")
            frames = [(audio * 32767).astype(np.int16).tobytes()]
        else:
            frames = self.apply_vad(audio, sr)

        transcription = self.transcribe(frames)
        features = self.extract_features(audio, sr)

        self._log("\n✓ AUDIO ANALYSIS COMPLETE")
        self._log("=" * 60)

        return {
            "status": "success",
            "transcription": transcription,
            "audio_features": features,
            "metadata": {
                "duration_seconds": len(audio) / sr,
                "sample_rate": sr,
                "vad_applied": not skip_vad,
            },
        }


def main():
    import sys

    if len(sys.argv) < 2:
        print("Usage: python audio_analysis_pipeline.py <audio_file> [--skip-vad]")
        sys.exit(1)

    audio_path = sys.argv[1]
    skip_vad = "--skip-vad" in sys.argv

    pipeline = AudioAnalysisPipeline(verbose=True)
    result = pipeline.process(audio_path, skip_vad=skip_vad)

    print("\nRESULT:")
    print(result)


if __name__ == "__main__":
    main()
