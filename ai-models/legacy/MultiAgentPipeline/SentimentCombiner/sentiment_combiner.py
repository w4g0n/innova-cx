"""
Audio Sentiment Feature Combiner

Converts audio features (pitch, energy, etc.) into sentiment signals
and combines them with text-based sentiment from RoBERTa model.

Principles:
- Single Responsibility: Only handles audio → sentiment conversion
- Fail-Fast: Validate inputs immediately
- Observability: Log feature transformations
"""

import numpy as np
from typing import Dict
from dataclasses import dataclass
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-7s | %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)


@dataclass
class AudioSentimentSignals:
    """
    Validated audio sentiment signals.
    All values normalized to -1 to 1 range.
    """
    energy_signal: float        # Low energy = more negative
    pitch_signal: float          # High pitch variance = emotional/upset
    speaking_rate_signal: float  # Fast speaking = stressed/urgent
    overall_audio_sentiment: float  # Combined audio sentiment score
    
    def __post_init__(self):
        """Validate all signals are in valid range"""
        for field_name in ['energy_signal', 'pitch_signal', 'speaking_rate_signal', 'overall_audio_sentiment']:
            value = getattr(self, field_name)
            if not -1.0 <= value <= 1.0:
                raise ValueError(f"❌ {field_name} must be in [-1, 1], got {value}")


class AudioSentimentAnalyzer:
    """
    Analyzes audio features and converts them to sentiment signals.
    
    Audio features that indicate negative sentiment:
    - Low energy (tired, defeated, sad)
    - High pitch variance (upset, crying, shouting)
    - Fast speaking rate (stressed, urgent, angry)
    - Low pitch (sadness, depression)
    - High pitch (anxiety, stress)
    """
    
    def __init__(self):
        """Initialize with empirically-derived thresholds"""
        
        # Energy thresholds (from librosa RMS)
        self.energy_low_threshold = 0.02   # Below this = low energy (negative)
        self.energy_high_threshold = 0.08  # Above this = high energy (can be positive or angry)
        
        # Pitch thresholds (Hz)
        self.pitch_low_threshold = 120    # Below this = sad/defeated
        self.pitch_high_threshold = 200   # Above this = stressed/anxious
        self.pitch_variance_threshold = 50  # High variance = emotional
        
        # Speaking rate threshold (zero crossing rate proxy)
        self.zcr_slow_threshold = 0.05    # Below this = slow/measured
        self.zcr_fast_threshold = 0.15    # Above this = fast/rushed
        
        logger.info("✓ AudioSentimentAnalyzer initialized")
    
    def analyze_energy(self, mean_energy: float, std_energy: float) -> float:
        """
        Convert energy features to sentiment signal.
        
        Low energy → negative sentiment (tired, defeated)
        Very high energy → could be angry or excited (context-dependent)
        
        Returns: -1 (very negative) to +1 (very positive)
        """
        # Normalize energy to sentiment scale
        if mean_energy < self.energy_low_threshold:
            # Very low energy = negative (sad, defeated)
            signal = -0.7
        elif mean_energy > self.energy_high_threshold:
            # Very high energy = intense emotion (could be anger or excitement)
            # Use energy variance to distinguish
            if std_energy > 0.02:
                signal = -0.4  # High variance = likely angry/upset
            else:
                signal = 0.0   # Stable high energy = neutral
        else:
            # Normal energy range
            signal = 0.0
        
        logger.debug(f"  Energy: {mean_energy:.4f} → sentiment signal: {signal:.2f}")
        return signal
    
    def analyze_pitch(self, mean_pitch: float, std_pitch: float) -> float:
        """
        Convert pitch features to sentiment signal.
        
        Very low pitch → sadness, depression
        Very high pitch → anxiety, stress
        High pitch variance → emotional distress
        
        Returns: -1 (very negative) to +1 (very positive)
        """
        if mean_pitch == 0:
            # No valid pitch detected
            return 0.0
        
        signal = 0.0
        
        # Low pitch = sadness
        if mean_pitch < self.pitch_low_threshold:
            signal = -0.5
        
        # High pitch = stress/anxiety
        elif mean_pitch > self.pitch_high_threshold:
            signal = -0.3
        
        # High pitch variance = emotional upset
        if std_pitch > self.pitch_variance_threshold:
            signal -= 0.3  # Make more negative
        
        signal = np.clip(signal, -1.0, 1.0)
        logger.debug(f"  Pitch: mean={mean_pitch:.1f}Hz, std={std_pitch:.1f}Hz → signal: {signal:.2f}")
        return signal
    
    def analyze_speaking_rate(self, zcr: float) -> float:
        """
        Convert speaking rate (via zero crossing rate) to sentiment signal.
        
        Very fast speaking → stressed, urgent, angry
        Very slow speaking → defeated, sad (but context-dependent)
        
        Returns: -1 (very negative) to +1 (very positive)
        """
        if zcr > self.zcr_fast_threshold:
            # Fast speaking = stressed/urgent
            signal = -0.4
        elif zcr < self.zcr_slow_threshold:
            # Slow speaking = possibly sad/defeated
            signal = -0.2
        else:
            # Normal speaking rate
            signal = 0.0
        
        logger.debug(f"  Speaking rate (ZCR): {zcr:.4f} → signal: {signal:.2f}")
        return signal
    
    def extract_sentiment_signals(self, audio_features: Dict[str, float]) -> AudioSentimentSignals:
        """
        Extract sentiment signals from audio features.
        
        Args:
            audio_features: Dict with keys:
                - mean_energy
                - std_energy
                - mean_pitch
                - std_pitch
                - mean_zero_crossing_rate
        
        Returns:
            AudioSentimentSignals with all signals normalized to [-1, 1]
        """
        logger.info("🎙️ Extracting sentiment signals from audio features...")
        
        # Validate input
        required_keys = ['mean_energy', 'std_energy', 'mean_pitch', 'std_pitch', 'mean_zero_crossing_rate']
        for key in required_keys:
            if key not in audio_features:
                raise ValueError(f"❌ Missing required audio feature: {key}")
        
        # Extract individual signals
        energy_signal = self.analyze_energy(
            audio_features['mean_energy'],
            audio_features['std_energy']
        )
        
        pitch_signal = self.analyze_pitch(
            audio_features['mean_pitch'],
            audio_features['std_pitch']
        )
        
        speaking_rate_signal = self.analyze_speaking_rate(
            audio_features['mean_zero_crossing_rate']
        )
        
        # Combine signals (weighted average)
        overall = (
            energy_signal * 0.4 +      # Energy is most reliable
            pitch_signal * 0.4 +        # Pitch is very informative
            speaking_rate_signal * 0.2  # Speaking rate is supplementary
        )
        
        signals = AudioSentimentSignals(
            energy_signal=energy_signal,
            pitch_signal=pitch_signal,
            speaking_rate_signal=speaking_rate_signal,
            overall_audio_sentiment=overall
        )
        
        logger.info(f"✓ Audio sentiment signals extracted: {overall:.3f}")
        return signals
    
    def combine_text_audio_sentiment(
        self,
        text_sentiment: float,
        audio_signals: AudioSentimentSignals,
        text_weight: float = 0.7,
        audio_weight: float = 0.3
    ) -> Dict[str, float]:
        """
        Combine text-based sentiment with audio sentiment signals.
        
        Args:
            text_sentiment: Sentiment from RoBERTa model (-1 to 1)
            audio_signals: Audio sentiment signals
            text_weight: Weight for text sentiment (default 0.7)
            audio_weight: Weight for audio sentiment (default 0.3)
        
        Returns:
            Dict with:
                - text_sentiment: Original text sentiment
                - audio_sentiment: Audio sentiment
                - combined_sentiment: Weighted combination
                - confidence: How much audio reinforces text
        """
        # Validate inputs
        if not -1.0 <= text_sentiment <= 1.0:
            raise ValueError(f"❌ text_sentiment must be in [-1, 1], got {text_sentiment}")
        
        if not np.isclose(text_weight + audio_weight, 1.0):
            raise ValueError(f"❌ Weights must sum to 1.0, got {text_weight + audio_weight}")
        
        # Combine sentiments
        audio_sentiment = audio_signals.overall_audio_sentiment
        combined_sentiment = (text_sentiment * text_weight) + (audio_sentiment * audio_weight)
        
        # Calculate confidence (how much audio agrees with text)
        # If both are same sign and similar magnitude = high confidence
        # If opposite signs = low confidence
        if text_sentiment * audio_sentiment > 0:
            # Same sign (both positive or both negative)
            agreement = 1.0 - abs(text_sentiment - audio_sentiment) / 2.0
        else:
            # Opposite signs
            agreement = 0.5 - abs(text_sentiment - audio_sentiment) / 4.0
        
        confidence = np.clip(agreement, 0.0, 1.0)
        
        logger.info(f"🔗 Combined sentiment: text={text_sentiment:.3f}, audio={audio_sentiment:.3f} → combined={combined_sentiment:.3f} (confidence={confidence:.2f})")
        
        return {
            'text_sentiment': text_sentiment,
            'audio_sentiment': audio_sentiment,
            'combined_sentiment': combined_sentiment,
            'confidence': confidence,
            'energy_signal': audio_signals.energy_signal,
            'pitch_signal': audio_signals.pitch_signal,
            'speaking_rate_signal': audio_signals.speaking_rate_signal
        }


# ============================================================================
# EXAMPLE USAGE
# ============================================================================

if __name__ == "__main__":
    # Example audio features (from librosa extraction)
    example_features = {
        'mean_energy': 0.03,       # Low energy
        'std_energy': 0.01,
        'mean_pitch': 110.0,       # Low pitch (sad)
        'std_pitch': 30.0,
        'mean_zero_crossing_rate': 0.08
    }
    
    # Example text sentiment from RoBERTa
    example_text_sentiment = -0.65  # Negative
    
    # Initialize analyzer
    analyzer = AudioSentimentAnalyzer()
    
    # Extract audio signals
    audio_signals = analyzer.extract_sentiment_signals(example_features)
    
    print("\n" + "="*60)
    print("Audio Sentiment Signals:")
    print("="*60)
    print(f"Energy signal:        {audio_signals.energy_signal:.3f}")
    print(f"Pitch signal:         {audio_signals.pitch_signal:.3f}")
    print(f"Speaking rate signal: {audio_signals.speaking_rate_signal:.3f}")
    print(f"Overall audio:        {audio_signals.overall_audio_sentiment:.3f}")
    
    # Combine with text sentiment
    result = analyzer.combine_text_audio_sentiment(
        text_sentiment=example_text_sentiment,
        audio_signals=audio_signals
    )
    
    print("\n" + "="*60)
    print("Combined Sentiment Analysis:")
    print("="*60)
    print(f"Text sentiment:     {result['text_sentiment']:.3f}")
    print(f"Audio sentiment:    {result['audio_sentiment']:.3f}")
    print(f"Combined sentiment: {result['combined_sentiment']:.3f}")
    print(f"Confidence:         {result['confidence']:.2f}")
    print("="*60)
