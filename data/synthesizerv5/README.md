# InnovaCX Sentiment Analysis Pipeline
## Complete Setup, Training & Three-Model Comparison

---

## 1. The Data Variety Problem

Your core problem is not just duplicates — it is that the synthesizer (`enhanced_data_synthesizer.py`) generates structurally identical transcripts with only slot fillers swapped. Every support call follows this exact template:

```
Agent greeting → Tenant opening (tone-based) → "We are experiencing {issue}."
→ "{random phrase from issue}" → Agent asks for details → Tenant gives location
→ [if recurring: frustration line] → [if high impact: business impact line]
→ [if safety: safety line] → Agent commitment → Closing
```

The numbers tell the story:

| Category | Issues Available | Records Generated | Effective Ratio |
|----------|-----------------|-------------------|-----------------|
| Critical | 4 | 60 | 15 per issue |
| High | 4 | 150 | 37.5 per issue |
| Medium | 4 | 240 | 60 per issue |
| Low | 4 | 150 | 37.5 per issue |

With only 16 unique issue templates feeding 600 support records, the model will learn "if transcript contains 'complete power outage' → very negative" as a lookup table, not as generalized sentiment understanding. It will fail on any complaint not matching these 16 templates.

**What the augmentation pipeline does about this (already implemented):**

| Strategy | Status | What It Does |
|----------|--------|-------------|
| Near-duplicate removal (TF-IDF cosine) | Implemented (Step 1) | Clusters and collapses transcripts with >0.92 similarity |
| Synonym replacement | Implemented (Step 2) | "frustrated" → "irritated", "broken" → "malfunctioning" |
| Random word deletion | Implemented (Step 2) | Drops ~10% of words to simulate Whisper errors |
| Random word insertion | Implemented (Step 2) | Adds fillers ("honestly", "you know") |
| Sentence shuffle | Implemented (Step 2) | Reorders multi-sentence complaints |
| ASR noise injection | Implemented (Step 2) | "can't" → "cant", "maintenance" → "maintanence" |
| Template synthesis for underrepresented bins | Implemented (Step 2) | Generates complaints for sparse sentiment×urgency zones |
| Enhanced proxy labeler (negation, intensifiers, noise) | Implemented (Step 2) | "not satisfied" correctly scores negative |
| 10 text features | Implemented (Step 2) | word count, caps ratio, demands, time refs, escalation |
| **Back-translation (en→ar→en via MarianMT)** | **NOT implemented** | Would create natural paraphrases |
| **VADER cross-labeling in proxy labels** | **NOT implemented** | Would add label variance via ensemble labeling |

**My recommendation: You should generate new, more varied data.** The augmentation pipeline helps, but it cannot create fundamentally new complaint types — it can only perturb the 16 existing templates. For the model to handle "no matter what is fed into it", you need complaints about issues that don't exist in the current dataset at all. More on this below.

---

## 2. Does RoBERTa Need Changes?

**The RoBERTa architecture itself does NOT need changes.** The multi-task architecture in `step3_compare_models.py` already matches the V6 spec:

```
RoBERTa-base (768-dim CLS token)
├── Sentiment head: 768 → 256 → 1 (tanh) → [-1, +1]
├── Urgency head:   768 → 256 → 1 (sigmoid) → [0, 1]
└── Keyword head:   768 → 256 → 50 (sigmoid) → multi-label
```

This matches the architecture in `model_architecture.py` across all three copies in the repo (DSPY/src, SentimentAnalysisAgent/src, backend/sentiment-service).

**What DOES need to happen is retraining on better data.** The architecture is sound. The bottleneck is data variety, not model capacity. RoBERTa-base has 125M parameters — more than enough to learn sentiment patterns from a few hundred diverse complaints. The issue is that your current 600 support records contain only 16 unique complaint topics, so the model memorizes topics instead of learning sentiment patterns.

**Specific training improvements already built into step3:**
- Stratified train/test split (the existing `train_production.py` uses `random_split` which doesn't guarantee proportional sentiment bins — step3 fixes this)
- Multi-task loss with MSE for sentiment/urgency + BCE for keywords (matching V6)
- Gradient clipping at norm=1.0 to prevent catastrophic fine-tuning updates
- Best-checkpoint restoration based on validation loss

---

## 3. BLITS-M vs TweetNLP — What Was Built, What You Asked For

The V6 strategy session mentioned "BLITS-M, TweetNLP, or a fine-tuned DistilBERT" as options for the third comparison model. **Step 3 currently implements TweetNLP (cardiffnlp/twitter-roberta-base-sentiment-latest), not BLITS-M.**

Here is the difference:

| Aspect | TweetNLP (currently implemented) | BLITS-M (alternative) |
|--------|-----------------------------------|----------------------|
| **What it is** | RoBERTa fine-tuned on 124M tweets for 3-class sentiment (neg/neu/pos) | Bidirectional multimodal model that processes text AND audio jointly |
| **Modality** | Text only | Text + audio (multimodal) |
| **Why it matters** | Tests if social-media pre-training transfers to business complaints | Tests if joint text+audio processing beats your pipeline's separate text→combine→audio approach |
| **Setup** | `pip install transformers` — zero-shot, no training | Requires audio features as input alongside text |
| **Academic angle** | "Does domain-specific fine-tuning (our RoBERTa) beat general social sentiment pre-training?" | "Does end-to-end multimodal learning beat our hand-crafted audio+text combination?" |

**My recommendation: Keep TweetNLP.** Here's why:

BLITS-M would be comparing apples to oranges — it takes audio input directly, while your pipeline design explicitly separates audio processing (Whisper → librosa features → `audio_sentiment_combiner.py`) from text sentiment (RoBERTa). Your `unified_complaint_analyzer.py` already handles the multimodal fusion with 70/30 text/audio weighting. BLITS-M would bypass this architecture entirely.

TweetNLP gives you a cleaner comparison: three text-only models on the same test set, measuring whether domain-specific fine-tuning beats a model trained on 124M social media posts. This directly validates your training investment.

If your professor specifically wants BLITS-M, it would need to be evaluated on the audio+text combined pipeline (against `unified_complaint_analyzer.py`), which is a separate comparison story from the text-only three-model comparison.

---

## 4. Complete Setup Instructions

### 4.1 Prerequisites

```bash
pip install pandas numpy scikit-learn scipy
pip install torch transformers
pip install vaderSentiment
```

These are the only dependencies. No special hardware required — all three models run on CPU. GPU accelerates RoBERTa training but is not required.

### 4.2 Prepare the Data

**Option A: Use existing synthesized data (if you already have dataset.csv)**

```bash
cd ai-models/MultiAgentPipeline/FeatureEngineeringAgent

# Run preprocessing (extracts tenant speech, filters to complaints, deduplicates)
python app/preprocess.py
# Output: data/processed/cleaned.csv with "clean_text" column

# Rename column for sentiment pipeline compatibility
python -c "
import pandas as pd
df = pd.read_csv('data/processed/cleaned.csv')
df = df.rename(columns={'clean_text': 'transcript'})
df.to_csv('data/processed/cleaned.csv', index=False)
print(f'Done. {len(df)} rows, columns: {list(df.columns)}')
"
```

**Option B: Generate new, more varied data (RECOMMENDED)**

The current synthesizer produces only 16 issue types. If you want the model to generalize, you should expand `enhanced_data_synthesizer.py` to include more issue templates. Specifically:

What to add to `service_issues` in the synthesizer:
- HVAC: "heating not working in winter", "strange smell from vents", "thermostat unresponsive"
- Plumbing: "low water pressure", "hot water not available", "sewage backup"
- Electrical: "flickering lights", "frequent circuit breaker trips", "outlets not grounded"
- Structural: "ceiling tiles falling", "cracks in walls", "door lock broken"
- Pest control: "rodent sighting", "insect infestation", "bird nesting in vents"
- Common areas: "gym equipment broken", "pool maintenance overdue", "lobby not cleaned"
- Administrative: "billing error", "lease renewal not processed", "access card not working"

Going from 16 to 40+ issue types would dramatically improve generalization. Each new issue type should have 3-4 unique phrases and appropriate severity/impact assignments.

After regenerating, run the same preprocessing:
```bash
cd data
python enhanced_data_synthesizer.py
cp Enhanced_DataSet_SentimentAnalysis.csv \
   ../ai-models/MultiAgentPipeline/FeatureEngineeringAgent/data/raw/dataset.csv

cd ../ai-models/MultiAgentPipeline/FeatureEngineeringAgent
python app/preprocess.py

python -c "
import pandas as pd
df = pd.read_csv('data/processed/cleaned.csv')
df = df.rename(columns={'clean_text': 'transcript'})
df.to_csv('data/processed/cleaned.csv', index=False)
print(f'Done. {len(df)} rows')
"
```

### 4.3 Step 1: Near-Duplicate Removal

```bash
python step1_deduplicate.py data/processed/cleaned.csv 0.92
```

Output: `data/processed/deduplicated_n{N}.csv` where `{N}` is the surviving record count.

What it does: Builds TF-IDF vectors for all transcripts, computes pairwise cosine similarity, clusters transcripts above 0.92 threshold, keeps the longest per cluster. Also removes transcripts under 10 characters and outputs `deduplication_stats.json`.

### 4.4 Step 2: Augmentation & Enhanced Labeling

```bash
python step2_augment.py data/processed/deduplicated_n{N}.csv 3
```

The `3` means up to 3 augmented variants per original transcript. Output: `data/processed/augmented_n{M}.csv`.

What happens inside:
1. **6 augmentation techniques** applied randomly (synonym replacement, word deletion, word insertion, sentence shuffle, ASR noise). Each augmented sample is re-scored by the enhanced proxy labeler. If sentiment drifts > 0.15 from original, the augment is discarded.
2. **Template synthesis** generates new complaints for underrepresented sentiment×urgency bins.
3. **Enhanced proxy labeling** replaces the original flat-lexicon labeler. Handles negation ("not satisfied" → negative), intensifiers ("extremely frustrated" → stronger negative), position weighting (first/last sentences weighted 20% more), and adds Gaussian noise (σ=0.04) to prevent discrete label clustering.
4. **10 text features** are computed and added as columns: word count, sentence count, avg word length, exclamation count, question count, CAPS ratio, type-token ratio, has_demand, has_time_reference, has_escalation_language.

The output CSV contains columns: `transcript`, `proxy_sentiment`, `proxy_urgency`, `proxy_keywords_str`, plus the 10 `feat_*` columns and metadata.

### 4.5 Step 3: Train All Three Models & Compare

```bash
python step3_compare_models.py data/processed/augmented_n{M}.csv results/
```

This single command does everything:

**Model 1 — RoBERTa (Fine-tuned):**
- Loads `roberta-base` from HuggingFace (125M params, downloads ~500MB on first run)
- Creates multi-task architecture: shared encoder + sentiment/urgency/keyword heads
- Fine-tunes ALL layers (not frozen) with AdamW, lr=2e-5, batch_size=8
- Trains for 5 epochs with validation loss tracking and best-checkpoint restoration
- Saves to `results/roberta/model.pt` + tokenizer files

**Model 2 — VADER (Rule-based):**
- No training required. Imports `vaderSentiment` library
- Uses built-in lexicon (7,500+ sentiment-rated words) plus rules for CAPS, punctuation, negation, degree modifiers, conjunctions
- Outputs compound score directly in [-1, +1] matching our sentiment scale
- Evaluated zero-shot on the same test set as RoBERTa

**Model 3 — TweetNLP (Transfer Learning):**
- Loads `cardiffnlp/twitter-roberta-base-sentiment-latest` from HuggingFace (downloads ~500MB on first run)
- Pre-trained on 124M tweets for 3-class sentiment (negative, neutral, positive)
- Outputs class probabilities. Converted to continuous score: `P(positive) - P(negative)` → [-1, +1]
- Evaluated zero-shot on the same test set as RoBERTa

**Evaluation (all three on same test set):**
- Stratified 80/20 train/test split on sentiment bins (negative/neutral/positive)
- Metrics: MAE, RMSE, Pearson correlation, Spearman rank correlation, per-category accuracy, inference latency
- Outputs:
  - `results/comparison_report.txt` — human-readable comparison table
  - `results/comparison_results.json` — machine-readable metrics
  - `results/comparison_metrics.csv` — spreadsheet-friendly format
  - `results/roberta/` — trained model files for deployment

### 4.6 Deploy Trained Model

After step 3 completes, copy the RoBERTa model to the sentiment service:

```bash
cp results/roberta/model.pt backend/sentiment-service/models/
cp results/roberta/tokenizer* backend/sentiment-service/models/
cp results/roberta/special_tokens* backend/sentiment-service/models/
cp results/roberta/vocab* backend/sentiment-service/models/
cp results/roberta/merges* backend/sentiment-service/models/
```

Then in `.env` or `docker-compose.yml`:
```yaml
USE_MOCK_MODEL: "false"
```

Restart: `docker-compose up -d sentiment`

Verify: `curl http://localhost:8002/health` should return `{"status":"healthy","mock_mode":false}`.

---

## 5. Complete Copy-Paste Execution (End to End)

```bash
# ==================================================================
# STEP 0: Preprocess (extract tenant speech, filter, exact dedup)
# ==================================================================
cd ai-models/MultiAgentPipeline/FeatureEngineeringAgent
python app/preprocess.py

# ==================================================================
# STEP 0.5: Rename column (clean_text → transcript)
# ==================================================================
python -c "
import pandas as pd
df = pd.read_csv('data/processed/cleaned.csv')
df = df.rename(columns={'clean_text': 'transcript'})
df.to_csv('data/processed/cleaned.csv', index=False)
print(f'Done. {len(df)} rows.')
"

# ==================================================================
# STEP 1: Near-duplicate removal
# ==================================================================
python step1_deduplicate.py data/processed/cleaned.csv 0.92
# Note the N in the output filename

# ==================================================================
# STEP 2: Augmentation + enhanced labeling
# (replace {N} with the number from step 1 output)
# ==================================================================
python step2_augment.py data/processed/deduplicated_n{N}.csv 3
# Note the M in the output filename

# ==================================================================
# STEP 3: Train RoBERTa + evaluate all three models
# (replace {M} with the number from step 2 output)
# ==================================================================
python step3_compare_models.py data/processed/augmented_n{M}.csv results/

# ==================================================================
# VIEW RESULTS
# ==================================================================
cat results/comparison_report.txt

# ==================================================================
# DEPLOY (optional — copy trained model to sentiment service)
# ==================================================================
cp -r results/roberta/* ../../backend/sentiment-service/models/
```

---

## 6. What Was Implemented vs What Was Discussed

For full transparency, here is the mapping between the V6 strategy session recommendations and what exists in the code:

| Strategy Session Recommendation | Status | Location |
|---------------------------------|--------|----------|
| Near-duplicate removal (TF-IDF cosine 0.92) | Done | step1_deduplicate.py |
| Synonym replacement (domain-curated, intensity-matched) | Done | step2_augment.py → TextAugmenter.synonym_replacement() |
| Random word deletion (~10%) | Done | step2_augment.py → TextAugmenter.random_word_deletion() |
| Random word insertion (fillers) | Done | step2_augment.py → TextAugmenter.random_word_insertion() |
| Sentence shuffle | Done | step2_augment.py → TextAugmenter.sentence_shuffle() |
| ASR noise injection | Done | step2_augment.py → TextAugmenter.asr_noise_injection() |
| Template synthesis for underrepresented bins | Done | step2_augment.py → ComplaintSynthesizer |
| Enhanced proxy labeler (negation, intensifiers, position weighting) | Done | step2_augment.py → EnhancedProxyLabelGenerator |
| Continuous label noise (σ=0.04) | Done | step2_augment.py → EnhancedProxyLabelGenerator |
| 10 text features | Done | step2_augment.py → add_text_features() |
| Three-model comparison framework | Done | step3_compare_models.py |
| RoBERTa multi-task (sentiment + urgency + keywords) | Done | step3_compare_models.py → SentimentRoBERTa |
| VADER (zero-shot baseline) | Done | step3_compare_models.py → VADERSentimentModel |
| TweetNLP/CardiffNLP (transfer learning) | Done | step3_compare_models.py → TweetNLPSentimentModel |
| Stratified train/test split | Done | step3_compare_models.py → run_comparison() |
| Back-translation (en→ar→en via MarianMT) | **Not done** | Would require pip install sentencepiece + ~1GB model download |
| VADER cross-labeling in proxy labels | **Not done** | VADER is only used as a comparison model, not as a labeling signal |
| BLITS-M multimodal comparison | **Not done** | TweetNLP used instead (text-only, cleaner comparison) |
| Expanded synthesizer templates (>16 issues) | **Not done** | User can expand enhanced_data_synthesizer.py |

The two missing augmentation strategies (back-translation and VADER cross-labeling) would improve data variety but are not essential — the six implemented techniques already provide meaningful perturbation. Back-translation is the higher-value addition if you want to implement it.
