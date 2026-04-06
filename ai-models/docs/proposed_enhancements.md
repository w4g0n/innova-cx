# InnovaCX Proposed Enhancements: Model Comparison, Fuzzy Logic & Security

## Table of Contents

1. [Sentiment Model Comparison](#1-sentiment-model-comparison)
2. [Classification Models for Priority & Routing](#2-classification-models-for-priority--routing)
3. [Fuzzy Logic Prioritization System](#3-fuzzy-logic-prioritization-system)
4. [Security Measures](#4-security-measures)
5. [Dependencies & Integration Summary](#5-dependencies--integration-summary)

---

## 1. Sentiment Model Comparison

### 1.1 Current State: RoBERTa Multi-Task Model

The platform currently uses a single **RoBERTa-base multi-task model** (`ai-models/ml-models/sentiment-model/src/model_architecture.py`) that simultaneously predicts three outputs from a shared transformer encoder:

```
Input Text: "The AC has been broken for three days!"
                            |
                    RoBERTa Encoder
                    (12 layers, 768d hidden, ~125M params)
                            |
              +-------------+-------------+
              |             |             |
        Sentiment      Urgency       Keywords
        Head           Head          Head
        (768->256->1)  (768->256->1) (768->256->50)
              |             |             |
        Tanh [-1,1]    Sigmoid [0,1]  Sigmoid [0,1]^50
              |             |             |
        -0.75          0.82          [AC, broken, ...]
    (very negative)   (high urgent)  (extracted keywords)
```

**Key characteristics:**
- **Parameters**: ~125M (RoBERTa base) + ~590K (task heads) = ~125.6M total
- **Input processing**: RobertaTokenizer, max_length=128, padding='max_length'
- **Training**: AdamW optimizer, lr=2e-5, batch_size=8, 10 epochs
- **Loss function**: MSE (sentiment, urgency) + BCE (keywords), weights 1.0 : 1.0 : 0.5
- **Training data**: Proxy labels generated via rule-based `ProxyLabelGenerator` (not human-annotated)
- **Inference**: Extracts CLS token -> passes through each task head independently
- **API**: FastAPI endpoint at `/analyze` returning `{text_sentiment, text_urgency, keywords, category}`

**Limitation**: With only one model, there is no way to validate whether RoBERTa's predictions are reliable, identify systematic biases, or understand if the model complexity is justified for this domain. A single-model approach also creates a single point of failure.

### 1.2 Proposed Model 1: VADER (Valence Aware Dictionary and sEntiment Reasoner)

#### 1.2.1 Why VADER?

VADER is a **rule-based, lexicon-driven** sentiment analysis tool specifically attuned to sentiments expressed in social media and informal text. It requires no training data, no GPU, and produces instant results.

**Rationale for selection:**
- **Architectural diversity**: Entirely rule-based (no neural network), providing maximum contrast with the transformer-based RoBERTa
- **Baseline establishment**: As a zero-training model, VADER serves as the performance "floor" - if RoBERTa cannot significantly outperform VADER on our domain data, the additional complexity of a 125M-parameter transformer is not justified
- **Domain relevance**: Customer complaints often use emphatic language (capitalization, exclamation marks, intensifiers like "very" and "extremely") which VADER handles natively through its valence-shifting rules
- **Inference speed**: Near-zero latency (no model loading, no GPU), providing a speed benchmark
- **Interpretability**: Every score can be traced back to specific lexicon entries and grammar rules, making it fully explainable

#### 1.2.2 Architecture

```
Input Text: "The AC has been broken for three days!"
                            |
                    VADER SentimentIntensityAnalyzer
                    (Lexicon: ~7,500 entries with valence scores)
                            |
                    Compound Score Calculation:
                    1. Tokenize and match lexicon entries
                    2. Apply valence-shifting rules:
                       - Negation ("not good" flips valence)
                       - Degree modifiers ("very" intensifies)
                       - Capitalization (ALL CAPS amplifies)
                       - Punctuation (!! amplifies)
                       - Conjunctions ("but" shifts emphasis)
                    3. Normalize to [-1, +1]
                            |
              +-------------+-------------+
              |             |             |
        Sentiment      Urgency       Keywords
        (native)       (heuristic)   (heuristic)
              |             |             |
        Compound       Keyword-based  Domain keyword
        Score [-1,1]   matching [0,1] matching
              |             |             |
        -0.68          0.60          [AC, broken]
```

**VADER natively produces:**
- `compound`: Normalized sentiment score in [-1, +1] (maps directly to our `text_sentiment`)
- `pos`, `neg`, `neu`: Proportion of text falling into each category

**For urgency and keywords (not native to VADER)**, the system uses heuristic post-processing identical to the existing `MockPredictor` (`backend/sentiment-service/mock_predictor.py`):
- **Urgency**: Keyword matching against urgency lexicon (emergency, urgent, immediately, flooding, fire, dangerous, safety, critical) with weighted scoring
- **Keywords**: String matching against the 50-word `KEYWORD_VOCABULARY` defined in `model_architecture.py`

#### 1.2.3 Strengths and Limitations

| Aspect | Strength | Limitation |
|--------|----------|------------|
| Training | Zero training required | Cannot learn domain-specific patterns |
| Speed | Sub-millisecond inference | N/A |
| Accuracy | Good on emphatic/informal text | Misses implicit sentiment ("elevator stuck" has no explicit negative word) |
| Interpretability | Fully explainable via lexicon lookup | Rule-based system cannot generalize |
| Urgency | N/A | Must rely on keyword heuristics (not learned) |
| Keywords | N/A | Simple string matching, no semantic understanding |
| Model Size | ~300KB (lexicon file) | Fixed vocabulary cannot be expanded without manual effort |

### 1.3 Proposed Model 2: BiLSTM with GloVe Embeddings

#### 1.3.1 Why BiLSTM?

A Bidirectional Long Short-Term Memory (BiLSTM) network represents the **pre-transformer era of deep learning** for NLP. It processes text sequentially in both forward and backward directions, capturing word-order dependencies through hidden state propagation rather than self-attention.

**Rationale for selection:**
- **Architectural diversity**: Recurrent neural network (sequential processing) vs. transformer (parallel attention). This is a fundamentally different approach to text encoding - BiLSTM builds a sentence representation by reading one word at a time in both directions, while RoBERTa attends to all words simultaneously
- **Embedding diversity**: GloVe embeddings are **static** (each word has one fixed vector regardless of context) vs. RoBERTa's **contextual** embeddings (the vector for "bank" differs in "river bank" vs "bank account"). This tests whether contextual understanding matters for our complaint domain
- **Parameter efficiency**: ~2M parameters (100x fewer than RoBERTa), testing whether a lighter model suffices for our relatively narrow domain of building complaints
- **Training efficiency**: Can train in minutes on CPU vs. hours for RoBERTa, with batch_size=32 (vs. 8 for RoBERTa)
- **Middle ground**: Sits between rule-based VADER (no learning) and attention-based RoBERTa (full contextual learning), creating a natural three-point comparison spectrum

#### 1.3.2 Architecture

```
Input Text: "The AC has been broken for three days!"
                            |
                    GloVe Embedding Layer
                    (300d, frozen pre-trained, ~400K vocab)
                            |
        [0.21, -0.08, ...]  [0.53, 0.12, ...]  ...  [0.15, -0.33, ...]
            "The"               "AC"                    "days"
                            |
                    Bidirectional LSTM
                    (2 layers, 256 hidden per direction)
                            |
                    Forward final hidden (256d)
                    +
                    Backward final hidden (256d)
                    = Concatenated (512d)
                            |
              +-------------+-------------+
              |             |             |
        Sentiment      Urgency       Keywords
        Head           Head          Head
        (512->256->1)  (512->256->1) (512->256->50)
              |             |             |
        Tanh [-1,1]    Sigmoid [0,1]  Sigmoid [0,1]^50
              |             |             |
        -0.71          0.78          [AC, broken, ...]
```

**Architecture details:**
- **Embedding**: GloVe 6B 300d (pre-trained, frozen) - ~1.2M vectors, 300 dimensions each
- **Encoder**: 2-layer BiLSTM, 256 hidden units per direction, dropout=0.3 between layers
- **Representation**: Concatenation of final forward and backward hidden states = 512d
- **Task heads**: Identical structure to RoBERTa model but with 512d input instead of 768d:
  - Sentiment: Linear(512, 256) -> ReLU -> Dropout(0.1) -> Linear(256, 1) -> Tanh
  - Urgency: Linear(512, 256) -> ReLU -> Dropout(0.1) -> Linear(256, 1) -> Sigmoid
  - Keywords: Linear(512, 256) -> ReLU -> Dropout(0.1) -> Linear(256, 50) -> Sigmoid

**Training configuration:**
- **Optimizer**: Adam (not AdamW - no transformer weight decay needed)
- **Learning rate**: 1e-3 (50x higher than RoBERTa fine-tuning rate, appropriate for training from scratch)
- **Batch size**: 32 (larger than RoBERTa's 8, since BiLSTM uses far less memory)
- **Epochs**: 20 (more epochs due to higher learning rate and smaller model)
- **Loss**: Same `MultiTaskLoss` class from `train_production.py` (MSE + MSE + BCE, weights 1:1:0.5)
- **Dataset**: Same `MultiTaskDataset` format, but tokenization replaces RobertaTokenizer with GloVe vocabulary lookup

#### 1.3.3 Strengths and Limitations

| Aspect | Strength | Limitation |
|--------|----------|------------|
| Training | Fast (minutes on CPU) | Requires training data (same as RoBERTa) |
| Speed | ~5-10ms inference (vs ~20-50ms RoBERTa) | Slower than VADER |
| Accuracy | Captures word order and sequential patterns | Cannot model long-range dependencies as well as attention |
| Parameters | ~2M (100x fewer than RoBERTa) | Less representational capacity |
| Embeddings | GloVe captures general word semantics | Static - "broken" has same vector in all contexts |
| Interpretability | Hidden states harder to interpret than lexicon | More interpretable than 12-layer transformer (simpler architecture) |
| Keywords | Learned multi-label classification | Same keyword vocabulary constraint as RoBERTa |

### 1.4 Three-Model Comparison Framework

#### 1.4.1 Comparison Dimensions

| Dimension | VADER | BiLSTM + GloVe | RoBERTa |
|-----------|-------|----------------|---------|
| **Architecture** | Rule-based lexicon | Recurrent (sequential) | Transformer (attention) |
| **Embeddings** | None (lexicon lookup) | GloVe static (300d) | Contextual (768d) |
| **Parameters** | 0 (no weights) | ~2M | ~125.6M |
| **Training** | None required | ~10 min CPU | ~2+ hours GPU |
| **Inference Time** | <1ms | ~5-10ms | ~20-50ms |
| **GPU Required** | No | No (feasible on CPU) | Recommended |
| **Context Understanding** | None (word-level) | Sequential (word order) | Full (all-to-all attention) |
| **Multi-Task** | No (sentiment only, heuristic urgency/keywords) | Yes (shared encoder, 3 heads) | Yes (shared encoder, 3 heads) |
| **Interpretability** | High (lexicon trace) | Medium (hidden states) | Low (attention patterns) |

#### 1.4.2 Proposed Evaluation Metrics

**Sentiment quality:**
- Mean Squared Error (MSE) against proxy labels
- Mean Absolute Error (MAE) against proxy labels
- Pearson correlation between predictions and proxy labels
- Direction accuracy: % of texts where model agrees on positive/negative/neutral classification

**Urgency quality:**
- MSE and MAE against proxy urgency labels
- Binary accuracy at threshold 0.5 (urgent vs not urgent)
- Spearman rank correlation (does the model order texts by urgency correctly?)

**Keyword extraction quality:**
- Precision, Recall, F1 per keyword (micro and macro averaged)
- Hamming loss (fraction of incorrect labels across all 50 keywords)

**Performance metrics:**
- Mean inference latency (ms per sample)
- P95 and P99 latency
- Throughput (samples per second)
- Peak memory usage (MB)

**Agreement metrics:**
- Pairwise model agreement (% of texts where both models agree on sentiment category)
- Cohen's Kappa between model pairs
- Cases where models disagree strongly (sentinel for potential errors)

#### 1.4.3 Proposed API Integration

The sentiment service API (`backend/sentiment-service/api.py`) would be extended with:

**Abstract predictor interface** (`BasePredictor`):
- All three models implement the same `predict(text) -> PredictionResult` interface
- `PredictionResult` contains: `text_sentiment`, `text_urgency`, `keywords`, `keyword_scores`, `processing_time_ms`

**Model router** (`ModelRouter`):
- Registers available models by name
- Routes `predict()` calls to configured primary model
- Provides `predict_all()` for comparison mode

**New endpoints:**
- `POST /analyze-compare`: Runs text through all loaded models, returns side-by-side results
- `GET /models`: Lists loaded models with metadata (name, type, parameter count, status)

**Configuration:**
- `SENTIMENT_MODEL` env var: `mock` | `roberta` | `vader` | `bilstm` | `all`
- Existing `POST /analyze` continues to use the configured primary model

---

## 2. Classification Models for Priority & Routing

### 2.1 Classification Tasks

The platform has two natural classification tasks based on the database schema:

**Task 1: Priority Classification (4 classes)**
- Priority levels: 1 (low), 2 (medium), 3 (high), 4 (critical)
- Currently computed by rule-based pipeline in `ai-models/prioritization/prioritization.py`
- Formula: `raw_score = 1*severity + 1*urgency + 2*sentiment_pressure`, rounded to 1-4

**Task 2: Department Routing (multi-class)**
- Departments defined in database: IT Support, Network, Billing, Customer Service, Operations
- Not currently ML-driven (manual assignment or rule-based)
- Adding ML-based routing would enable automatic ticket assignment

### 2.2 Feature Engineering Pipeline

All three classifiers use the same feature set:

```
Complaint Text: "The AC in building A has been broken for 3 days"
                            |
              +-------------+-------------+
              |             |             |
        TF-IDF          Sentiment       Categorical
        Features        Features        Features
              |             |             |
    Vectorize text   From RoBERTa:    One-hot encode:
    max_features=    text_sentiment   - channel (text/audio/chat)
    5000             text_urgency     - tenant_tier (4 levels)
    stop_words=eng   keywords count   - asset_type (3 types)
              |             |             |
    Sparse matrix   Dense vector    Dense vector
    (1 x 5000)      (1 x 3)        (1 x ~10)
              |             |             |
              +------+------+
                     |
              Feature Vector
              (1 x ~5013)
              scipy.sparse.hstack
```

**Feature details:**
- **TF-IDF features (5000)**: Captures word importance and complaint vocabulary patterns
- **Sentiment features (3)**: `text_sentiment` [-1,1], `text_urgency` [0,1], keyword count [0,50] from the sentiment model
- **Categorical features (~10)**: One-hot encoded metadata from the ticket (channel, tenant tier, asset type, is_recurring, safety_concern)

### 2.3 Model 1: Random Forest

#### 2.3.1 Why Random Forest?

Random Forest is an **ensemble of decision trees** that votes on the final prediction. Each tree sees a random subset of features and training samples.

**Rationale:**
- **Feature importance**: Built-in `feature_importances_` attribute reveals which words and features drive priority decisions - valuable for understanding the model's reasoning
- **Robustness**: Ensemble averaging reduces overfitting, works well with both sparse TF-IDF and dense numeric features
- **No scaling required**: Unlike SVM, Random Forest is invariant to feature scaling
- **Handles mixed features**: Works naturally with the combination of high-dimensional sparse text features and low-dimensional dense metadata

#### 2.3.2 Configuration

```python
from sklearn.ensemble import RandomForestClassifier

rf_model = RandomForestClassifier(
    n_estimators=200,          # Number of trees
    max_depth=None,            # Let trees grow fully
    min_samples_split=5,       # Minimum samples to split a node
    min_samples_leaf=2,        # Minimum samples in leaf node
    max_features='sqrt',       # sqrt(n_features) per split
    class_weight='balanced',   # Handle class imbalance
    random_state=42,
    n_jobs=-1                  # Parallel training
)
```

#### 2.3.3 Expected Properties

| Property | Value |
|----------|-------|
| Training time | ~30 seconds (CPU, 5000 samples) |
| Inference time | ~1-2ms per sample |
| Interpretability | High (feature importance, tree visualization) |
| Hyperparameters | n_estimators, max_depth, min_samples |
| Handles imbalance | Yes (class_weight='balanced') |
| Scales with data | Well (more trees = better, parallelizable) |

### 2.4 Model 2: XGBoost (Extreme Gradient Boosting)

#### 2.4.1 Why XGBoost?

XGBoost is a **gradient boosting** algorithm that builds trees sequentially, where each new tree corrects the errors of the previous ensemble.

**Rationale:**
- **Typically highest accuracy**: Gradient boosting consistently achieves top performance in structured/tabular data competitions and benchmarks
- **Regularization built-in**: L1 and L2 regularization prevent overfitting, important when TF-IDF features are high-dimensional
- **SHAP explainability**: Native SHAP (SHapley Additive exPlanations) integration provides per-prediction feature importance - for each individual complaint, shows exactly which words and features drove the priority decision
- **Handling missing values**: XGBoost natively handles NaN values, useful when some metadata fields may be missing

#### 2.4.2 Configuration

```python
import xgboost as xgb

xgb_model = xgb.XGBClassifier(
    n_estimators=300,          # Number of boosting rounds
    max_depth=6,               # Max tree depth (shallower than RF)
    learning_rate=0.1,         # Step size for each tree
    subsample=0.8,             # Row sampling per tree
    colsample_bytree=0.8,     # Feature sampling per tree
    reg_alpha=0.1,             # L1 regularization
    reg_lambda=1.0,            # L2 regularization
    eval_metric='mlogloss',    # Multi-class log loss
    use_label_encoder=False,
    random_state=42
)
```

#### 2.4.3 Expected Properties

| Property | Value |
|----------|-------|
| Training time | ~1-2 minutes (CPU, 5000 samples) |
| Inference time | ~1-3ms per sample |
| Interpretability | High (SHAP values, feature importance) |
| Hyperparameters | n_estimators, max_depth, learning_rate, regularization |
| Handles imbalance | Yes (scale_pos_weight or sample_weight) |
| Regularization | L1 + L2 built-in |

### 2.5 Model 3: SVM with RBF Kernel

#### 2.5.1 Why SVM?

Support Vector Machine finds the optimal **hyperplane** that maximizes the margin between classes. With an RBF (Radial Basis Function) kernel, it projects data into a higher-dimensional space where non-linear boundaries become linear.

**Rationale:**
- **Text classification strength**: SVMs have a strong theoretical foundation for high-dimensional, sparse feature spaces like TF-IDF vectors
- **Margin-based confidence**: The distance from the decision boundary provides a natural confidence measure, useful for flagging uncertain predictions for human review
- **Different decision boundary**: While tree-based models create axis-aligned splits, SVM creates smooth, continuous decision boundaries - this architectural diversity may capture patterns the tree models miss
- **Small dataset robustness**: SVMs generalize well with limited training data, important if the proxy-labeled dataset is small

#### 2.5.2 Configuration

```python
from sklearn.svm import SVC
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline

svm_pipeline = Pipeline([
    ('scaler', StandardScaler(with_mean=False)),  # with_mean=False for sparse matrices
    ('svm', SVC(
        kernel='rbf',
        C=1.0,                     # Regularization parameter
        gamma='scale',             # Kernel coefficient
        class_weight='balanced',   # Handle class imbalance
        probability=True,          # Enable probability estimates
        random_state=42
    ))
])
```

**Note**: SVM requires feature scaling (StandardScaler), unlike the tree-based models. The `with_mean=False` parameter is necessary because our TF-IDF features are sparse matrices that cannot be centered.

#### 2.5.3 Expected Properties

| Property | Value |
|----------|-------|
| Training time | ~2-5 minutes (CPU, 5000 samples, depends on C) |
| Inference time | ~5-10ms per sample (slower than trees) |
| Interpretability | Medium (support vectors, but harder to visualize than trees) |
| Hyperparameters | C, gamma, kernel |
| Handles imbalance | Yes (class_weight='balanced') |
| Scaling | Required (StandardScaler) |

### 2.6 Training Strategy

**Data source**: Same complaint transcripts used for sentiment model training, with priority labels generated by the existing `compute_priority()` function in `prioritization.py`.

**Evaluation**: Stratified 5-fold cross-validation to ensure all priority levels are represented in each fold.

**Metrics per classifier:**
- Accuracy (overall)
- Precision, Recall, F1 per priority class (weighted and macro-averaged)
- Confusion matrix
- ROC-AUC (one-vs-rest for multi-class)
- Training time and inference time

### 2.7 Ensemble Approach

The three classifiers can be combined with the fuzzy logic system (Section 3) through weighted majority voting:

```
Complaint -> Feature Extraction -> [RF, XGBoost, SVM] -> ML Predictions
                                                              |
Complaint -> Sentiment Model -> Fuzzy Logic System -> Fuzzy Prediction
                                                              |
                              Weighted Vote                   |
                        (0.4 * fuzzy + 0.2 * RF +            |
                         0.25 * XGB + 0.15 * SVM)            |
                                    |                         |
                              Final Priority (1-4)
```

The fuzzy system receives higher weight because it incorporates domain-specific rules and expert knowledge, while ML models capture statistical patterns from data.

---

## 3. Fuzzy Logic Prioritization System

### 3.1 Current System Analysis

The current prioritization pipeline uses **hard-coded thresholds and linear weighted sums**:

**Severity scoring** (`ai-models/prioritization/severity_score.py`):
```
severity = IMPACT_BASE[business_impact] + ASSET_WEIGHT[asset_type] + (0.3 if safety)
           {low: 0.2, med: 0.5, high: 0.8}   {office: 0, retail: 0.1, warehouse: 0.2}
```

**Urgency scoring** (`ai-models/prioritization/urgency_score.py`):
```
urgency = text_urgency * 0.5 + safety_bonus + recurring_bonus + tier_bonus + type_bonus
```

**Priority calculation** (`ai-models/prioritization/prioritization.py`):
```
sentiment_pressure = max(0.0, -sentiment_score)
raw_score = 1*severity + 1*urgency + 2*sentiment_pressure
priority = clamp(round(raw_score), 1, 4)
```

### 3.2 Problems with Hard Thresholds

1. **Cliff effects**: A severity score of 0.49 rounds to priority 2, while 0.51 rounds to priority 3 - a tiny input difference causes a full priority level jump
2. **Linear-only interactions**: The weighted sum `1*S + 1*U + 2*P` cannot capture non-linear interactions (e.g., moderate severity combined with moderate urgency from a VIP tenant should be treated differently than the same scores from a standard tenant)
3. **No gradual transitions**: The `round()` function creates sharp boundaries between priority levels instead of smooth transitions
4. **Fixed weights**: The 1:1:2 weighting is hardcoded and cannot adapt to different scenarios (e.g., safety-related complaints might need different weighting than noise complaints)

### 3.3 Fuzzy Logic Solution

Fuzzy logic replaces the hard-threshold system with **membership functions** that allow partial membership in multiple categories simultaneously, and **fuzzy rules** that capture expert knowledge about how inputs interact.

**Library**: `scikit-fuzzy` (skfuzzy) - a Python library for fuzzy logic systems.

### 3.4 Fuzzy Input Variables (Antecedents)

Three input variables, each with three membership functions (low, medium, high):

**Variable 1: Sentiment Pressure** [0, 1]
```
    1.0 |  low        medium        high
        | /\          /\            /\
    0.5 |/  \   ____/  \____  ____/  \
        |    \ /              \/      \
    0.0 |     X                X       \
        +-----|-------|-------|---------|
        0    0.2    0.35    0.65     1.0

  low:    trimf [0.0, 0.0, 0.35]     - calm or positive sentiment
  medium: trimf [0.2, 0.5, 0.8]      - moderately negative
  high:   trimf [0.65, 1.0, 1.0]     - strongly negative/angry
```

**Variable 2: Severity** [0, 1]
```
    1.0 |  low        medium        high
        | /\          /\            /\
    0.5 |/  \   ____/  \____  ____/  \
        |    \ /              \/      \
    0.0 |     X                X       \
        +-----|-------|-------|---------|
        0    0.2    0.25    0.6      1.0

  low:    trimf [0.0, 0.0, 0.4]      - minor issue
  medium: trimf [0.25, 0.5, 0.75]    - moderate impact
  high:   trimf [0.6, 1.0, 1.0]      - severe/safety-critical
```

**Variable 3: Urgency** [0, 1]
```
    1.0 |  low        medium        high
        | /\          /\            /\
    0.5 |/  \   ____/  \____  ____/  \
        |    \ /              \/      \
    0.0 |     X                X       \
        +-----|-------|-------|---------|
        0    0.2    0.25    0.6      1.0

  low:    trimf [0.0, 0.0, 0.4]      - no time pressure
  medium: trimf [0.25, 0.5, 0.75]    - moderate urgency
  high:   trimf [0.6, 1.0, 1.0]      - immediate action needed
```

### 3.5 Fuzzy Output Variable (Consequent)

**Priority** [1, 4] with four membership functions:

```
    1.0 | P1(low)    P2(medium)   P3(high)    P4(critical)
        |  /\          /\           /\           /\
    0.5 | /  \   ____/  \____  ___/  \___  ____/  \
        |/    \ /              \/         \/        \
    0.0 |      X                X         X          \
        +------|-------|--------|---------|-----------|
        1     1.5     2       2.5       3           4

  p1_low:      trimf [1.0, 1.0, 2.0]    - low priority
  p2_medium:   trimf [1.5, 2.25, 3.0]   - medium priority
  p3_high:     trimf [2.5, 3.25, 4.0]   - high priority
  p4_critical: trimf [3.0, 4.0, 4.0]    - critical priority
```

### 3.6 Fuzzy Rule Base

12 rules capturing expert knowledge about how input combinations should map to priority:

| # | Severity | Urgency | Sentiment Pressure | Priority | Rationale |
|---|----------|---------|-------------------|----------|-----------|
| 1 | high | high | * | P4 (critical) | Two critical factors demand immediate attention |
| 2 | high | * | high | P4 (critical) | Severe issue + angry customer = escalation |
| 3 | * | high | high | P4 (critical) | Time-critical + distressed customer = escalation |
| 4 | high | medium | * | P3 (high) | Severe issue with some urgency |
| 5 | medium | high | * | P3 (high) | Moderate issue but time-sensitive |
| 6 | medium | * | high | P3 (high) | Moderate issue but very unhappy customer |
| 7 | medium | medium | medium | P2 (medium) | All moderate inputs = standard handling |
| 8 | medium | low | * | P2 (medium) | Moderate impact but no time pressure |
| 9 | low | medium | high | P2 (medium) | Minor issue but customer is upset |
| 10 | low | low | * | P1 (low) | Everything is low = routine |
| 11 | low | low | low | P1 (low) | Explicit: all calm = lowest priority |
| 12 | low | medium | low | P1 (low) | Minor issue, some urgency, customer is calm |

The `*` wildcard means the rule applies regardless of that variable's value.

### 3.7 Defuzzification

The fuzzy inference engine fires all applicable rules simultaneously, computes the aggregate output membership function, and then **defuzzifies** using the **centroid method** (center of gravity):

```
priority_crisp = centroid(aggregate_output_membership)
priority_integer = clamp(round(priority_crisp), 1, 4)
```

This produces a continuous priority score that is then discretized to match the existing 1-4 integer format, maintaining compatibility with the database schema and frontend display.

### 3.8 Feature Flag Integration

The fuzzy system is deployed **side-by-side** with the existing rule-based system via an environment variable:

```
USE_FUZZY_PRIORITY=true   -> Use fuzzy logic for priority calculation
USE_FUZZY_PRIORITY=false  -> Use existing rule-based calculation (default)
```

The modified `prioritization.py` would check this flag and route to the appropriate calculation:

```python
def compute_priority(severity_score, urgency_score, sentiment):
    if os.environ.get("USE_FUZZY_PRIORITY", "false").lower() == "true":
        return compute_priority_fuzzy(severity_score, urgency_score, sentiment)
    else:
        # Existing rule-based logic
        sentiment_pressure = max(0.0, -sentiment)
        raw_score = 1 * severity_score + 1 * urgency_score + 2 * sentiment_pressure
        return max(1, min(4, round(raw_score)))
```

This enables A/B testing and comparison between the two approaches without code changes - just toggle the environment variable.

### 3.9 Comparison: Rule-Based vs Fuzzy

| Input Scenario | Rule-Based | Fuzzy (expected) | Difference |
|---------------|------------|-------------------|------------|
| severity=0.45, urgency=0.45, sentiment=-0.4 | round(0.45+0.45+2*0.4) = round(1.7) = **2** | ~**2.1** -> **2** | Same |
| severity=0.51, urgency=0.51, sentiment=-0.4 | round(0.51+0.51+2*0.4) = round(1.82) = **2** | ~**2.4** -> **2** | Same, but fuzzy shows higher confidence |
| severity=0.8, urgency=0.3, sentiment=-0.9 | round(0.8+0.3+2*0.9) = round(2.9) = **3** | ~**3.4** -> **3** | Fuzzy captures severity+sentiment interaction |
| severity=0.6, urgency=0.6, sentiment=-0.6 | round(0.6+0.6+2*0.6) = round(2.4) = **2** | ~**3.2** -> **3** | Fuzzy prioritizes the all-moderate-high case |

The key difference: fuzzy logic can produce **non-linear interactions** between inputs that the linear weighted sum cannot. In the last example, having all three inputs at moderate-high levels triggers multiple "high" rules simultaneously, pushing the priority higher than the linear sum would suggest.

---

## 4. Security Measures

### 4.1 Current Security Gaps

The following vulnerabilities were identified in the codebase:

| # | Gap | Location | Risk Level |
|---|-----|----------|------------|
| 1 | CORS allows all origins | `backend/api/main.py:9`, `backend/sentiment-service/api.py:23` | Medium |
| 2 | No backend authentication | All API endpoints are open | High |
| 3 | Client-side only auth | `frontend/src/auth/ProtectedRoute.jsx` checks `localStorage` | High |
| 4 | Plaintext password seeds | `database/init.sql` uses `'hash123'` as password_hash | High |
| 5 | No rate limiting | All three FastAPI services | Medium |
| 6 | Minimal input validation | Only empty string check in `api.py:146` | Medium |
| 7 | No inter-service auth | Services communicate freely within Docker network | Low-Medium |
| 8 | Secrets as plain env vars | Third-party credentials passed via docker-compose env vars | Low |

### 4.2 Proposed Security Measures

#### 4.2.1 JWT Authentication

**Purpose**: Replace client-side-only authentication with server-validated JSON Web Tokens.

**Design:**
```
Login Flow:
  Client -> POST /auth/login {email, password}
         <- {access_token (30min), refresh_token (7 days)}

API Request Flow:
  Client -> GET /api/complaints [Authorization: Bearer <access_token>]
         -> Backend validates JWT signature and expiry
         -> Backend extracts user_id and role from token payload
         -> Returns data if authorized

Token Refresh Flow:
  Client -> POST /auth/refresh {refresh_token}
         <- {new_access_token, new_refresh_token}
```

**JWT payload structure:**
```json
{
  "sub": "account_id_here",
  "email": "user@example.com",
  "role": "customer|employee|manager|operator",
  "exp": 1700000000,
  "type": "access"
}
```

**Role-based access control:**
- `customer`: Can only access own complaints, chatbot, and profile
- `employee`: Can view assigned complaints, update status, generate reports
- `manager`: Can view all complaints, approve escalations, view trends
- `operator`: Can view model analytics, chatbot performance

**Dependencies**: `python-jose[cryptography]` (JWT encoding/decoding), `passlib[bcrypt]` (password hashing)

**Files to create:**
- `backend/auth/__init__.py`
- `backend/auth/jwt_handler.py` - Token creation and validation
- `backend/auth/dependencies.py` - FastAPI dependency injection for route protection
- `backend/auth/password.py` - bcrypt hashing utilities
- `backend/auth/routes.py` - Login, refresh, and registration endpoints

#### 4.2.2 Password Hashing (bcrypt)

**Purpose**: Replace plaintext `'hash123'` seed data with properly hashed passwords.

**Implementation:**
```python
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Hashing (during registration or seed data generation)
hashed = pwd_context.hash("user_password_here")
# Result: "$2b$12$LJ3m4ys..." (60-character bcrypt hash)

# Verification (during login)
is_valid = pwd_context.verify("user_password_here", hashed)
```

**Changes required:**
- Update `database/init.sql` seed data to use bcrypt-hashed passwords
- Create a seed data generation script that hashes passwords before insertion
- Update any login endpoint to use `pwd_context.verify()` instead of string comparison

#### 4.2.3 CORS Restriction

**Purpose**: Restrict Cross-Origin Resource Sharing to known frontend origins.

**Current (insecure):**
```python
allow_origins=["*"]  # Any website can call our API
```

**Proposed:**
```python
ALLOWED_ORIGINS = os.environ.get(
    "ALLOWED_ORIGINS",
    "http://localhost:5173"  # Default: local Vite dev server
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)
```

**Files to modify:**
- `backend/api/main.py` (line 9)
- `backend/sentiment-service/api.py` (line 23)
- `backend/chatbot/app.py`
- Add `ALLOWED_ORIGINS` to `.env.example` and `docker-compose.yml`

#### 4.2.4 Rate Limiting

**Purpose**: Prevent abuse, brute-force attacks, and denial-of-service.

**Implementation** using `slowapi`:

```python
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

# Per-endpoint limits
@app.post("/auth/login")
@limiter.limit("5/minute")        # Brute-force protection
async def login(...): ...

@app.post("/analyze")
@limiter.limit("30/minute")       # Compute-intensive
async def analyze_text(...): ...

@app.post("/analyze-compare")
@limiter.limit("10/minute")       # Multi-model, very intensive
async def analyze_compare(...): ...

@app.post("/api/chat")
@limiter.limit("20/minute")       # LLM inference
async def chat(...): ...

@app.post("/transcribe")
@limiter.limit("10/minute")       # Audio processing
async def transcribe(...): ...
```

**Dependency**: `slowapi>=0.1.9`

#### 4.2.5 Input Validation and Sanitization

**Purpose**: Prevent injection attacks and enforce input constraints.

**Implementation** using Pydantic validators:

```python
from pydantic import BaseModel, validator, constr
import bleach

class SanitizedTextInput(BaseModel):
    text: constr(min_length=1, max_length=10000)

    @validator('text')
    def sanitize_text(cls, v):
        # Strip HTML/script tags to prevent XSS
        cleaned = bleach.clean(v, tags=[], strip=True)
        # Remove null bytes
        cleaned = cleaned.replace('\x00', '')
        if not cleaned.strip():
            raise ValueError("Text cannot be empty after sanitization")
        return cleaned
```

**Apply to:**
- Sentiment API: Replace `TextInput` with `SanitizedTextInput`
- Chatbot API: Add length limit and sanitization to chat messages
- Transcription API: Validate audio file size and type

**Dependency**: `bleach>=6.0.0`

#### 4.2.6 Inter-Service Authentication

**Purpose**: Prevent unauthorized services from calling internal APIs.

**Implementation**: Shared API key between services within the Docker network.

```python
INTERNAL_API_KEY = os.environ.get("INTERNAL_API_KEY")

async def verify_internal_service(
    x_api_key: str = Header(None, alias="X-Internal-API-Key")
):
    if not INTERNAL_API_KEY or x_api_key != INTERNAL_API_KEY:
        raise HTTPException(status_code=403, detail="Invalid service key")
```

**Application**: The whisper service calls the sentiment service internally - this call should require the API key. Frontend-facing endpoints use JWT instead.

#### 4.2.7 Security Summary Table

| Measure | Complexity | Impact | Priority |
|---------|-----------|--------|----------|
| JWT Authentication | Medium | High - prevents unauthorized access | 1 (implement first) |
| Password Hashing | Low | High - prevents credential exposure | 1 |
| CORS Restriction | Low | Medium - prevents cross-origin attacks | 2 |
| Rate Limiting | Low | Medium - prevents abuse | 2 |
| Input Sanitization | Low | Medium - prevents injection | 3 |
| Inter-Service Auth | Low | Low-Medium - defense in depth | 3 |

---

## 5. Dependencies & Integration Summary

### 5.1 New Python Packages

**Backend sentiment service** (`backend/sentiment-service/requirements.txt`):
```
vaderSentiment>=3.3.2          # VADER sentiment model
```

**Backend main** (`backend/requirements.txt`):
```
python-jose[cryptography]>=3.3.0   # JWT tokens
passlib[bcrypt]>=1.7.4             # Password hashing
slowapi>=0.1.9                     # Rate limiting
bleach>=6.0.0                      # Input sanitization
scikit-fuzzy>=0.4.2                # Fuzzy logic
```

**AI models** (new requirements file for classifiers):
```
xgboost>=2.0.0                     # Gradient boosting classifier
scikit-learn>=1.3.0                # RF, SVM, TF-IDF, metrics
scikit-fuzzy>=0.4.2                # Fuzzy logic
```

**BiLSTM specific**:
- GloVe 6B 300d embeddings (~1GB download, stored in `ai-models/ml-models/sentiment-model/data/embeddings/`)
- PyTorch (already available)

### 5.2 New Files to Create

| File | Purpose |
|------|---------|
| `backend/sentiment-service/vader_predictor.py` | VADER model predictor |
| `backend/sentiment-service/bilstm_predictor.py` | BiLSTM model predictor |
| `backend/sentiment-service/model_router.py` | Multi-model routing |
| `backend/sentiment-service/base_predictor.py` | Abstract predictor interface |
| `ai-models/ml-models/sentiment-model/src/bilstm_architecture.py` | BiLSTM model definition |
| `ai-models/ml-models/sentiment-model/src/train_bilstm.py` | BiLSTM training script |
| `ai-models/ml-models/sentiment-model/src/benchmark.py` | Model comparison framework |
| `ai-models/ml-models/classifiers/priority_classifiers.py` | RF + XGBoost + SVM |
| `ai-models/ml-models/classifiers/train_classifiers.py` | Classifier training |
| `ai-models/ml-models/classifiers/classifier_benchmark.py` | Classifier comparison |
| `ai-models/prioritization/fuzzy_prioritization.py` | Fuzzy logic system |
| `ai-models/prioritization/fuzzy_config.py` | Tunable membership parameters |
| `backend/auth/jwt_handler.py` | JWT creation/validation |
| `backend/auth/dependencies.py` | FastAPI auth dependencies |
| `backend/auth/password.py` | bcrypt utilities |
| `backend/auth/routes.py` | Auth endpoints |
| `backend/middleware/rate_limiter.py` | Rate limiting config |
| `backend/middleware/input_validation.py` | Sanitization utilities |
| `backend/middleware/service_auth.py` | Inter-service API key |

### 5.3 Existing Files to Modify

| File | Change |
|------|--------|
| `backend/sentiment-service/api.py` | Add model selection, `/analyze-compare` endpoint, auth, CORS, rate limiting |
| `backend/api/main.py` | Add auth routes, CORS restriction, rate limiting |
| `ai-models/prioritization/prioritization.py` | Add fuzzy logic feature flag |
| `backend/sentiment-service/requirements.txt` | Add vaderSentiment |
| `backend/requirements.txt` | Add security packages |
| `.env.example` | Add new environment variables |
| `docker-compose.yml` | Add new env vars to service definitions |

### 5.4 New Environment Variables

```env
# Model selection
SENTIMENT_MODEL=roberta          # mock|roberta|vader|bilstm|all

# Fuzzy logic
USE_FUZZY_PRIORITY=false         # true|false

# Security
JWT_SECRET_KEY=your-secret-key-here
INTERNAL_API_KEY=your-internal-key-here
ALLOWED_ORIGINS=http://localhost:5173
```

### 5.5 Implementation Phasing

| Phase | Scope | Estimated Effort |
|-------|-------|-----------------|
| **Phase 1** | Security (JWT, bcrypt, CORS, rate limiting, input validation) | Medium |
| **Phase 2** | Sentiment models (BasePredictor, VADER, model router, /analyze-compare) | Medium |
| **Phase 3** | Fuzzy logic prioritization + feature flag | Low-Medium |
| **Phase 4** | BiLSTM architecture + training script + predictor | Medium |
| **Phase 5** | Classification models (RF, XGBoost, SVM) + training | Medium |
| **Phase 6** | Benchmark framework + comparison reports | Low-Medium |
| **Phase 7** | Integration testing + Docker updates | Low |

### 5.6 Testing Strategy

**Unit tests** (per component):
- VADER predictor: Output range validation, edge cases (empty text, all caps, emojis)
- BiLSTM predictor: Output format compliance, batch processing
- Fuzzy system: All input extremes produce valid 1-4 output, gradual transitions verified
- JWT: Token creation, validation, expiry, invalid tokens, role checking
- Classifiers: Output format, cross-validation scores

**Integration tests:**
- End-to-end auth flow: login -> get token -> call protected endpoint -> verify
- Multi-model comparison: `/analyze-compare` returns valid results from all models
- Fuzzy vs rule-based: Both systems produce same-range output for identical inputs
- Rate limiting: Verify 429 status after exceeding limits

**Comparison tests:**
- Benchmark all three sentiment models on same test dataset
- Compare fuzzy vs rule-based priority on a set of edge cases
- Run all three classifiers on cross-validation splits, report metrics
