"""
Multi-Task Data Preparation

Generates THREE proxy labels:
1. Sentiment: -1 to +1
2. Urgency: 0 to 1  
3. Keywords: Binary vector [0,1,0,1,...] for 50 keywords

This REPLACES your current data_preparation.py
"""

import pandas as pd
import numpy as np
from pathlib import Path
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Import keyword vocabulary
from model_architecture_UPDATED import get_keyword_vocabulary


# ==============================================================================
# PROXY LABEL GENERATION
# ==============================================================================

class ProxyLabelGenerator:
    """
    Generate proxy labels for all 3 tasks using rule-based analysis.
    """
    
    def __init__(self):
        self.keyword_vocab = get_keyword_vocabulary()
        
        # Sentiment lexicon
        self.sentiment_words = {
            'strong_negative': [
                'unacceptable', 'outrageous', 'ridiculous', 'disgraceful',
                'terrible', 'horrible', 'worst', 'disgusting', 'furious',
                'angry', 'livid', 'enraged', 'pathetic', 'shameful'
            ],
            'moderate_negative': [
                'broken', 'failed', 'not working', 'issue', 'problem',
                'malfunction', 'defective', 'damaged', 'faulty', 'error'
            ],
            'dissatisfaction': [
                'disappointed', 'frustrated', 'unhappy', 'dissatisfied',
                'upset', 'concerned', 'worried', 'annoyed', 'bothered'
            ],
            'positive': [
                'thank', 'appreciate', 'excellent', 'great', 'wonderful',
                'satisfied', 'happy', 'pleased', 'good', 'helpful', 'quick'
            ]
        }
        
        # Urgency lexicon
        self.urgency_words = {
            'critical': [
                'emergency', 'urgent', 'immediately', 'ASAP', 'critical',
                'dangerous', 'safety', 'hazard', 'risk', 'flooding',
                'fire', 'gas leak', 'no power', 'complete failure'
            ],
            'high': [
                'soon', 'quickly', 'today', 'now', 'can\'t wait',
                'need help', 'losing business', 'affecting operations',
                'customers complaining', 'can\'t work'
            ],
            'time_pressure': [
                'three days', 'a week', 'days', 'weeks', 'for days',
                'since monday', 'all week', 'several days'
            ],
            'escalation': [
                'third time', 'multiple times', 'reported before',
                'still not fixed', 'called again', 'manager', 'escalate'
            ]
        }
        
        logger.info(f"✓ ProxyLabelGenerator initialized")
        logger.info(f"  - {len(self.keyword_vocab)} keywords")
        logger.info(f"  - Sentiment words: {sum(len(v) for v in self.sentiment_words.values())}")
        logger.info(f"  - Urgency words: {sum(len(v) for v in self.urgency_words.values())}")
    
    def generate_sentiment(self, text: str) -> float:
        """
        Generate sentiment score from text.
        
        Returns: -1 (very negative) to +1 (very positive)
        """
        text_lower = text.lower()
        
        # Count sentiment indicators
        strong_neg = sum(1 for w in self.sentiment_words['strong_negative'] if w in text_lower)
        mod_neg = sum(1 for w in self.sentiment_words['moderate_negative'] if w in text_lower)
        dissatisfied = sum(1 for w in self.sentiment_words['dissatisfaction'] if w in text_lower)
        positive = sum(1 for w in self.sentiment_words['positive'] if w in text_lower)
        
        # Calculate score
        score = 0.0
        score -= strong_neg * 0.35
        score -= mod_neg * 0.20
        score -= dissatisfied * 0.15
        score += positive * 0.30
        
        # Clip to [-1, 1]
        return float(np.clip(score, -1.0, 1.0))
    
    def generate_urgency(self, text: str) -> float:
        """
        Generate urgency score from text.
        
        Returns: 0 (not urgent) to 1 (critical)
        """
        text_lower = text.lower()
        
        # Count urgency indicators
        critical = sum(1 for w in self.urgency_words['critical'] if w in text_lower)
        high = sum(1 for w in self.urgency_words['high'] if w in text_lower)
        time_pressure = sum(1 for w in self.urgency_words['time_pressure'] if w in text_lower)
        escalation = sum(1 for w in self.urgency_words['escalation'] if w in text_lower)
        
        # Calculate score (baseline 0.3 = any complaint has some urgency)
        score = 0.3
        score += critical * 0.5      # Critical words → max urgency
        score += high * 0.25          # High urgency words
        score += time_pressure * 0.15 # Time mentioned → more urgent
        score += escalation * 0.20    # Escalation → higher urgency
        
        # Clip to [0, 1]
        return float(np.clip(score, 0.0, 1.0))
    
    def generate_keywords(self, text: str) -> list:
        """
        Extract which keywords are present.
        
        Returns: List of indices (0-49) of present keywords
        """
        text_lower = text.lower()
        present = []
        
        for idx, keyword in enumerate(self.keyword_vocab):
            if keyword.lower() in text_lower:
                present.append(idx)
        
        return present


# ==============================================================================
# DATASET PREPARATION
# ==============================================================================

def prepare_dataset(
    input_csv: str,
    output_dir: str = 'data/processed',
    sample_size: int = None
):
    """
    Prepare dataset with multi-task proxy labels.
    
    Args:
        input_csv: Path to CSV with 'transcript' column
        output_dir: Where to save processed data
        sample_size: Optional sample size (for testing)
    
    Returns:
        DataFrame with proxy labels
    """
    logger.info("="*70)
    logger.info("Multi-Task Data Preparation")
    logger.info("="*70)
    
    # Load data
    logger.info(f"\n📂 Loading: {input_csv}")
    df = pd.read_csv(input_csv)
    logger.info(f"✓ Loaded {len(df)} records")
    
    if 'transcript' not in df.columns:
        raise ValueError("❌ CSV must have 'transcript' column")
    
    # Sample if requested
    if sample_size and sample_size < len(df):
        logger.info(f"\n🔀 Sampling {sample_size} records...")
        df = df.sample(n=sample_size, random_state=42).reset_index(drop=True)
    
    # Generate labels
    logger.info(f"\n🏷️ Generating proxy labels for {len(df)} samples...")
    generator = ProxyLabelGenerator()
    
    sentiments = []
    urgencies = []
    keywords_list = []
    
    for idx, row in df.iterrows():
        if (idx + 1) % 100 == 0:
            logger.info(f"  Processed: {idx+1}/{len(df)}")
        
        text = str(row['transcript'])
        
        sentiments.append(generator.generate_sentiment(text))
        urgencies.append(generator.generate_urgency(text))
        keywords_list.append(generator.generate_keywords(text))
    
    # Add to dataframe
    df['proxy_sentiment'] = sentiments
    df['proxy_urgency'] = urgencies
    df['proxy_keywords'] = keywords_list
    
    # Convert keyword lists to string for CSV storage
    df['proxy_keywords_str'] = df['proxy_keywords'].apply(
        lambda x: ','.join(map(str, x)) if x else ''
    )
    
    logger.info(f"✓ Generated labels")
    
    # Log statistics
    _log_statistics(df)
    
    # Save
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    output_file = output_path / f"processed_multi_task_n{len(df)}.csv"
    
    # Save (drop list column, keep string version)
    df_save = df.drop(columns=['proxy_keywords'])
    df_save.to_csv(output_file, index=False)
    
    logger.info(f"\n💾 Saved to: {output_file}")
    logger.info(f"   Columns: {list(df_save.columns)}")
    
    logger.info("\n" + "="*70)
    logger.info("✅ Data preparation complete!")
    logger.info("="*70)
    
    return df


def _log_statistics(df: pd.DataFrame):
    """Log label statistics"""
    logger.info("\n📊 Proxy Label Statistics:")
    
    # Sentiment
    logger.info(f"\n  Sentiment:")
    logger.info(f"    Mean: {df['proxy_sentiment'].mean():.3f}")
    logger.info(f"    Std:  {df['proxy_sentiment'].std():.3f}")
    logger.info(f"    Range: [{df['proxy_sentiment'].min():.3f}, {df['proxy_sentiment'].max():.3f}]")
    
    neg = (df['proxy_sentiment'] < -0.2).sum()
    neu = ((df['proxy_sentiment'] >= -0.2) & (df['proxy_sentiment'] <= 0.2)).sum()
    pos = (df['proxy_sentiment'] > 0.2).sum()
    logger.info(f"    Distribution:")
    logger.info(f"      Negative: {neg} ({neg/len(df)*100:.1f}%)")
    logger.info(f"      Neutral:  {neu} ({neu/len(df)*100:.1f}%)")
    logger.info(f"      Positive: {pos} ({pos/len(df)*100:.1f}%)")
    
    # Urgency
    logger.info(f"\n  Urgency:")
    logger.info(f"    Mean: {df['proxy_urgency'].mean():.3f}")
    logger.info(f"    Std:  {df['proxy_urgency'].std():.3f}")
    logger.info(f"    Range: [{df['proxy_urgency'].min():.3f}, {df['proxy_urgency'].max():.3f}]")
    
    low = (df['proxy_urgency'] < 0.4).sum()
    med = ((df['proxy_urgency'] >= 0.4) & (df['proxy_urgency'] < 0.7)).sum()
    high = (df['proxy_urgency'] >= 0.7).sum()
    logger.info(f"    Distribution:")
    logger.info(f"      Low:    {low} ({low/len(df)*100:.1f}%)")
    logger.info(f"      Medium: {med} ({med/len(df)*100:.1f}%)")
    logger.info(f"      High:   {high} ({high/len(df)*100:.1f}%)")
    
    # Keywords
    logger.info(f"\n  Keywords:")
    avg_keywords = df['proxy_keywords'].apply(len).mean()
    max_keywords = df['proxy_keywords'].apply(len).max()
    logger.info(f"    Average per sample: {avg_keywords:.1f}")
    logger.info(f"    Max in one sample:  {max_keywords}")


# ==============================================================================
# CLI
# ==============================================================================

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("\nUsage: python data_preparation_UPDATED.py <input_csv> [sample_size]")
        print("\nExample:")
        print("  python data_preparation_UPDATED.py data/raw/Enhanced.csv 1000")
        print()
        sys.exit(1)
    
    input_csv = sys.argv[1]
    sample_size = int(sys.argv[2]) if len(sys.argv) > 2 else None
    
    df = prepare_dataset(
        input_csv=input_csv,
        output_dir='data/processed',
        sample_size=sample_size
    )
    
    print(f"\n✅ Complete! Processed {len(df)} records")
