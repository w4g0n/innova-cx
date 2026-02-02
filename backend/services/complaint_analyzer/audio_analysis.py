"""
Audio Analysis Pipeline 
==========================================================

"""

import numpy as np
import librosa
import webrtcvad
import warnings
from typing import Dict, List, Tuple, Optional
from faster_whisper import WhisperModel

# Suppress the pkg_resources warning
warnings.filterwarnings('ignore', category=UserWarning, module='pkg_resources')


class AudioAnalysisPipeline:
    """
    Main pipeline class for processing audio complaints.
    """
    
    def __init__(self, sample_rate: int = 16000, vad_aggressiveness: int = 2):
        """
        Initialize the audio analysis pipeline.
        """
        self.sample_rate = sample_rate
        self.vad_aggressiveness = vad_aggressiveness
        
        # Initialize VAD
        print("Initializing Voice Activity Detection...")
        self.vad = webrtcvad.Vad(self.vad_aggressiveness)
        print("✓ VAD initialized")
        
        # Initialize Whisper model
        print("Loading Whisper model (this may take a moment)...")
        self.whisper_model = WhisperModel(
            "base",
            device="cpu",
            compute_type="int8"
        )
        print("✓ Whisper model loaded")
    
    
    def load_audio(self, audio_path: str) -> Tuple[np.ndarray, int]:
        """
        Load an audio file and convert it to the required format.
        """
        print(f"\nLoading audio from: {audio_path}")
        
        try:
            audio, sr = librosa.load(audio_path, sr=self.sample_rate)
            duration = len(audio) / sr
            print(f"✓ Audio loaded: {duration:.2f}s duration, {sr}Hz sample rate")
            return audio, sr
            
        except FileNotFoundError:
            print(f"✗ Error: Audio file not found: {audio_path}")
            raise
        except Exception as e:
            print(f"✗ Error loading audio: {e}")
            raise
    
    
    def apply_vad(self, audio: np.ndarray, sample_rate: int) -> List[bytes]:
        """
        Apply Voice Activity Detection to remove silence and noise.
        """
        print("\nApplying Voice Activity Detection...")
        
        # Convert float audio to 16-bit PCM format
        audio_int16 = (audio * 32767).astype(np.int16)
        audio_bytes = audio_int16.tobytes()
        
        # Calculate frame size (30ms frames)
        frame_duration_ms = 30
        frame_size = int((sample_rate * frame_duration_ms / 1000) * 2)
        
        # Process each frame through VAD
        speech_frames = []
        total_frames = len(audio_bytes) // frame_size
        
        for i in range(0, len(audio_bytes), frame_size):
            frame = audio_bytes[i:i+frame_size]
            
            if len(frame) == frame_size:
                try:
                    if self.vad.is_speech(frame, sample_rate):
                        speech_frames.append(frame)
                except Exception as e:
                    speech_frames.append(frame)
        
        speech_percentage = (len(speech_frames) / total_frames * 100) if total_frames > 0 else 0
        print(f"✓ Found {len(speech_frames)}/{total_frames} speech frames ({speech_percentage:.1f}%)")
        
        if not speech_frames:
            print("⚠️ WARNING: No speech detected by VAD!")
        
        return speech_frames
    
    
    def transcribe_audio(self, audio_frames: List[bytes]) -> Dict[str, str]:
        """
        Transcribe speech frames to text using Whisper.
        """
        print("\nTranscribing audio...")
        
        if not audio_frames:
            print("⚠️ No audio frames to transcribe")
            return {"text": "", "language": "unknown"}
        
        try:
            # Combine audio frames
            combined_audio_bytes = b''.join(audio_frames)
            
            # Convert to numpy array
            audio_int16 = np.frombuffer(combined_audio_bytes, dtype=np.int16)
            audio_for_whisper = audio_int16.astype(np.float32) / 32767.0
            
            # Transcribe using faster-whisper
            segments, info = self.whisper_model.transcribe(audio_for_whisper)
            
            # Collect all text
            full_text = " ".join([segment.text for segment in segments])
            
            transcription = {
                "text": full_text.strip(),
                "language": info.language,
                "language_probability": info.language_probability
            }
            
            preview = transcription['text'][:100]
            if len(transcription['text']) > 100:
                preview += "..."
            print(f"✓ Transcription complete ({info.language}): '{preview}'")
            
            return transcription
            
        except Exception as e:
            print(f"✗ Transcription error: {e}")
            return {
                "text": "",
                "language": "unknown",
                "language_probability": 0.0,
                "error": str(e)
            }
    
    
    def extract_audio_features(self, audio: np.ndarray, sample_rate: int) -> Dict[str, float]:
        """
        Extract acoustic features that indicate emotion.
        """
        print("\nExtracting audio features...")
        
        features = {}
        
        try:
            # Extract pitch
            f0 = librosa.yin(audio, fmin=75, fmax=500, sr=sample_rate)
            f0_valid = f0[f0 > 0]
            
            if len(f0_valid) > 0:
                features['mean_pitch'] = float(np.mean(f0_valid))
                features['std_pitch'] = float(np.std(f0_valid))
            else:
                features['mean_pitch'] = 0.0
                features['std_pitch'] = 0.0
            
            # Extract energy
            rms = librosa.feature.rms(y=audio)[0]
            features['mean_energy'] = float(np.mean(rms))
            features['std_energy'] = float(np.std(rms))
            
            # Extract spectral centroid
            spectral_centroids = librosa.feature.spectral_centroid(y=audio, sr=sample_rate)[0]
            features['mean_spectral_centroid'] = float(np.mean(spectral_centroids))
            
            # Extract zero crossing rate
            zcr = librosa.feature.zero_crossing_rate(audio)[0]
            features['mean_zero_crossing_rate'] = float(np.mean(zcr))
            
            print(f"✓ Extracted {len(features)} features")
            
        except Exception as e:
            print(f"⚠️ Warning: Feature extraction error: {e}")
            features = {
                'mean_pitch': 0.0,
                'std_pitch': 0.0,
                'mean_energy': 0.0,
                'mean_spectral_centroid': 0.0,
                'mean_zero_crossing_rate': 0.0
            }
        
        return features
    
    
    def process_audio_complaint(self, audio_path: str, skip_vad: bool = False) -> Dict:
        """
        Main pipeline method - processes a complete audio complaint.
        """
        print("\n" + "="*70)
        print("AUDIO ANALYSIS PIPELINE - InnovaCX")
        print("="*70)
        
        try:
            # Step 1: Load audio
            audio, sr = self.load_audio(audio_path)
            
            # Step 2: Apply VAD
            if skip_vad:
                print("\nSkipping VAD (using full audio)...")
                audio_int16 = (audio * 32767).astype(np.int16)
                audio_bytes = audio_int16.tobytes()
                speech_frames = [audio_bytes]
            else:
                speech_frames = self.apply_vad(audio, sr)
            
            # Step 3: Transcribe
            transcription = self.transcribe_audio(speech_frames)
            
            # Step 4: Extract features
            features = self.extract_audio_features(audio, sr)
            
            # Combine results
            result = {
                "status": "success",
                "transcription": transcription,
                "audio_features": features,
                "metadata": {
                    "duration_seconds": len(audio) / sr,
                    "sample_rate": sr,
                    "vad_applied": not skip_vad
                }
            }
            
            print("\n" + "="*70)
            print("✓ AUDIO ANALYSIS COMPLETE")
            print("="*70)
            
            return result
            
        except Exception as e:
            print(f"\n✗ Pipeline failed: {e}")
            print("="*70)
            
            return {
                "status": "error",
                "error": str(e),
                "transcription": {"text": "", "language": "unknown"},
                "audio_features": {}
            }


def main():
    """
    Test the audio analysis pipeline.
    """
    import sys
    import os
    
    print("\n" + "="*70)
    print("InnovaCX Audio Analysis Pipeline - Test Mode")
    print("="*70 + "\n")
    
    # Check if audio file was provided
    if len(sys.argv) < 2:
        print("❌ ERROR: No audio file provided!")
        print("\n📖 HOW TO USE:")
        print("   python audio_analysis_template.py <path_to_audio_file>")
        print("\n💡 EXAMPLES:")
        print('   python audio_analysis_template.py "C:\\Users\\ali\\Desktop\\test_audio.wav"')
        print('   python audio_analysis_template.py test_audio.wav')
        print('   python audio_analysis_template.py recording.mp3')
        print("\n" + "="*70 + "\n")
        return
    
    audio_path = sys.argv[1]
    skip_vad = "--skip-vad" in sys.argv
    
    # Check if file exists
    if not os.path.exists(audio_path):
        print(f"❌ ERROR: Audio file not found!")
        print(f"   Looking for: {audio_path}")
        print(f"\n💡 Make sure:")
        print(f"   1. The file exists at that location")
        print(f"   2. The path is correct")
        print(f"   3. You have permission to read the file")
        print("\n" + "="*70 + "\n")
        return
    
    print(f"✓ Audio file found: {audio_path}")
    print(f"   File size: {os.path.getsize(audio_path) / 1024:.2f} KB")
    
    # Initialize pipeline
    print("\nInitializing pipeline...")
    pipeline = AudioAnalysisPipeline(
        sample_rate=16000,
        vad_aggressiveness=2
    )
    print("\n✓ Pipeline ready!")
    
    # THIS IS THE KEY PART - ACTUALLY PROCESS THE AUDIO!
    result = pipeline.process_audio_complaint(audio_path, skip_vad=skip_vad)
    
    # Display results
    if result['status'] == 'success':
        print("\n" + "="*70)
        print("📊 RESULTS")
        print("="*70)
        
        # Transcription
        print("\n📝 TRANSCRIPTION:")
        print(f"   Text: {result['transcription']['text']}")
        print(f"   Language: {result['transcription'].get('language', 'unknown')}")
        if 'language_probability' in result['transcription']:
            print(f"   Confidence: {result['transcription']['language_probability']:.2%}")
        
        # Audio features
        print("\n📊 AUDIO FEATURES:")
        for key, value in result['audio_features'].items():
            print(f"   {key}: {value:.4f}")
        
        # Metadata
        print("\n⚙️ METADATA:")
        for key, value in result['metadata'].items():
            print(f"   {key}: {value}")
        
        print("\n" + "="*70)
        print("✅ SUCCESS - Audio analysis complete!")
        print("="*70 + "\n")
    else:
        print("\n" + "="*70)
        print("❌ FAILED")
        print("="*70)
        print(f"Error: {result.get('error', 'Unknown error')}")
        print("="*70 + "\n")


if __name__ == "__main__":
    main()
