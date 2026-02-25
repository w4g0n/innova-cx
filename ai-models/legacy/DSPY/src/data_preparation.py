"""
Data Preparation Module for InnovaCX Signal Extraction

Generates proxy labels for sentiment and urgency from unlabeled transcripts.

Principles Applied:
- Fail-Fast: Validate inputs immediately with guard clauses
- Parse Don't Validate: Transform to validated types (dataclasses)
- Single Responsibility: Each function does ONE thing
- Immutability: Frozen dataclasses for lexicons
- Observability: Structured logging with emojis and timing
- Design by Contract: Explicit preconditions and postconditions
- KISS: Simple, straightforward logic
"""

import pandas as pd
import numpy as np
import re
import time
from pathlib import Path
from typing import List, Optional
from dataclasses import dataclass
import logging

# Structured logging with observability
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-7s | %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)


# ==============================================================================
# DOMAIN TYPES (Parse, Don't Validate)
# ==============================================================================

@dataclass(frozen=True)  # Immutability
class SentimentLexicon:
    """Immutable sentiment word lists. Validated at construction."""
    
    strong_negative: tuple[str, ...]
    moderate_negative: tuple[str, ...]
    dissatisfaction: tuple[str, ...]
    positive: tuple[str, ...]
    neutral_cooperative: tuple[str, ...]
    
    def __post_init__(self):
        """Fail-fast: Design by Contract"""
        if not all([
            self.strong_negative,
            self.moderate_negative,
            self.dissatisfaction,
            self.positive,
            self.neutral_cooperative
        ]):
            raise ValueError("❌ All sentiment categories must be non-empty")


@dataclass(frozen=True)
class UrgencyLexicon:
    """Immutable urgency keyword lists."""
    
    high_urgency: tuple[str, ...]
    medium_urgency: tuple[str, ...]
    low_urgency: tuple[str, ...]
    
    def __post_init__(self):
        """Fail-fast validation"""
        if not all([self.high_urgency, self.medium_urgency, self.low_urgency]):
            raise ValueError("❌ All urgency categories must be non-empty")


@dataclass
class ProxyLabel:
    """
    Validated proxy label output.
    Type proves validity - if you have this object, scores are valid.
    """
    
    sentiment: float
    urgency: float
    keywords: List[str]
    
    def __post_init__(self):
        """Design by Contract: Enforce invariants"""
        # Guard clauses for early validation
        if not -1.0 <= self.sentiment <= 1.0:
            raise ValueError(
                f"❌ Sentiment must be in [-1, 1], got {self.sentiment}"
            )
        
        if not 0.0 <= self.urgency <= 1.0:
            raise ValueError(
                f"❌ Urgency must be in [0, 1], got {self.urgency}"
            )
        
        if not isinstance(self.keywords, list):
            raise TypeError(
                f"❌ Keywords must be list, got {type(self.keywords)}"
            )


# ==============================================================================
# PROXY LABEL GENERATOR
# ==============================================================================

class ProxyLabelGenerator:
    """
    Generates validated proxy labels from transcripts.
    
    Single Responsibility: Only generates labels, nothing else.
    Immutability: Uses frozen lexicons.
    """
    
    def __init__(self):
        """Initialize with immutable lexicons"""
        self._sentiment_lexicon = self._create_sentiment_lexicon()
        self._urgency_lexicon = self._create_urgency_lexicon()
        logger.info("✓ Initialized ProxyLabelGenerator")
    
    def _create_sentiment_lexicon(self) -> SentimentLexicon:
        """
        Single Responsibility: Create sentiment lexicon.
        Returns immutable, validated lexicon.
        """
        return SentimentLexicon(
            strong_negative=tuple([
                'unacceptable', 'frustrated', 'disappointed', 'upset',
                'breach', 'legal action', 'violation', 'extremely frustrating',
                'completely unacceptable', 'very upset'
            ]),
            moderate_negative=tuple([
                'inconvenient', 'concerning', 'serious', 'uncomfortable',
                'delays', 'not ideal', 'complaining', 'affecting', 'impacting'
            ]),
            dissatisfaction=tuple([
                'third time', 'been calling for days', 'nothing has been done',
                'reported last week', 'still waiting', 'no response'
            ]),
            positive=tuple([
                'appreciate', 'perfect', 'thank you', 'great', 'excellent',
                'satisfied', 'that works', 'sounds good', 'wonderful'
            ]),
            neutral_cooperative=tuple([
                'can you', 'please', 'would be helpful',
                'when convenient', 'when possible', 'thank'
            ])
        )
    
    def _create_urgency_lexicon(self) -> UrgencyLexicon:
        """Single Responsibility: Create urgency lexicon"""
        return UrgencyLexicon(
            high_urgency=tuple([
                'urgent', 'immediately', 'asap', 'emergency', 'critical',
                'escalate immediately', 'right now', 'cannot wait',
                'need this now', 'serious issue'
            ]),
            medium_urgency=tuple([
                'soon', 'quickly', 'as soon as possible', 'need this fixed',
                'impacting business', 'affecting operations', 'quickly please'
            ]),
            low_urgency=tuple([
                'when you can', 'when convenient', 'when possible',
                'not urgent', 'no rush', 'whenever'
            ])
        )
    
    def generate(self, row: pd.Series) -> ProxyLabel:
        """
        Generate validated proxy label from DataFrame row.
        
        Args:
            row: DataFrame row with transcript and metadata
            
        Returns:
            ProxyLabel: Validated label (type proves validity)
            
        Raises:
            ValueError: If row is invalid
        """
        # Fail-fast: Validate input
        if not isinstance(row, pd.Series):
            raise TypeError(f"❌ Expected pd.Series, got {type(row)}")
        
        if 'transcript' not in row:
            raise ValueError("❌ Row must contain 'transcript' column")
        
        # Generate components (delegated to specialized methods)
        sentiment = self._compute_sentiment(row)
        urgency = self._compute_urgency(row)
        keywords = self._extract_keywords(row)
        
        # Return validated type
        return ProxyLabel(
            sentiment=sentiment,
            urgency=urgency,
            keywords=keywords
        )
    
    def _compute_sentiment(self, row: pd.Series) -> float:
        """
        Single Responsibility: Compute sentiment score only.
        
        Combines linguistic signals with contextual adjustments.
        Returns score in [-1, 1].
        """
        transcript_lower = str(row['transcript']).lower()
        score = 0.0
        
        # Linguistic signals (primary)
        score += self._score_linguistic_sentiment(transcript_lower)
        
        # Contextual adjustments (secondary)
        score += self._score_contextual_sentiment(row)
        
        # Postcondition: Ensure valid range
        return float(np.clip(score, -1.0, 1.0))
    
    def _score_linguistic_sentiment(self, text: str) -> float:
        """
        Single Responsibility: Score text-based sentiment.
        Guard clause: Returns 0 for empty text.
        """
        # Guard clause
        if not text or not isinstance(text, str):
            return 0.0
        
        score = 0.0
        lex = self._sentiment_lexicon  # Shorter name for readability
        
        # Strong negative
        score -= 0.15 * sum(1 for phrase in lex.strong_negative if phrase in text)
        
        # Moderate negative
        score -= 0.10 * sum(1 for phrase in lex.moderate_negative if phrase in text)
        
        # Dissatisfaction
        score -= 0.20 * sum(1 for phrase in lex.dissatisfaction if phrase in text)
        
        # Positive
        score += 0.10 * sum(1 for phrase in lex.positive if phrase in text)
        
        # Neutral cooperative
        score += 0.05 * sum(1 for phrase in lex.neutral_cooperative if phrase in text)
        
        return score
    
    def _score_contextual_sentiment(self, row: pd.Series) -> float:
        """Single Responsibility: Score metadata-based sentiment"""
        score = 0.0
        
        # Issue severity adjustment
        if 'issue_severity' in row and pd.notna(row['issue_severity']):
            severity_scores = {
                'low': 0.05,
                'medium': 0.0,
                'high': -0.15,
                'critical': -0.30
            }
            score += severity_scores.get(row['issue_severity'], 0.0)
        
        # Business impact adjustment
        if 'business_impact' in row and pd.notna(row['business_impact']):
            impact_scores = {
                'low': 0.05,
                'medium': 0.0,
                'medium-high': -0.10,
                'high': -0.20
            }
            score += impact_scores.get(row['business_impact'], 0.0)
        
        # Recurring issues
        if row.get('is_recurring', False):
            score -= 0.20
        
        # Safety concerns
        if row.get('safety_concern', False):
            score -= 0.15
        
        # Tenant tier expectations
        if self._is_premium_high_severity(row):
            score -= 0.10
        elif self._is_vip_high_severity(row):
            score -= 0.15
        
        # Leasing inquiries are positive
        if row.get('call_category') == 'Leasing Inquiry':
            score += 0.20
        
        return score
    
    def _is_premium_high_severity(self, row: pd.Series) -> bool:
        """Guard clause pattern: Check specific condition"""
        return (
            row.get('tenant_tier') == 'Premium' and
            row.get('issue_severity') in ['high', 'critical']
        )
    
    def _is_vip_high_severity(self, row: pd.Series) -> bool:
        """Guard clause pattern: Check specific condition"""
        return (
            row.get('tenant_tier') == 'VIP' and
            row.get('issue_severity') in ['high', 'critical']
        )
    
    def _compute_urgency(self, row: pd.Series) -> float:
        """
        Single Responsibility: Compute urgency score only.
        Returns score in [0, 1].
        """
        transcript_lower = str(row['transcript']).lower()
        score = 0.0
        
        # Keyword-based urgency
        score += self._score_urgency_keywords(transcript_lower)
        
        # Context-based urgency
        score += self._score_urgency_context(row)
        
        # Postcondition: Ensure valid range
        return float(np.clip(score, 0.0, 1.0))
    
    def _score_urgency_keywords(self, text: str) -> float:
        """Single Responsibility: Score urgency from keywords"""
        # Guard clause
        if not text or not isinstance(text, str):
            return 0.0
        
        score = 0.0
        lex = self._urgency_lexicon
        
        score += 0.30 * sum(1 for kw in lex.high_urgency if kw in text)
        score += 0.15 * sum(1 for kw in lex.medium_urgency if kw in text)
        score -= 0.20 * sum(1 for kw in lex.low_urgency if kw in text)
        
        return score
    
    def _score_urgency_context(self, row: pd.Series) -> float:
        """Single Responsibility: Score urgency from context"""
        score = 0.0
        
        # Severity-based urgency
        if 'issue_severity' in row and pd.notna(row['issue_severity']):
            severity_urgency = {
                'critical': 0.40,
                'high': 0.25,
                'medium': 0.10,
                'low': 0.0
            }
            score += severity_urgency.get(row['issue_severity'], 0.0)
        
        # Safety = urgent
        if row.get('safety_concern', False):
            score += 0.30
        
        # Recurring = more urgent
        if row.get('is_recurring', False):
            score += 0.15
        
        # High business impact
        if row.get('business_impact') in ['high', 'medium-high']:
            score += 0.15
        
        return score
    
    def _extract_keywords(self, row: pd.Series) -> List[str]:
        """
        Single Responsibility: Extract keywords only.
        
        Returns deduplicated list of domain-specific keywords.
        """
        keywords = []
        
        # Structured field keywords
        keywords.extend(self._extract_structured_keywords(row))
        
        # Transcript-based keywords
        if 'transcript' in row and pd.notna(row['transcript']):
            keywords.extend(self._extract_transcript_keywords(row['transcript']))
        
        # Deduplicate and return
        return list(set(keywords))
    
    def _extract_structured_keywords(self, row: pd.Series) -> List[str]:
        """Extract keywords from structured fields"""
        keywords = []
        
        for field in ['issue_type', 'location', 'asset_type']:
            if field in row and pd.notna(row[field]):
                keywords.append(str(row[field]))
        
        return keywords
    
    def _extract_transcript_keywords(self, transcript: str) -> List[str]:
        """Extract keywords from transcript text"""
        keywords = []
        
        # Complaint patterns
        patterns = [
            r'(air conditioning|AC|cooling|heating)',
            r'(elevator|lift)',
            r'(power outage|electricity|blackout)',
            r'(water|leak|flood|drainage)',
            r'(parking|gate)',
            r'(internet|WiFi|connectivity)',
            r'(lighting|lights)',
            r'(security|alarm|fire)',
            r'(noise|disturbance)',
            r'(cleaning|maintenance)'
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, transcript, re.IGNORECASE)
            keywords.extend(matches)
        
        # Time indicators
        time_pattern = r'(\d+\s+(?:days|weeks|months|hours)|yesterday|last week)'
        time_matches = re.findall(time_pattern, transcript, re.IGNORECASE)
        keywords.extend(time_matches)
        
        return keywords


# ==============================================================================
# PUBLIC API
# ==============================================================================

def prepare_dataset(
    input_csv: str,
    output_dir: str = 'data/processed',
    sample_size: Optional[int] = None,
    stratify_by: Optional[List[str]] = None
) -> pd.DataFrame:
    """
    Load dataset, generate proxy labels, save processed data.
    
    Design by Contract:
    - Precondition: input_csv must exist
    - Postcondition: Returns df with proxy labels
    
    Args:
        input_csv: Path to input CSV file
        output_dir: Directory to save processed data
        sample_size: If specified, create smaller sample
        stratify_by: Columns to stratify sampling by
        
    Returns:
        DataFrame with proxy labels added
        
    Raises:
        FileNotFoundError: If input_csv doesn't exist
        ValueError: If sampling fails
    """
    start_time = time.perf_counter()
    
    # Fail-fast: Validate preconditions
    input_path = Path(input_csv)
    if not input_path.exists():
        raise FileNotFoundError(f"❌ Input file not found: {input_csv}")
    
    logger.info(f"📂 Loading dataset from {input_csv}")
    df = pd.read_csv(input_csv)
    logger.info(f"✓ Loaded {len(df)} records")
    
    # Sample if requested
    if sample_size and sample_size < len(df):
        df = _create_sample(df, sample_size, stratify_by)
    
    # Generate proxy labels
    logger.info("🔧 Generating proxy labels...")
    df = _add_proxy_labels(df)
    
    # Log statistics
    _log_label_statistics(df)
    
    # Save processed data
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    output_file = output_path / f"processed_n{len(df)}.csv"
    df.to_csv(output_file, index=False)
    
    elapsed_sec = time.perf_counter() - start_time
    logger.info(f"✅ Saved to {output_file} ({elapsed_sec:.1f}s total)")
    
    return df


def _create_sample(
    df: pd.DataFrame,
    sample_size: int,
    stratify_by: Optional[List[str]]
) -> pd.DataFrame:
    """
    Single Responsibility: Create stratified or random sample.
    Guard clause: Returns original if sample_size >= len(df)
    """
    # Guard clause
    if sample_size >= len(df):
        return df
    
    if stratify_by and all(col in df.columns for col in stratify_by):
        # Stratified sampling
        sampled = df.groupby(stratify_by, group_keys=False).apply(
            lambda x: x.sample(
                min(len(x), sample_size // len(df.groupby(stratify_by))),
                random_state=42
            )
        ).reset_index(drop=True)
        logger.info(f"✓ Created stratified sample: {len(sampled)} records")
    else:
        # Random sampling
        sampled = df.sample(n=sample_size, random_state=42)
        logger.info(f"✓ Created random sample: {len(sampled)} records")
    
    return sampled


def _add_proxy_labels(df: pd.DataFrame) -> pd.DataFrame:
    """
    Single Responsibility: Add proxy labels to DataFrame.
    Observability: Times the operation.
    """
    start_time = time.perf_counter()
    generator = ProxyLabelGenerator()
    
    # Generate labels for each row
    labels = [generator.generate(row) for _, row in df.iterrows()]
    
    # Unpack into columns
    df['proxy_sentiment'] = [label.sentiment for label in labels]
    df['proxy_urgency'] = [label.urgency for label in labels]
    df['keywords'] = [label.keywords for label in labels]
    
    elapsed_sec = time.perf_counter() - start_time
    logger.info(f"✓ Generated labels in {elapsed_sec:.1f}s")
    
    return df


def _log_label_statistics(df: pd.DataFrame) -> None:
    """
    Single Responsibility: Log proxy label statistics.
    Observability principle: Make data visible.
    """
    logger.info("\n📊 Proxy Label Statistics:")
    logger.info(f"  Sentiment → μ={df['proxy_sentiment'].mean():.3f} "
                f"σ={df['proxy_sentiment'].std():.3f}")
    logger.info(f"  Sentiment → min={df['proxy_sentiment'].min():.3f} "
                f"max={df['proxy_sentiment'].max():.3f}")
    logger.info(f"  Urgency   → μ={df['proxy_urgency'].mean():.3f} "
                f"σ={df['proxy_urgency'].std():.3f}")
    
    # Distribution analysis
    neg = (df['proxy_sentiment'] < -0.2).sum()
    neu = ((df['proxy_sentiment'] >= -0.2) & (df['proxy_sentiment'] <= 0.2)).sum()
    pos = (df['proxy_sentiment'] > 0.2).sum()
    
    logger.info(f"\n📈 Sentiment Distribution:")
    logger.info(f"  Negative (<-0.2): {neg} ({neg/len(df)*100:.1f}%)")
    logger.info(f"  Neutral [-0.2,0.2]: {neu} ({neu/len(df)*100:.1f}%)")
    logger.info(f"  Positive (>0.2): {pos} ({pos/len(df)*100:.1f}%)")


# ==============================================================================
# CLI ENTRY POINT
# ==============================================================================

if __name__ == "__main__":
    import sys
    
    # Guard clause: Check arguments
    if len(sys.argv) < 2:
        print("Usage: python data_preparation.py <input_csv> [sample_size]")
        print("Example: python data_preparation.py data/raw/Enhanced.csv 50")
        sys.exit(1)
    
    input_path = sys.argv[1]
    sample_size = int(sys.argv[2]) if len(sys.argv) > 2 else None
    
    # Execute
    df = prepare_dataset(
        input_csv=input_path,
        output_dir='data/processed',
        sample_size=sample_size,
        stratify_by=['call_category', 'issue_severity']
    )
    
    print(f"\n✅ Dataset preparation complete!")
    print(f"   Records: {len(df)}")
    print(f"   Output: data/processed/processed_n{len(df)}.csv")
