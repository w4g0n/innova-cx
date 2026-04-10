"""
=============================================================================
STEP 2: DATA AUGMENTATION & SYNTHESIS
=============================================================================

PURPOSE:
    After deduplication (Step 1), the dataset is clean but likely smaller.
    This step increases dataset size AND variety through controlled
    augmentation techniques that preserve semantic meaning.

    The goal is NOT just to make the dataset bigger — it is to force the
    model to learn GENERALIZABLE patterns rather than memorizing surface
    forms. Each augmentation technique targets a specific failure mode:

    1. SYNONYM REPLACEMENT → Teaches the model that "frustrated" and
       "irritated" carry the same sentiment signal, preventing it from
       being brittle to word choice.

    2. RANDOM WORD DELETION → Teaches robustness to incomplete input,
       which is critical because real Whisper transcriptions often drop
       words from noisy audio.

    3. RANDOM WORD INSERTION → Teaches the model to ignore filler words
       and focus on sentiment-bearing terms, simulating natural speech
       patterns where people add "like", "you know", etc.

    4. SENTENCE SHUFFLE → For multi-sentence complaints, teaches that
       sentiment is about CONTENT not ORDER. A complaint that says
       "The AC broke. I'm furious." carries the same sentiment as
       "I'm furious. The AC broke."

    5. TEMPLATE-BASED SYNTHESIS → Fills gaps in the label distribution.
       If the dataset has very few positive-sentiment or very-high-urgency
       samples, we generate synthetic examples for those underrepresented
       categories to prevent class imbalance from biasing the model.

    6. ASR NOISE INJECTION → Simulates the kinds of errors that Whisper
       transcription introduces (homophones, dropped apostrophes, run-on
       words), making the model robust to the actual input it will receive
       in production.

CRITICAL DESIGN DECISION — LABEL VALIDATION:
    After every augmentation, we re-run the proxy label generator on the
    augmented text and compare the new label to the original. If the
    sentiment score shifts by more than MAX_LABEL_DRIFT (default 0.15),
    the augmented sample is DISCARDED. This prevents augmentation from
    creating label noise that would degrade model performance.

    This is only possible BECAUSE we use rule-based proxy labels rather
    than human annotations. We can re-compute labels cheaply and verify
    augmentation quality programmatically.

USAGE:
    python step2_augment.py <deduplicated_csv> [augmentation_factor]

    Example:
        python step2_augment.py data/processed/deduplicated_n500.csv 3

    augmentation_factor controls how many augmented variants per original
    (default: 3, meaning ~3x dataset size increase)

=============================================================================
"""

import pandas as pd
import numpy as np
import re
import random
from pathlib import Path
from typing import List, Tuple, Optional, Dict
from dataclasses import dataclass
import logging
import time
import json

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-7s | %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)


# ==============================================================================
# CONFIGURATION
# ==============================================================================

@dataclass
class AugmentationConfig:
    """
    Controls augmentation behavior.
    
    REASONING for defaults:
    - max_augments_per_sample=3: Produces ~3x dataset size. Going beyond 4x
      risks the model learning augmentation patterns rather than real text
      patterns. Academic literature (Wei & Zou, 2019 "EDA") recommends 1-4x.
    - max_label_drift=0.15: A sentiment shift of 0.15 on a [-1,1] scale is
      ~7.5% of the full range. Beyond this, the augmentation has changed
      the semantic meaning enough to invalidate the original label.
    - synonym_replace_pct=0.15: Replace ~15% of words with synonyms. Higher
      rates risk changing meaning; lower rates don't introduce enough variety.
    - word_delete_pct=0.10: Delete ~10% of words. Higher rates create
      incomprehensible text; lower rates don't test robustness.
    - word_insert_pct=0.10: Insert filler in ~10% of positions.
    """
    input_csv: str
    output_dir: str = 'data/processed'
    max_augments_per_sample: int = 3
    max_label_drift: float = 0.15
    synonym_replace_pct: float = 0.15
    word_delete_pct: float = 0.10
    word_insert_pct: float = 0.10
    random_seed: int = 42
    
    def __post_init__(self):
        if not Path(self.input_csv).exists():
            raise FileNotFoundError(f"❌ Input file not found: {self.input_csv}")
        if self.max_augments_per_sample < 1:
            raise ValueError("❌ max_augments_per_sample must be >= 1")
        if not 0.0 < self.max_label_drift < 1.0:
            raise ValueError("❌ max_label_drift must be in (0, 1)")


# ==============================================================================
# DOMAIN-SPECIFIC SYNONYM DICTIONARY
# ==============================================================================

# REASONING: We use a CURATED domain-specific synonym dictionary rather than
# WordNet because:
# 1. WordNet synonyms are too broad — it might replace "broken" with "broke"
#    (past tense of "break" as a financial term), which changes domain meaning
# 2. Complaint-domain synonyms need to preserve sentiment INTENSITY — we group
#    synonyms by approximate intensity level so "furious" maps to "livid" (both
#    high intensity) not "annoyed" (lower intensity)
# 3. This gives us full control over what substitutions are valid, eliminating
#    the risk of introducing nonsensical or off-domain text

DOMAIN_SYNONYMS = {
    # --- Negative emotions (HIGH intensity) ---
    'furious': ['livid', 'enraged', 'infuriated', 'irate'],
    'livid': ['furious', 'enraged', 'infuriated', 'irate'],
    'outrageous': ['appalling', 'shocking', 'atrocious', 'scandalous'],
    'unacceptable': ['intolerable', 'inexcusable', 'deplorable', 'unreasonable'],
    'terrible': ['awful', 'dreadful', 'horrendous', 'abysmal'],
    'horrible': ['awful', 'dreadful', 'horrendous', 'appalling'],
    'disgusting': ['revolting', 'repulsive', 'appalling', 'sickening'],
    'pathetic': ['deplorable', 'pitiful', 'woeful', 'lamentable'],
    
    # --- Negative emotions (MODERATE intensity) ---
    'frustrated': ['irritated', 'exasperated', 'aggravated', 'vexed'],
    'disappointed': ['let down', 'disheartened', 'displeased', 'dismayed'],
    'upset': ['distressed', 'troubled', 'bothered', 'perturbed'],
    'annoyed': ['irritated', 'bothered', 'vexed', 'agitated'],
    'unhappy': ['dissatisfied', 'discontented', 'displeased', 'discontent'],
    'concerned': ['worried', 'troubled', 'anxious', 'uneasy'],
    'inconvenient': ['troublesome', 'bothersome', 'problematic', 'disruptive'],
    
    # --- Problem descriptors ---
    'broken': ['malfunctioning', 'defective', 'non-functional', 'out of order'],
    'damaged': ['impaired', 'compromised', 'deteriorated', 'harmed'],
    'failed': ['malfunctioned', 'stopped working', 'ceased functioning', 'gave out'],
    'faulty': ['defective', 'flawed', 'malfunctioning', 'imperfect'],
    'leaking': ['dripping', 'seeping', 'oozing', 'trickling'],
    'noisy': ['loud', 'disruptive', 'clamorous', 'deafening'],
    
    # --- Urgency terms ---
    'immediately': ['right away', 'at once', 'without delay', 'promptly'],
    'urgent': ['pressing', 'critical', 'time-sensitive', 'imperative'],
    'emergency': ['crisis', 'critical situation', 'urgent matter', 'dire situation'],
    'quickly': ['promptly', 'swiftly', 'rapidly', 'without delay'],
    'soon': ['shortly', 'promptly', 'in short order', 'before long'],
    
    # --- Action requests ---
    'fix': ['repair', 'resolve', 'rectify', 'remedy'],
    'repair': ['fix', 'restore', 'mend', 'service'],
    'replace': ['swap out', 'exchange', 'substitute', 'renew'],
    'check': ['inspect', 'examine', 'look into', 'investigate'],
    'send': ['dispatch', 'deploy', 'assign', 'direct'],
    
    # --- Positive terms ---
    'excellent': ['outstanding', 'superb', 'exceptional', 'first-rate'],
    'great': ['wonderful', 'fantastic', 'terrific', 'splendid'],
    'helpful': ['useful', 'beneficial', 'supportive', 'accommodating'],
    'satisfied': ['content', 'pleased', 'happy', 'gratified'],
    'appreciate': ['value', 'am grateful for', 'am thankful for', 'recognize'],
    
    # --- Facility terms (Dubai CommerCity specific) ---
    'office': ['workspace', 'work area', 'business unit', 'suite'],
    'warehouse': ['storage facility', 'distribution center', 'storage unit', 'depot'],
    'building': ['facility', 'premises', 'structure', 'property'],
    'tenant': ['occupant', 'lessee', 'business owner', 'company'],
}

# Filler words that can be inserted without changing sentiment
# REASONING: These are conversational fillers that appear naturally in
# spoken complaints (transcribed by Whisper) but carry zero sentiment
# signal. Inserting them trains the model to ignore them.
FILLER_WORDS = [
    'basically', 'honestly', 'actually', 'literally', 'like',
    'you know', 'I mean', 'look', 'so', 'well', 'anyway',
    'essentially', 'clearly', 'obviously', 'frankly',
    'to be honest', 'the thing is', 'at this point',
]

# ASR (Automatic Speech Recognition) error patterns
# REASONING: These simulate real errors that Whisper introduces when
# transcribing noisy call center audio. Training on these patterns
# makes the model robust to imperfect transcription input — which is
# the ACTUAL input the model receives in production, not clean text.
ASR_ERROR_PATTERNS = {
    "can't": ["cant", "cannot", "can not"],
    "won't": ["wont", "will not", "wouldn't"],
    "don't": ["dont", "do not"],
    "isn't": ["isnt", "is not"],
    "wasn't": ["wasnt", "was not"],
    "doesn't": ["doesnt", "does not"],
    "haven't": ["havent", "have not"],
    "shouldn't": ["shouldnt", "should not"],
    "it's": ["its", "it is"],
    "that's": ["thats", "that is"],
    "there's": ["theres", "there is"],
    "they're": ["theyre", "they are", "their"],
    "we're": ["were", "we are"],
    "you're": ["youre", "you are", "your"],
    "I've": ["ive", "I have"],
    "air conditioning": ["air conditionin", "airconditioning", "ac"],
    "maintenance": ["maintanence", "maintainance", "maintenence"],
    "temperature": ["tempature", "temperture", "temprature"],
    "electricity": ["electricty", "electrisity"],
    "elevator": ["elevater", "elavator"],
}


# ==============================================================================
# AUGMENTATION TECHNIQUES
# ==============================================================================

class TextAugmenter:
    """
    Applies controlled text augmentation techniques.
    
    Each method is designed to preserve semantic meaning while introducing
    surface-level variation that prevents model memorization.
    """
    
    def __init__(self, config: AugmentationConfig):
        self.config = config
        self.rng = random.Random(config.random_seed)
        
        # Build reverse synonym lookup for faster access
        self._synonym_lookup = {}
        for word, synonyms in DOMAIN_SYNONYMS.items():
            self._synonym_lookup[word.lower()] = [s.lower() for s in synonyms]
    
    def synonym_replacement(self, text: str) -> str:
        """
        Replace a fraction of words with domain-specific synonyms.
        
        REASONING:
            This is the primary augmentation for teaching the model that
            sentiment is about MEANING not specific WORDS. If the model
            only ever sees "frustrated" in negative contexts, it learns
            a brittle word-level association. By also showing "irritated",
            "exasperated", and "aggravated" in the same contexts, the model
            learns the underlying concept of moderate negative emotion.
            
            We replace words probabilistically (not all at once) because:
            1. Replacing too many words creates unnatural text
            2. The model should still see the original terms most of the time
            3. Partial replacement creates a gradient of variation
        
        Returns:
            Text with some words replaced by synonyms, or original if no
            replaceable words found.
        """
        words = text.split()
        if len(words) < 3:
            return text  # Too short to augment meaningfully
        
        n_replacements = max(1, int(len(words) * self.config.synonym_replace_pct))
        
        # Find replaceable positions
        replaceable = []
        for i, word in enumerate(words):
            word_clean = re.sub(r'[^\w\s]', '', word).lower()
            if word_clean in self._synonym_lookup:
                replaceable.append(i)
        
        if not replaceable:
            return text  # No replaceable words found
        
        # Select positions to replace
        n_to_replace = min(n_replacements, len(replaceable))
        positions = self.rng.sample(replaceable, n_to_replace)
        
        # Apply replacements
        new_words = words.copy()
        for pos in positions:
            original = words[pos]
            word_clean = re.sub(r'[^\w\s]', '', original).lower()
            
            if word_clean in self._synonym_lookup:
                synonym = self.rng.choice(self._synonym_lookup[word_clean])
                
                # Preserve capitalization pattern
                if original[0].isupper():
                    synonym = synonym.capitalize()
                if original.isupper():
                    synonym = synonym.upper()
                
                # Preserve trailing punctuation
                trailing_punct = ''
                if original and not original[-1].isalnum():
                    trailing_punct = original[-1]
                    synonym = synonym.rstrip('.,!?;:') + trailing_punct
                
                new_words[pos] = synonym
        
        return ' '.join(new_words)
    
    def random_word_deletion(self, text: str) -> str:
        """
        Randomly remove words from the text.
        
        REASONING:
            Deletion augmentation serves two purposes:
            1. ROBUSTNESS: Real Whisper transcriptions frequently drop words,
               especially in noisy audio. The model must handle incomplete input.
            2. FEATURE IMPORTANCE: By removing random words and seeing that the
               label stays similar, the model learns which words are truly
               sentiment-bearing vs. which are structural filler.
            
            We NEVER delete the first or last word because:
            - First word often establishes subject ("The AC...")
            - Last word often carries emotional emphasis ("...unacceptable!")
            - Deleting these would disproportionately change meaning
        """
        words = text.split()
        if len(words) <= 4:
            return text  # Too short — deletion would destroy meaning
        
        n_deletions = max(1, int(len(words) * self.config.word_delete_pct))
        
        # Eligible positions: not first, not last
        eligible = list(range(1, len(words) - 1))
        n_to_delete = min(n_deletions, len(eligible))
        positions_to_delete = set(self.rng.sample(eligible, n_to_delete))
        
        new_words = [w for i, w in enumerate(words) if i not in positions_to_delete]
        
        return ' '.join(new_words)
    
    def random_word_insertion(self, text: str) -> str:
        """
        Insert domain-neutral filler words at random positions.
        
        REASONING:
            Real spoken complaints (captured by call center audio → Whisper)
            contain natural speech fillers: "honestly", "you know", "like",
            "basically". These carry NO sentiment signal but appear frequently
            in real data.
            
            By inserting fillers during training, the model learns to:
            1. Not be distracted by filler words
            2. Maintain correct sentiment prediction despite noisy input
            3. Focus attention on sentiment-bearing terms
            
            We insert BETWEEN words (never at start/end) to maintain
            grammatical structure of the opening and closing.
        """
        words = text.split()
        if len(words) < 3:
            return text
        
        n_insertions = max(1, int(len(words) * self.config.word_insert_pct))
        
        new_words = words.copy()
        for _ in range(n_insertions):
            filler = self.rng.choice(FILLER_WORDS)
            # Insert at random interior position
            insert_pos = self.rng.randint(1, len(new_words) - 1)
            new_words.insert(insert_pos, filler)
        
        return ' '.join(new_words)
    
    def sentence_shuffle(self, text: str) -> str:
        """
        Shuffle the order of sentences within a transcript.
        
        REASONING:
            Multi-sentence complaints often follow a pattern:
            [Context] → [Problem] → [Emotion] → [Request]
            
            But sentiment is independent of sentence ORDER — a complaint
            is equally negative whether the emotional statement comes first
            or last. By shuffling sentence order, we teach the model that
            sentiment is a GLOBAL property of the text, not dependent on
            position.
            
            This is especially important because RoBERTa uses positional
            embeddings that inherently encode position information. Without
            this augmentation, the model might learn that "negative words
            appearing at position 50-60 indicate negative sentiment" rather
            than learning the words themselves are negative.
            
            We only apply this when there are 2+ sentences to shuffle.
        """
        # Split on sentence boundaries
        sentences = re.split(r'(?<=[.!?])\s+', text.strip())
        
        if len(sentences) < 2:
            return text  # Single sentence — nothing to shuffle
        
        # Shuffle
        shuffled = sentences.copy()
        self.rng.shuffle(shuffled)
        
        # Don't return if order didn't change
        if shuffled == sentences:
            # Force a swap of first and last
            shuffled[0], shuffled[-1] = shuffled[-1], shuffled[0]
        
        return ' '.join(shuffled)
    
    def asr_noise_injection(self, text: str) -> str:
        """
        Simulate Automatic Speech Recognition (Whisper) transcription errors.
        
        REASONING:
            In production, the sentiment model receives text FROM Whisper,
            not clean typed text. Whisper makes predictable errors:
            - Contractions get split or mangled ("can't" → "cant")
            - Homophones get swapped ("their" vs "they're")
            - Domain terms get misspelled ("maintenance" → "maintanence")
            - Punctuation is inconsistent or missing
            
            If the model is only trained on clean text, it will fail on
            Whisper output. By injecting these specific error patterns during
            training, we bridge the gap between training data and production
            data distribution.
            
            We apply errors probabilistically (not to every instance) to
            create a mixture of clean and noisy examples, which teaches
            the model to handle BOTH cases.
        """
        result = text
        
        for correct, errors in ASR_ERROR_PATTERNS.items():
            if correct.lower() in result.lower():
                # 30% chance of introducing this specific error
                if self.rng.random() < 0.30:
                    error = self.rng.choice(errors)
                    # Case-insensitive replacement
                    pattern = re.compile(re.escape(correct), re.IGNORECASE)
                    result = pattern.sub(error, result, count=1)
        
        # 20% chance: remove some punctuation (simulating Whisper's
        # inconsistent punctuation)
        if self.rng.random() < 0.20:
            # Remove commas (most commonly dropped by ASR)
            result = result.replace(',', '')
        
        return result
    
    def augment_single(self, text: str) -> List[str]:
        """
        Generate multiple augmented variants of a single transcript.
        
        REASONING for the technique selection strategy:
            Rather than applying all techniques to every sample, we randomly
            select 1-2 techniques per variant. This ensures:
            1. Each augmented sample is different from the others
            2. The model sees diverse augmentation patterns
            3. No single technique dominates the augmented data
            
            The techniques are ordered by "safety" (least likely to change
            meaning → most likely to change meaning). We weight safer
            techniques more heavily.
        
        Returns:
            List of augmented text variants
        """
        techniques = [
            (self.synonym_replacement, 0.30),    # 30% chance per variant
            (self.random_word_deletion, 0.20),    # 20% chance
            (self.random_word_insertion, 0.25),    # 25% chance
            (self.sentence_shuffle, 0.15),         # 15% chance
            (self.asr_noise_injection, 0.25),      # 25% chance
        ]
        
        variants = []
        attempts = 0
        max_attempts = self.config.max_augments_per_sample * 3  # Allow retries
        
        while len(variants) < self.config.max_augments_per_sample and attempts < max_attempts:
            attempts += 1
            
            # Apply 1-2 randomly selected techniques
            augmented = text
            n_techniques = self.rng.randint(1, 2)
            
            # Weighted selection of techniques
            selected = []
            for technique, weight in techniques:
                if self.rng.random() < weight:
                    selected.append(technique)
            
            if not selected:
                # Fallback: always apply at least synonym replacement
                selected = [self.synonym_replacement]
            
            # Apply selected techniques (limit to n_techniques)
            for technique in selected[:n_techniques]:
                augmented = technique(augmented)
            
            # Validate: augmented text must be different from original
            # and different from existing variants
            if (augmented != text and
                augmented not in variants and
                len(augmented.strip()) > 10):
                variants.append(augmented)
        
        return variants


# ==============================================================================
# TEMPLATE-BASED SYNTHESIS
# ==============================================================================

class TemplateSynthesizer:
    """
    Generate synthetic complaint transcripts from parameterized templates.
    
    REASONING:
        After deduplication and augmentation of existing data, there may still
        be gaps in the label distribution — particularly for:
        - Very positive sentiment (rare in complaint datasets)
        - Very high urgency (safety-critical complaints)
        - Low urgency inquiries (polite questions)
        - Specific complaint categories that were underrepresented
        
        Template synthesis fills these gaps by generating structurally valid
        complaints where we CONTROL the sentiment and urgency parameters.
        
        Each template has slots for:
        - EMOTION: Controls sentiment label
        - ISSUE: Provides domain context
        - DURATION: Controls urgency label
        - ESCALATION: Modifies urgency label
        - CLOSING: Reinforces sentiment direction
        
        The slot fillers are organized by intensity level so we can
        precisely target specific regions of the label space.
    """
    
    def __init__(self, seed: int = 42):
        self.rng = random.Random(seed)
        
        # --- TEMPLATES ---
        # Each template produces a different complaint STRUCTURE
        self.templates = [
            # Structure: Emotion → Problem → Duration → Request
            "I am {emotion} about the {issue} in my {asset}. This has been going on for {duration}. {closing}",
            
            # Structure: Problem → Emotion → Escalation → Request
            "The {issue} in our {asset} is {problem_state}. I am {emotion} because {escalation}. {closing}",
            
            # Structure: Direct complaint → Context → Impact
            "{greeting} I need to report a {issue} problem. The {issue} in {asset} has been {problem_state} for {duration}. {impact}. {closing}",
            
            # Structure: Escalation → Problem → Demand
            "This is the {nth_time} I am contacting you about the {issue} in my {asset}. It has been {duration} and {escalation}. {closing}",
            
            # Structure: Polite inquiry (for positive/neutral synthesis)
            "{greeting} I would like to inquire about {inquiry_topic}. {context}. {closing}",
            
            # Structure: Follow-up (moderate urgency)
            "I am following up on my previous complaint about the {issue}. It has been {duration} since I reported it and {status}. {closing}",
        ]
        
        # --- SLOT FILLERS organized by sentiment/urgency intensity ---
        
        self.emotions = {
            'very_negative': [
                'furious', 'livid', 'outraged', 'appalled', 'disgusted',
                'absolutely infuriated', 'extremely angry', 'beside myself'
            ],
            'negative': [
                'frustrated', 'disappointed', 'upset', 'unhappy', 'annoyed',
                'dissatisfied', 'displeased', 'concerned'
            ],
            'neutral': [
                'writing to report', 'contacting you regarding',
                'reaching out about', 'informing you about'
            ],
            'positive': [
                'pleased to note', 'happy to report', 'grateful for',
                'satisfied with', 'appreciative of', 'thankful for'
            ]
        }
        
        self.issues = [
            'air conditioning', 'heating system', 'elevator',
            'parking gate', 'water leak', 'power outage',
            'internet connectivity', 'lighting', 'security system',
            'cleaning service', 'noise from construction',
            'plumbing', 'fire alarm', 'ventilation',
            'drainage system', 'electrical outlet'
        ]
        
        self.assets = [
            'office', 'warehouse', 'retail space', 'unit',
            'workspace', 'building', 'floor', 'facility'
        ]
        
        self.durations = {
            'short': ['since yesterday', 'since this morning', 'for a few hours'],
            'medium': ['for three days', 'for almost a week', 'for several days', 'since Monday'],
            'long': ['for two weeks', 'for over a month', 'for several weeks', 'since last month'],
            'very_long': ['for three months', 'for over six weeks', 'since we moved in']
        }
        
        self.problem_states = [
            'completely non-functional', 'not working at all', 'broken',
            'malfunctioning', 'intermittently failing', 'making strange noises',
            'leaking badly', 'producing a strong smell', 'overheating'
        ]
        
        self.escalations = {
            'none': ['I just noticed it today', 'this is a new issue'],
            'mild': ['I mentioned this last week', 'I submitted a request earlier'],
            'moderate': [
                'nobody has responded to my previous complaint',
                'I have been waiting with no update',
                'there has been no progress on this'
            ],
            'severe': [
                'this is the third time I am calling about this',
                'nothing has been done despite multiple complaints',
                'I have escalated this twice already with no result',
                'I am considering involving legal counsel'
            ]
        }
        
        self.closings = {
            'very_negative': [
                'This is completely unacceptable and I demand immediate action.',
                'I expect this to be resolved within 24 hours or I will escalate further.',
                'This needs to be fixed immediately or there will be consequences.',
                'I am losing patience and expect a resolution today.'
            ],
            'negative': [
                'Please fix this as soon as possible.',
                'I would appreciate a prompt resolution.',
                'Kindly address this issue at your earliest convenience.',
                'I expect to hear back about this soon.'
            ],
            'neutral': [
                'Please let me know the status.',
                'I would appreciate an update on this matter.',
                'Could you please provide more information?',
                'Thank you for looking into this.'
            ],
            'positive': [
                'Thank you for the quick response last time.',
                'I appreciate your team handling this well.',
                'Great work on resolving the previous issue promptly.',
                'Thank you for the excellent service.'
            ]
        }
        
        self.greetings = [
            'Hello,', 'Hi,', 'Good morning,', 'Good afternoon,',
            'Dear support team,', 'To whom it may concern,',
        ]
        
        self.inquiry_topics = [
            'upgrading my workspace', 'available maintenance windows',
            'the schedule for building improvements', 'parking availability',
            'additional storage space', 'meeting room booking',
            'Wi-Fi upgrade options', 'extended office hours',
        ]
        
        self.nth_times = [
            'second time', 'third time', 'fourth time', 'fifth time'
        ]
        
        self.impacts = [
            'This is affecting our daily operations',
            'Our employees cannot work comfortably',
            'Clients have been complaining about this',
            'We are losing productivity because of this',
            'This creates a safety concern for our staff',
            'This is disrupting our business significantly'
        ]
        
        self.statuses = [
            'nothing has changed', 'the problem persists',
            'I have not received any update', 'the issue is getting worse',
            'there has been some improvement but it is not resolved',
            'the repair was attempted but it broke again'
        ]
    
    def synthesize_complaint(self, target_sentiment: str, target_urgency: str) -> str:
        """
        Generate a synthetic complaint targeting a specific sentiment/urgency region.
        
        REASONING:
            By controlling which slot fillers we select, we can generate
            complaints that will produce predictable proxy labels when
            run through the labeler. This lets us surgically fill gaps
            in the label distribution.
            
            target_sentiment: 'very_negative', 'negative', 'neutral', 'positive'
            target_urgency: 'low', 'medium', 'high', 'critical'
        
        Returns:
            Synthetic complaint transcript
        """
        # Map urgency to duration and escalation levels
        urgency_map = {
            'low': ('short', 'none'),
            'medium': ('medium', 'mild'),
            'high': ('long', 'moderate'),
            'critical': ('very_long', 'severe'),
        }
        
        duration_key, escalation_key = urgency_map.get(
            target_urgency, ('medium', 'mild')
        )
        
        # Select appropriate template based on sentiment
        if target_sentiment == 'positive':
            template_idx = 4  # Inquiry template
        elif target_sentiment == 'neutral':
            template_idx = self.rng.choice([4, 5])
        else:
            template_idx = self.rng.randint(0, 3)  # Complaint templates
        
        template = self.templates[template_idx]
        
        # Fill slots
        filled = template.format(
            emotion=self.rng.choice(self.emotions.get(target_sentiment, self.emotions['neutral'])),
            issue=self.rng.choice(self.issues),
            asset=self.rng.choice(self.assets),
            duration=self.rng.choice(self.durations[duration_key]),
            problem_state=self.rng.choice(self.problem_states),
            escalation=self.rng.choice(self.escalations[escalation_key]),
            closing=self.rng.choice(self.closings.get(target_sentiment, self.closings['neutral'])),
            greeting=self.rng.choice(self.greetings),
            nth_time=self.rng.choice(self.nth_times),
            inquiry_topic=self.rng.choice(self.inquiry_topics),
            context='We have been considering this for our team',
            impact=self.rng.choice(self.impacts),
            status=self.rng.choice(self.statuses),
        )
        
        return filled
    
    def generate_balanced_set(
        self,
        n_per_category: int,
        existing_distribution: Dict[str, int]
    ) -> List[Tuple[str, str, str]]:
        """
        Generate synthetic samples to balance the label distribution.
        
        REASONING:
            We analyze the existing distribution and generate MORE samples
            for underrepresented categories. This prevents the model from
            developing a bias toward the majority class.
            
            For example, if the dataset has:
            - 60% negative sentiment
            - 30% neutral sentiment
            - 10% positive sentiment
            
            We generate extra positive and neutral samples to bring the
            distribution closer to balanced, without overshooting (we cap
            at n_per_category to avoid overwhelming real data with synthetic).
        
        Returns:
            List of (transcript, target_sentiment, target_urgency) tuples
        """
        synthetic_samples = []
        
        sentiment_levels = ['very_negative', 'negative', 'neutral', 'positive']
        urgency_levels = ['low', 'medium', 'high', 'critical']
        
        for sentiment in sentiment_levels:
            for urgency in urgency_levels:
                category_key = f"{sentiment}_{urgency}"
                existing_count = existing_distribution.get(category_key, 0)
                
                # Generate enough to reach n_per_category
                n_needed = max(0, n_per_category - existing_count)
                
                for _ in range(n_needed):
                    transcript = self.synthesize_complaint(sentiment, urgency)
                    synthetic_samples.append((transcript, sentiment, urgency))
        
        logger.info(f"  Generated {len(synthetic_samples)} synthetic samples "
                    f"across {len(sentiment_levels)}×{len(urgency_levels)} categories")
        
        return synthetic_samples


# ==============================================================================
# ENHANCED PROXY LABEL GENERATOR (STEP 2 IMPROVEMENT)
# ==============================================================================

class EnhancedProxyLabelGenerator:
    """
    Improved proxy label generator with:
    1. Negation handling
    2. Intensifier awareness
    3. Position weighting
    4. Controlled label noise
    
    REASONING:
        The original ProxyLabelGenerator has a critical flaw that duplicates
        expose: it counts sentiment words flatly. The phrase "I am not satisfied"
        contains the word "satisfied" and would receive POSITIVE contribution,
        when the actual sentiment is NEGATIVE because of the negation.
        
        Similarly, "extremely frustrated" should score more negative than just
        "frustrated", but the original generator treats them identically.
        
        These improvements create more nuanced, continuous labels that give
        the model a richer signal to learn from.
    """
    
    # Sentiment lexicon (same as original for compatibility)
    STRONG_NEGATIVE = [
        'unacceptable', 'outrageous', 'ridiculous', 'disgraceful',
        'terrible', 'horrible', 'worst', 'disgusting', 'furious',
        'angry', 'livid', 'enraged', 'pathetic', 'shameful',
        'intolerable', 'inexcusable', 'deplorable', 'appalling',
        'atrocious', 'abysmal', 'dreadful', 'horrendous',
        'infuriated', 'irate', 'outraged', 'incensed'
    ]
    
    MODERATE_NEGATIVE = [
        'broken', 'failed', 'not working', 'issue', 'problem',
        'malfunction', 'defective', 'damaged', 'faulty', 'error',
        'malfunctioning', 'non-functional', 'out of order',
        'impaired', 'compromised', 'deteriorated', 'flawed'
    ]
    
    DISSATISFACTION = [
        'disappointed', 'frustrated', 'unhappy', 'dissatisfied',
        'upset', 'concerned', 'worried', 'annoyed', 'bothered',
        'irritated', 'exasperated', 'aggravated', 'vexed',
        'displeased', 'discontented', 'dismayed', 'troubled',
        'let down', 'disheartened', 'perturbed', 'agitated'
    ]
    
    POSITIVE = [
        'thank', 'appreciate', 'excellent', 'great', 'wonderful',
        'satisfied', 'happy', 'pleased', 'good', 'helpful', 'quick',
        'outstanding', 'superb', 'exceptional', 'fantastic', 'terrific',
        'grateful', 'thankful', 'splendid', 'first-rate',
        'accommodating', 'supportive', 'beneficial'
    ]
    
    # NEW: Negation words (within a 3-word window, flip sentiment)
    NEGATION_WORDS = [
        'not', 'no', 'never', 'neither', 'nor', 'nothing',
        'nowhere', 'nobody', "n't", 'nt', 'hardly', 'barely',
        'scarcely', 'without', 'lack', 'lacking', 'absent'
    ]
    
    # NEW: Intensifiers (multiply the sentiment score of the next word)
    INTENSIFIERS = {
        'very': 1.5, 'extremely': 2.0, 'incredibly': 2.0,
        'absolutely': 2.0, 'completely': 1.8, 'totally': 1.8,
        'utterly': 2.0, 'really': 1.3, 'quite': 1.2,
        'deeply': 1.5, 'highly': 1.5, 'thoroughly': 1.5,
        'immensely': 2.0, 'exceptionally': 1.8
    }
    
    # Urgency lexicon (same structure as original)
    URGENCY_CRITICAL = [
        'emergency', 'urgent', 'immediately', 'asap', 'critical',
        'dangerous', 'safety', 'hazard', 'risk', 'flooding',
        'fire', 'gas leak', 'no power', 'complete failure',
        'crisis', 'dire', 'imperative', 'life-threatening'
    ]
    
    URGENCY_HIGH = [
        'soon', 'quickly', 'today', 'now', "can't wait",
        'need help', 'losing business', 'affecting operations',
        'customers complaining', "can't work", 'promptly',
        'right away', 'without delay', 'swiftly'
    ]
    
    URGENCY_TIME_PRESSURE = [
        'three days', 'a week', 'days', 'weeks', 'for days',
        'since monday', 'all week', 'several days', 'two weeks',
        'over a month', 'several weeks', 'since last month',
        'three months', 'over six weeks'
    ]
    
    URGENCY_ESCALATION = [
        'third time', 'multiple times', 'reported before',
        'still not fixed', 'called again', 'manager', 'escalate',
        'second time', 'fourth time', 'fifth time',
        'nothing has been done', 'no response', 'no update'
    ]
    
    def __init__(self, label_noise_std: float = 0.04):
        """
        Args:
            label_noise_std: Standard deviation of Gaussian noise added to labels.
            
            REASONING for label_noise_std=0.04:
                On a [-1, 1] sentiment scale, σ=0.04 means 95% of noise values
                fall within ±0.08, which is 4% of the full range. This is enough
                to break the discrete clustering of identical scores (where many
                similar transcripts all map to exactly -0.35) while being small
                enough that it doesn't distort the actual label ordering.
                
                Without this noise, the model sees many training examples with
                label=exactly_0.3, which creates an artificial spike in the label
                distribution that the regression head tries to match, leading to
                predictions that cluster around a few discrete values rather than
                spanning the continuous range.
        """
        self.label_noise_std = label_noise_std
        self.rng = np.random.RandomState(42)
    
    def generate_sentiment(self, text: str) -> float:
        """
        Enhanced sentiment scoring with negation and intensifier awareness.
        """
        text_lower = text.lower()
        words = text_lower.split()
        
        score = 0.0
        
        # IMPROVEMENT 1: Negation-aware scoring
        # Check each sentiment word and look for negation in a 3-word window
        # REASONING: Negation typically precedes the word it modifies by 1-3
        # positions. "I am NOT satisfied" has 1-word gap. "I have never been
        # satisfied" has 2-word gap. Beyond 3 words, the negation likely
        # applies to a different clause.
        
        for i, word in enumerate(words):
            word_clean = re.sub(r'[^\w\s]', '', word)
            
            # Check if this word is negated (look back 3 words)
            is_negated = False
            for j in range(max(0, i - 3), i):
                prev_word = re.sub(r'[^\w\s]', '', words[j])
                if prev_word in self.NEGATION_WORDS:
                    is_negated = True
                    break
            
            # IMPROVEMENT 2: Check for intensifier (look back 1-2 words)
            # REASONING: Intensifiers typically immediately precede the word
            # they modify. "very frustrated" = 1 position. We check 2 positions
            # for cases like "I am very deeply frustrated".
            intensifier_multiplier = 1.0
            for j in range(max(0, i - 2), i):
                prev_word = re.sub(r'[^\w\s]', '', words[j])
                if prev_word in self.INTENSIFIERS:
                    intensifier_multiplier = max(
                        intensifier_multiplier,
                        self.INTENSIFIERS[prev_word]
                    )
            
            # Score the word
            word_score = 0.0
            
            if word_clean in [w.lower() for w in self.STRONG_NEGATIVE]:
                word_score = -0.35
            elif word_clean in [w.lower() for w in self.MODERATE_NEGATIVE]:
                word_score = -0.20
            elif word_clean in [w.lower() for w in self.DISSATISFACTION]:
                word_score = -0.15
            elif word_clean in [w.lower() for w in self.POSITIVE]:
                word_score = 0.30
            
            # Apply negation (flip sign)
            if is_negated and word_score != 0.0:
                word_score = -word_score * 0.8  # 0.8 because negation doesn't
                # fully invert intensity — "not great" is less negative than
                # "terrible", even though it flips "great" from positive
            
            # Apply intensifier
            word_score *= intensifier_multiplier
            
            score += word_score
        
        # Also check multi-word phrases (not captured by single-word scan)
        for phrase in self.STRONG_NEGATIVE:
            if ' ' in phrase and phrase in text_lower:
                score -= 0.35
        for phrase in self.DISSATISFACTION:
            if ' ' in phrase and phrase in text_lower:
                score -= 0.15
        
        # IMPROVEMENT 3: Position weighting
        # REASONING: In complaint text, people tend to state their strongest
        # emotions at the BEGINNING (opening salvo) and END (final demand)
        # of the message. The middle tends to be factual description.
        # We give 20% extra weight to the first and last quarter of words.
        n_words = len(words)
        if n_words >= 8:
            quarter = n_words // 4
            first_quarter = ' '.join(words[:quarter])
            last_quarter = ' '.join(words[-quarter:])
            
            # Additional scoring for emphasized positions
            for word_list, weight in [
                (self.STRONG_NEGATIVE, -0.07),
                (self.DISSATISFACTION, -0.04),
                (self.POSITIVE, 0.06)
            ]:
                for term in word_list:
                    if term in first_quarter or term in last_quarter:
                        score += weight  # Extra weight for position emphasis
        
        # Clip to valid range
        score = float(np.clip(score, -1.0, 1.0))
        
        # IMPROVEMENT 4: Add controlled noise
        # REASONING explained in __init__ docstring
        if self.label_noise_std > 0:
            noise = self.rng.normal(0, self.label_noise_std)
            score = float(np.clip(score + noise, -1.0, 1.0))
        
        return score
    
    def generate_urgency(self, text: str) -> float:
        """
        Enhanced urgency scoring.
        """
        text_lower = text.lower()
        
        # Baseline: any complaint has some inherent urgency
        score = 0.3
        
        # Critical urgency signals
        for term in self.URGENCY_CRITICAL:
            if term in text_lower:
                score += 0.5
        
        # High urgency signals
        for term in self.URGENCY_HIGH:
            if term in text_lower:
                score += 0.25
        
        # Time pressure signals
        for term in self.URGENCY_TIME_PRESSURE:
            if term in text_lower:
                score += 0.15
        
        # Escalation signals
        for term in self.URGENCY_ESCALATION:
            if term in text_lower:
                score += 0.20
        
        # Clip and add noise
        score = float(np.clip(score, 0.0, 1.0))
        
        if self.label_noise_std > 0:
            noise = self.rng.normal(0, self.label_noise_std)
            score = float(np.clip(score + noise, 0.0, 1.0))
        
        return score
    
    def generate_keywords(self, text: str) -> list:
        """
        Extract keyword indices from text.
        Uses the same KEYWORD_VOCABULARY as the model architecture.
        """
        # Import from the model architecture to stay in sync
        import sys
        import os
        _arch_path = os.path.join(
            os.path.dirname(__file__), '..', '..', 'ai-models',
            'MultiAgentPipeline', 'SentimentAnalysisAgent', 'src'
        )
        if _arch_path not in sys.path:
            sys.path.insert(0, _arch_path)
        from model_architecture import get_keyword_vocabulary
        keyword_vocab = get_keyword_vocabulary()
        
        text_lower = text.lower()
        present = []
        
        for idx, keyword in enumerate(keyword_vocab):
            if keyword.lower() in text_lower:
                present.append(idx)
        
        return present


# ==============================================================================
# DISTRIBUTION ANALYSIS
# ==============================================================================

def analyze_distribution(df: pd.DataFrame) -> Dict[str, int]:
    """
    Analyze the sentiment × urgency distribution of the dataset.
    
    REASONING:
        To know what synthetic samples to generate, we need to understand
        which regions of the label space are underrepresented. We bucket
        continuous sentiment/urgency into categorical bins and count.
    """
    distribution = {}
    
    for _, row in df.iterrows():
        sent = row.get('proxy_sentiment', 0)
        urg = row.get('proxy_urgency', 0.3)
        
        # Bucket sentiment
        if sent < -0.5:
            sent_cat = 'very_negative'
        elif sent < -0.1:
            sent_cat = 'negative'
        elif sent < 0.2:
            sent_cat = 'neutral'
        else:
            sent_cat = 'positive'
        
        # Bucket urgency
        if urg < 0.35:
            urg_cat = 'low'
        elif urg < 0.55:
            urg_cat = 'medium'
        elif urg < 0.75:
            urg_cat = 'high'
        else:
            urg_cat = 'critical'
        
        key = f"{sent_cat}_{urg_cat}"
        distribution[key] = distribution.get(key, 0) + 1
    
    return distribution


# ==============================================================================
# MAIN AUGMENTATION PIPELINE
# ==============================================================================

def augment_dataset(config: AugmentationConfig) -> pd.DataFrame:
    """
    Full augmentation pipeline:
    1. Load deduplicated data
    2. Augment existing transcripts with text transformations
    3. Generate synthetic samples for underrepresented categories
    4. Re-label all augmented/synthetic data with enhanced labeler
    5. Validate label drift and discard bad augmentations
    6. Save final dataset
    
    Returns:
        Augmented DataFrame ready for model training
    """
    start_time = time.perf_counter()
    
    logger.info("=" * 70)
    logger.info("STEP 2: DATA AUGMENTATION & SYNTHESIS")
    logger.info("=" * 70)
    
    # Seed for reproducibility
    random.seed(config.random_seed)
    np.random.seed(config.random_seed)
    
    # Load deduplicated data
    logger.info(f"\n📂 Loading: {config.input_csv}")
    df = pd.read_csv(config.input_csv)
    logger.info(f"✓ Loaded {len(df)} deduplicated records")
    
    if 'transcript' not in df.columns:
        raise ValueError("❌ CSV must have 'transcript' column")
    
    original_count = len(df)
    
    # Initialize components
    augmenter = TextAugmenter(config)
    labeler = EnhancedProxyLabelGenerator(label_noise_std=0.04)
    synthesizer = TemplateSynthesizer(seed=config.random_seed)
    
    # =========================================================================
    # PHASE A: Augment existing transcripts
    # =========================================================================
    logger.info(f"\n🔄 Phase A: Augmenting existing transcripts...")
    logger.info(f"  Target: {config.max_augments_per_sample} variants per sample")
    
    augmented_rows = []
    discarded_count = 0
    
    for idx, row in df.iterrows():
        text = str(row['transcript'])
        original_sentiment = labeler.generate_sentiment(text)
        
        # Generate augmented variants
        variants = augmenter.augment_single(text)
        
        for variant in variants:
            # Validate: check label drift
            variant_sentiment = labeler.generate_sentiment(variant)
            drift = abs(variant_sentiment - original_sentiment)
            
            if drift <= config.max_label_drift:
                new_row = row.copy()
                new_row['transcript'] = variant
                new_row['augmentation_type'] = 'text_augmentation'
                new_row['is_synthetic'] = False
                augmented_rows.append(new_row)
            else:
                discarded_count += 1
        
        if (idx + 1) % 200 == 0:
            logger.info(f"  Processed {idx+1}/{len(df)} "
                       f"({len(augmented_rows)} augmented, "
                       f"{discarded_count} discarded)")
    
    logger.info(f"  ✓ Generated {len(augmented_rows)} augmented samples")
    logger.info(f"  ✗ Discarded {discarded_count} samples (label drift > {config.max_label_drift})")
    
    # =========================================================================
    # PHASE B: Generate synthetic samples for balance
    # =========================================================================
    logger.info(f"\n🧪 Phase B: Generating synthetic samples for distribution balance...")
    
    # First, label the original data with the enhanced labeler
    # so we can analyze the distribution
    for idx, row in df.iterrows():
        text = str(row['transcript'])
        df.at[idx, 'proxy_sentiment'] = labeler.generate_sentiment(text)
        df.at[idx, 'proxy_urgency'] = labeler.generate_urgency(text)
    
    # Analyze current distribution
    distribution = analyze_distribution(df)
    logger.info(f"  Current distribution:")
    for cat, count in sorted(distribution.items()):
        logger.info(f"    {cat}: {count}")
    
    # Target: each category should have at least this many samples
    # REASONING: We use the median category count as the target, not the
    # maximum, because we want to SUPPLEMENT the distribution, not overwhelm
    # real data with synthetic data. If the majority category has 200 samples,
    # we don't force every category to 200 — we bring underrepresented ones
    # up to the median level.
    if distribution:
        counts = list(distribution.values())
        target_per_category = int(np.median(counts)) if counts else 20
    else:
        target_per_category = 20
    
    logger.info(f"  Target per category: {target_per_category}")
    
    synthetic_samples = synthesizer.generate_balanced_set(
        n_per_category=target_per_category,
        existing_distribution=distribution
    )
    
    synthetic_rows = []
    for transcript, target_sent, target_urg in synthetic_samples:
        synthetic_rows.append({
            'transcript': transcript,
            'proxy_sentiment': labeler.generate_sentiment(transcript),
            'proxy_urgency': labeler.generate_urgency(transcript),
            'augmentation_type': 'template_synthesis',
            'is_synthetic': True,
            'target_sentiment_category': target_sent,
            'target_urgency_category': target_urg,
        })
    
    logger.info(f"  ✓ Generated {len(synthetic_rows)} synthetic samples")
    
    # =========================================================================
    # PHASE C: Combine and re-label everything
    # =========================================================================
    logger.info(f"\n📊 Phase C: Combining and labeling final dataset...")
    
    # Mark original data
    df['augmentation_type'] = 'original'
    df['is_synthetic'] = False
    
    # Combine all data
    augmented_df = pd.DataFrame(augmented_rows)
    synthetic_df = pd.DataFrame(synthetic_rows)
    
    # Ensure consistent columns before concat
    all_dfs = [df]
    if len(augmented_df) > 0:
        all_dfs.append(augmented_df)
    if len(synthetic_df) > 0:
        all_dfs.append(synthetic_df)
    
    final_df = pd.concat(all_dfs, ignore_index=True)
    
    # Re-label EVERYTHING with the enhanced labeler for consistency
    logger.info(f"  Re-labeling {len(final_df)} samples with enhanced labeler...")

    # Pre-create columns to avoid KeyError when setting list values
    keyword_results = []
    for idx, row in final_df.iterrows():
        text = str(row['transcript'])
        final_df.at[idx, 'proxy_sentiment'] = labeler.generate_sentiment(text)
        final_df.at[idx, 'proxy_urgency'] = labeler.generate_urgency(text)
        keyword_results.append(labeler.generate_keywords(text))

        if (idx + 1) % 500 == 0:
            logger.info(f"  Labeled {idx+1}/{len(final_df)}")

    # Convert keyword lists to string for CSV storage
    final_df['proxy_keywords_str'] = [
        ','.join(map(str, kw)) if kw else '' for kw in keyword_results
    ]
    
    # =========================================================================
    # PHASE D: Add engineered features
    # =========================================================================
    logger.info(f"\n🔧 Phase D: Adding engineered text features...")
    final_df = add_text_features(final_df)
    
    # =========================================================================
    # Save
    # =========================================================================
    output_path = Path(config.output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    # Save full dataset (for training)
    output_csv = output_path / f"augmented_n{len(final_df)}.csv"
    save_cols = [c for c in final_df.columns if c != 'proxy_keywords']
    final_df[save_cols].to_csv(output_csv, index=False)
    
    # Save statistics
    stats = {
        'original_count': original_count,
        'augmented_count': len(augmented_rows),
        'synthetic_count': len(synthetic_rows),
        'discarded_count': discarded_count,
        'final_count': len(final_df),
        'augmentation_factor': round(len(final_df) / original_count, 2),
        'final_distribution': analyze_distribution(final_df),
        'sentiment_stats': {
            'mean': round(final_df['proxy_sentiment'].mean(), 4),
            'std': round(final_df['proxy_sentiment'].std(), 4),
            'min': round(final_df['proxy_sentiment'].min(), 4),
            'max': round(final_df['proxy_sentiment'].max(), 4),
        },
        'urgency_stats': {
            'mean': round(final_df['proxy_urgency'].mean(), 4),
            'std': round(final_df['proxy_urgency'].std(), 4),
            'min': round(final_df['proxy_urgency'].min(), 4),
            'max': round(final_df['proxy_urgency'].max(), 4),
        }
    }
    
    stats_file = output_path / "augmentation_stats.json"
    with open(stats_file, 'w') as f:
        json.dump(stats, f, indent=2, default=str)
    
    elapsed = time.perf_counter() - start_time
    
    logger.info(f"\n{'=' * 70}")
    logger.info(f"AUGMENTATION COMPLETE")
    logger.info(f"{'=' * 70}")
    logger.info(f"  Original:    {original_count}")
    logger.info(f"  Augmented:   +{len(augmented_rows)}")
    logger.info(f"  Synthetic:   +{len(synthetic_rows)}")
    logger.info(f"  Discarded:   {discarded_count}")
    logger.info(f"  Final:       {len(final_df)} ({stats['augmentation_factor']}x)")
    logger.info(f"  Saved to:    {output_csv}")
    logger.info(f"  Stats:       {stats_file}")
    logger.info(f"  Time:        {elapsed:.1f}s")
    
    # Log final distribution
    logger.info(f"\n📊 Final Sentiment Distribution:")
    neg = (final_df['proxy_sentiment'] < -0.2).sum()
    neu = ((final_df['proxy_sentiment'] >= -0.2) & (final_df['proxy_sentiment'] <= 0.2)).sum()
    pos = (final_df['proxy_sentiment'] > 0.2).sum()
    logger.info(f"  Negative: {neg} ({neg/len(final_df)*100:.1f}%)")
    logger.info(f"  Neutral:  {neu} ({neu/len(final_df)*100:.1f}%)")
    logger.info(f"  Positive: {pos} ({pos/len(final_df)*100:.1f}%)")
    
    return final_df


# ==============================================================================
# TEXT FEATURE ENGINEERING
# ==============================================================================

def add_text_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add engineered features derived from text structure.
    
    REASONING:
        These features give models additional signal beyond raw text content.
        Two complaints with identical words but different structures likely
        have different urgency/sentiment profiles. For example:
        
        - A complaint with 5 sentences and 3 question marks is more likely
          a frustrated customer demanding answers than a calm inquiry.
        - A complaint with high vocabulary richness (many unique words) is
          likely a detailed, specific complaint vs. a short emotional outburst.
        - The presence of exclamation marks correlates with emotional intensity.
        
        These features are particularly useful for the non-transformer models
        (VADER, TweetNLP) which cannot extract structural patterns themselves,
        and they provide RoBERTa with easily accessible pre-computed signals
        that complement its contextual understanding.
    """
    logger.info(f"  Computing text features for {len(df)} samples...")
    
    transcripts = df['transcript'].astype(str)
    
    # Feature 1: Word count
    # REASONING: Longer complaints tend to be more detailed and more negative
    # (frustrated customers write more). This gives the model a simple length
    # signal without needing to count tokens internally.
    df['feat_word_count'] = transcripts.str.split().str.len()
    
    # Feature 2: Sentence count
    # REASONING: Multi-sentence complaints indicate the customer is providing
    # context, which often correlates with escalated or complex issues.
    df['feat_sentence_count'] = transcripts.str.count(r'[.!?]+') + 1
    
    # Feature 3: Average word length
    # REASONING: Technical complaints use longer words ("malfunctioning",
    # "infrastructure") while emotional outbursts use shorter words ("bad",
    # "fix", "now"). This provides a proxy for complaint type.
    df['feat_avg_word_length'] = transcripts.apply(
        lambda t: np.mean([len(w) for w in t.split()]) if t.split() else 0
    )
    
    # Feature 4: Exclamation mark count
    # REASONING: Exclamation marks are a direct signal of emotional intensity.
    # "Fix this!" vs "Fix this." carry different urgency levels. This is one
    # of the strongest single-character features for sentiment.
    df['feat_exclamation_count'] = transcripts.str.count('!')
    
    # Feature 5: Question mark count
    # REASONING: Questions indicate the customer is seeking information,
    # which correlates with inquiry-type tickets (less negative sentiment)
    # or with frustrated demands ("Why hasn't this been fixed?")
    df['feat_question_count'] = transcripts.str.count(r'\?')
    
    # Feature 6: CAPS ratio
    # REASONING: Excessive capitalization ("THIS IS UNACCEPTABLE") is a
    # universally recognized signal of anger/urgency in text communication.
    # We use ratio rather than count to normalize for text length.
    df['feat_caps_ratio'] = transcripts.apply(
        lambda t: sum(1 for c in t if c.isupper()) / max(len(t), 1)
    )
    
    # Feature 7: Type-token ratio (vocabulary richness)
    # REASONING: Vocabulary richness (unique words / total words) indicates
    # complaint complexity. Repetitive complaints ("broken broken broken")
    # have low TTR and high emotional intensity. Detailed complaints with
    # varied vocabulary tend to be more analytical/factual.
    df['feat_type_token_ratio'] = transcripts.apply(
        lambda t: len(set(t.lower().split())) / max(len(t.split()), 1)
    )
    
    # Feature 8: Contains demand/request
    # REASONING: Binary feature indicating whether the complaint contains
    # an explicit demand or request for action, which correlates with
    # higher urgency scores.
    demand_pattern = r'\b(fix|repair|replace|send|resolve|need|must|demand|require|expect|want)\b'
    df['feat_has_demand'] = transcripts.str.contains(
        demand_pattern, case=False, regex=True
    ).astype(int)
    
    # Feature 9: Contains time reference
    # REASONING: Mentions of time duration ("three weeks", "since Monday")
    # indicate an ongoing unresolved issue, which directly correlates with
    # urgency and escalation probability.
    time_pattern = r'\b(\d+\s+(?:day|week|month|hour|year)s?|yesterday|last\s+week|since\s+\w+day)\b'
    df['feat_has_time_ref'] = transcripts.str.contains(
        time_pattern, case=False, regex=True
    ).astype(int)
    
    # Feature 10: Contains escalation language
    # REASONING: Explicit escalation language ("third time", "manager",
    # "legal") indicates a high-priority, previously-unresolved issue.
    escalation_pattern = r'\b(again|third time|fourth time|multiple times|escalat|legal|lawyer|manager|supervisor)\b'
    df['feat_has_escalation'] = transcripts.str.contains(
        escalation_pattern, case=False, regex=True
    ).astype(int)
    
    logger.info(f"  ✓ Added 10 text features")
    
    return df


# ==============================================================================
# CLI
# ==============================================================================

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("\nUsage: python step2_augment.py <deduplicated_csv> [augmentation_factor]")
        print("\nExample:")
        print("  python step2_augment.py data/processed/deduplicated_n500.csv 3")
        print("\nRun AFTER step1_deduplicate.py.")
        print("Produces augmented dataset ready for model training.")
        sys.exit(1)
    
    input_csv = sys.argv[1]
    aug_factor = int(sys.argv[2]) if len(sys.argv) > 2 else 3
    
    config = AugmentationConfig(
        input_csv=input_csv,
        output_dir='data/processed',
        max_augments_per_sample=aug_factor,
    )
    
    df = augment_dataset(config)
    print(f"\n✅ Augmentation complete: {len(df)} total samples")
