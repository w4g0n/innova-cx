"""
Unified Complaint Analyzer

Complete end-to-end pipeline:
Audio File → Transcription → Text Sentiment → Audio Features → Combined Sentiment

Usage:
    python unified_complaint_analyzer.py path/to/audio.wav models/sentiment-production
"""

import sys
import logging
from pathlib import Path
from typing import Dict
import json

# Add parent directory to path to import modules
sys.path.insert(0, str(Path(__file__).parent))

# Import our modules
from audio_sentiment_combiner import AudioSentimentAnalyzer

# Import existing modules (adjust paths as needed)
try:
    # Try importing from project structure
    from backend.audio_transcriber.whisper.audio_analysis import AudioAnalysisPipeline
except ImportError:
    # Fallback: assume we're in DSPY directory
    sys.path.insert(0, str(Path(__file__).parent / 'backend' / 'audio-transcriber' / 'whisper'))
    from audio_analysis import AudioAnalysisPipeline

try:
    from src.ml_wrapper import MLModelWrapper
except ImportError:
    print("⚠️ Warning: Could not import MLModelWrapper")
    print("   Make sure you're running from DSPY directory")
    print("   Or the path to ml_wrapper.py is correct")

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-7s | %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)


class UnifiedComplaintAnalyzer:
    """
    Complete pipeline for audio complaint analysis.
    
    Pipeline:
    1. Load audio file
    2. Apply Voice Activity Detection (remove silence)
    3. Transcribe with Whisper
    4. Extract audio features (pitch, energy, etc.)
    5. Analyze text sentiment with RoBERTa
    6. Convert audio features to sentiment signals
    7. Combine text + audio sentiment
    """
    
    def __init__(
        self,
        text_model_path: str,
        sample_rate: int = 16000,
        vad_aggressiveness: int = 2
    ):
        """
        Initialize complete pipeline.
        
        Args:
            text_model_path: Path to trained RoBERTa sentiment model
            sample_rate: Audio sample rate (default 16000)
            vad_aggressiveness: VAD sensitivity 0-3 (default 2)
        """
        logger.info("="*70)
        logger.info("🚀 Initializing Unified Complaint Analyzer")
        logger.info("="*70)
        
        # Initialize audio pipeline (Whisper + feature extraction)
        logger.info("\n📻 Initializing audio analysis pipeline...")
        self.audio_pipeline = AudioAnalysisPipeline(
            sample_rate=sample_rate,
            vad_aggressiveness=vad_aggressiveness,
            verbose=False  # We'll handle logging
        )
        logger.info("✓ Audio pipeline ready")
        
        # Initialize text sentiment model (RoBERTa)
        logger.info(f"\n🤖 Loading text sentiment model from: {text_model_path}")
        self.text_model = MLModelWrapper(text_model_path)
        logger.info("✓ Text model loaded")
        
        # Initialize audio sentiment analyzer
        logger.info("\n🎙️ Initializing audio sentiment analyzer...")
        self.audio_sentiment_analyzer = AudioSentimentAnalyzer()
        logger.info("✓ Audio sentiment analyzer ready")
        
        logger.info("\n" + "="*70)
        logger.info("✅ All components initialized successfully!")
        logger.info("="*70)
    
    def analyze_complaint(
        self,
        audio_path: str,
        skip_vad: bool = False,
        text_weight: float = 0.7,
        audio_weight: float = 0.3
    ) -> Dict:
        """
        Analyze a complaint from audio file.
        
        Args:
            audio_path: Path to audio file (.wav, .mp3, etc.)
            skip_vad: Skip voice activity detection (default False)
            text_weight: Weight for text sentiment (default 0.7)
            audio_weight: Weight for audio sentiment (default 0.3)
        
        Returns:
            Dict with complete analysis results:
                - transcription: Text from audio
                - audio_features: Raw audio features
                - text_sentiment: Sentiment from text
                - audio_sentiment: Sentiment from audio
                - combined_sentiment: Final combined score
                - confidence: How much audio agrees with text
                - metadata: Processing info
        """
        logger.info("\n" + "="*70)
        logger.info("🎯 ANALYZING AUDIO COMPLAINT")
        logger.info("="*70)
        logger.info(f"Audio file: {audio_path}")
        logger.info(f"Weights: text={text_weight:.0%}, audio={audio_weight:.0%}")
        logger.info("="*70)
        
        # Step 1: Process audio (transcribe + extract features)
        logger.info("\n📻 Step 1/4: Processing audio file...")
        audio_result = self.audio_pipeline.process(audio_path, skip_vad=skip_vad)
        
        if audio_result['status'] != 'success':
            logger.error("❌ Audio processing failed")
            return {
                'status': 'error',
                'error': audio_result.get('error', 'Unknown audio processing error'),
                'stage': 'audio_processing'
            }
        
        transcription_text = audio_result['transcription']['text']
        audio_features = audio_result['audio_features']
        metadata = audio_result['metadata']
        
        logger.info(f"✓ Transcription: \"{transcription_text[:100]}{'...' if len(transcription_text) > 100 else ''}\"")
        logger.info(f"✓ Audio duration: {metadata['duration_seconds']:.2f}s")
        
        # Check if transcription is empty
        if not transcription_text.strip():
            logger.warning("⚠️ Warning: Empty transcription detected")
            return {
                'status': 'warning',
                'message': 'No speech detected in audio',
                'transcription': transcription_text,
                'audio_features': audio_features,
                'metadata': metadata
            }
        
        # Step 2: Analyze text sentiment
        logger.info("\n🤖 Step 2/4: Analyzing text sentiment...")
        text_result = self.text_model.predict_sentiment(transcription_text)
        text_sentiment = text_result['sentiment']
        
        # Categorize text sentiment
        if text_sentiment < -0.6:
            text_category = "very negative"
        elif text_sentiment < -0.2:
            text_category = "negative"
        elif text_sentiment < 0.2:
            text_category = "neutral"
        elif text_sentiment < 0.6:
            text_category = "positive"
        else:
            text_category = "very positive"
        
        logger.info(f"✓ Text sentiment: {text_sentiment:.3f} ({text_category})")
        
        # Step 3: Extract audio sentiment signals
        logger.info("\n🎙️ Step 3/4: Extracting audio sentiment signals...")
        audio_signals = self.audio_sentiment_analyzer.extract_sentiment_signals(audio_features)
        logger.info(f"✓ Audio sentiment: {audio_signals.overall_audio_sentiment:.3f}")
        
        # Step 4: Combine text + audio sentiment
        logger.info("\n🔗 Step 4/4: Combining text and audio sentiment...")
        combined_result = self.audio_sentiment_analyzer.combine_text_audio_sentiment(
            text_sentiment=text_sentiment,
            audio_signals=audio_signals,
            text_weight=text_weight,
            audio_weight=audio_weight
        )
        
        combined_sentiment = combined_result['combined_sentiment']
        confidence = combined_result['confidence']
        
        # Categorize combined sentiment
        if combined_sentiment < -0.6:
            combined_category = "very negative"
        elif combined_sentiment < -0.2:
            combined_category = "negative"
        elif combined_sentiment < 0.2:
            combined_category = "neutral"
        elif combined_sentiment < 0.6:
            combined_category = "positive"
        else:
            combined_category = "very positive"
        
        logger.info(f"✓ Combined sentiment: {combined_sentiment:.3f} ({combined_category})")
        logger.info(f"✓ Confidence: {confidence:.2%}")
        
        # Compile complete result
        result = {
            'status': 'success',
            'transcription': {
                'text': transcription_text,
                'language': audio_result['transcription']['language'],
                'language_probability': audio_result['transcription']['language_probability']
            },
            'audio_features': audio_features,
            'sentiment_analysis': {
                'text_sentiment': text_sentiment,
                'text_category': text_category,
                'audio_sentiment': audio_signals.overall_audio_sentiment,
                'combined_sentiment': combined_sentiment,
                'combined_category': combined_category,
                'confidence': confidence,
                'audio_signals': {
                    'energy': audio_signals.energy_signal,
                    'pitch': audio_signals.pitch_signal,
                    'speaking_rate': audio_signals.speaking_rate_signal
                }
            },
            'metadata': {
                **metadata,
                'text_model_inference_ms': text_result['processing_time_ms'],
                'text_weight': text_weight,
                'audio_weight': audio_weight
            }
        }
        
        logger.info("\n" + "="*70)
        logger.info("✅ ANALYSIS COMPLETE")
        logger.info("="*70)
        
        return result
    
    def analyze_and_print(self, audio_path: str, **kwargs) -> Dict:
        """
        Analyze complaint and print formatted results.
        
        Args:
            audio_path: Path to audio file
            **kwargs: Additional arguments for analyze_complaint()
        
        Returns:
            Analysis result dict
        """
        result = self.analyze_complaint(audio_path, **kwargs)
        
        print("\n" + "="*70)
        print("📊 COMPLAINT ANALYSIS RESULTS")
        print("="*70)
        
        if result['status'] == 'success':
            # Transcription
            print("\n📝 TRANSCRIPTION:")
            print(f"   {result['transcription']['text']}")
            print(f"   Language: {result['transcription']['language']} ({result['transcription']['language_probability']:.0%})")
            
            # Sentiment
            print("\n💭 SENTIMENT ANALYSIS:")
            sent = result['sentiment_analysis']
            print(f"   Text Sentiment:     {sent['text_sentiment']:+.3f} ({sent['text_category']})")
            print(f"   Audio Sentiment:    {sent['audio_sentiment']:+.3f}")
            print(f"   Combined Sentiment: {sent['combined_sentiment']:+.3f} ({sent['combined_category']})")
            print(f"   Confidence:         {sent['confidence']:.0%}")
            
            # Audio signals
            print("\n🎙️ AUDIO SIGNALS:")
            signals = sent['audio_signals']
            print(f"   Energy:        {signals['energy']:+.3f}")
            print(f"   Pitch:         {signals['pitch']:+.3f}")
            print(f"   Speaking Rate: {signals['speaking_rate']:+.3f}")
            
            # Performance
            print("\n⚡ PERFORMANCE:")
            meta = result['metadata']
            print(f"   Audio Duration:   {meta['duration_seconds']:.2f}s")
            print(f"   Text Inference:   {meta['text_model_inference_ms']:.1f}ms")
            
        elif result['status'] == 'warning':
            print(f"\n⚠️ WARNING: {result['message']}")
        else:
            print(f"\n❌ ERROR: {result.get('error', 'Unknown error')}")
        
        print("\n" + "="*70)
        
        return result


def main():
    """Command-line interface"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Unified Audio Complaint Analyzer",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python unified_complaint_analyzer.py recording.wav models/sentiment-production
  python unified_complaint_analyzer.py audio.mp3 models/sentiment-production --skip-vad
  python unified_complaint_analyzer.py complaint.wav models/sentiment-production --text-weight 0.8
        """
    )
    
    parser.add_argument('audio_file', help='Path to audio file')
    parser.add_argument('model_path', help='Path to RoBERTa sentiment model')
    parser.add_argument('--skip-vad', action='store_true', help='Skip voice activity detection')
    parser.add_argument('--text-weight', type=float, default=0.7, help='Weight for text sentiment (0-1)')
    parser.add_argument('--audio-weight', type=float, default=0.3, help='Weight for audio sentiment (0-1)')
    parser.add_argument('--output', help='Save results to JSON file')
    
    args = parser.parse_args()
    
    # Validate weights
    if not np.isclose(args.text_weight + args.audio_weight, 1.0):
        print(f"❌ Error: Weights must sum to 1.0, got {args.text_weight + args.audio_weight}")
        sys.exit(1)
    
    # Check files exist
    if not Path(args.audio_file).exists():
        print(f"❌ Error: Audio file not found: {args.audio_file}")
        sys.exit(1)
    
    if not Path(args.model_path).exists():
        print(f"❌ Error: Model path not found: {args.model_path}")
        sys.exit(1)
    
    # Initialize analyzer
    analyzer = UnifiedComplaintAnalyzer(
        text_model_path=args.model_path,
        sample_rate=16000,
        vad_aggressiveness=2
    )
    
    # Analyze
    result = analyzer.analyze_and_print(
        audio_path=args.audio_file,
        skip_vad=args.skip_vad,
        text_weight=args.text_weight,
        audio_weight=args.audio_weight
    )
    
    # Save to file if requested
    if args.output:
        output_path = Path(args.output)
        with open(output_path, 'w') as f:
            json.dump(result, f, indent=2)
        print(f"\n💾 Results saved to: {output_path}")


if __name__ == "__main__":
    import numpy as np
    main()
