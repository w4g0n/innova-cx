# V2 Synthesizer vs V4 Synthesizer — Full Comparison

## 1. Data Format

| Aspect | V2 Synthesizer | V4 Synthesizer |
|--------|---------------|----------------|
| **Output format** | Multi-speaker call transcripts | Plain-text email-style ticket messages |
| **Speaker labels** | `Tenant:`, `Agent:`, `Caller:` per line, separated by `\n` | None — single paragraph of text |
| **Text column name** | `transcript` | `ticket_details` |
| **Record type identifier** | `call_category` ("Tenant Support" / "Leasing Inquiry") | `ticket_type` ("Complaint" / "Inquiry") |
| **Example complaint** | `Agent: Support Desk, how may I assist?\nTenant: We've had complete power outage for three days now.\nTenant: all our systems are down\nAgent: I understand. Can I confirm your location?\nTenant: Zone A, office.` | `Good afternoon, During our regular operations, we identified that the power instability persists within our premises. Operational efficiency has been noticeably impacted. We would appreciate your assistance in resolving this matter.` |

## 2. Schema

| Column | V2 | V4 |
|--------|----|----|
| `call_id` / `ticket_id` | ✅ `call_id` (IP-YYYYMM-NNNNN) | ✅ `ticket_id` (cxNNNNN) |
| `transcript` / `ticket_details` | ✅ `transcript` | ✅ `ticket_details` |
| `call_category` / `ticket_type` | ✅ `call_category` | ✅ `ticket_type` |
| `tenant_tier` | ✅ (Standard/Premium/VIP) | ❌ absent |
| `asset_type` | ✅ (Office/Warehouse/Retail Store) | ❌ absent |
| `location` | ✅ (7 zones) | ❌ absent |
| `issue_type` / `issue_category` | ✅ `issue_type` (free text) | ✅ `issue_category` (categorical) |
| `issue_severity` | ✅ (critical/high/medium/low) | ❌ absent |
| `business_impact` | ✅ (low/medium/medium-high/high) | ✅ (low/medium/high) |
| `safety_concern` | ✅ | ✅ |
| `is_recurring` | ✅ | ❌ absent |
| `timestamp` | ✅ | ❌ absent |

## 3. Content Variety

| Aspect | V2 | V4 |
|--------|----|----|
| **Complaint issue types** | 48 (8 critical + 10 high + 12 medium + 18 low) | 20 |
| **Inquiry types** | 5 inquiry personas with 5–9 questions each | 20 categories, all use same sentence |
| **Unique phrases per issue** | 4 per issue = 192 total | 0 — no issue-specific phrases |
| **Conversation structures** | 4 (standard, direct, narrative, multi-exchange) | 1 fixed template |
| **Emotional tone library** | 50 phrases across 5 tones | 0 — no emotional variation |
| **Duration references** | 10 phrases ("since yesterday" → "for nearly a month") | 0 |
| **Complaint template** | Variable: different openings, mid-sections, closings | Fixed: `greeting → background → "the {issue} persists within our premises" → clarification → consequence → expectation` |
| **Inquiry template** | Multi-turn conversation with agent Q&A | Fixed: `greeting → "We would like clarification regarding {issue}" → planning note → "Kindly advise us on the appropriate steps moving forward"` |

## 4. Pipeline Compatibility

This is the critical section. Here is every component in the InnovaCX pipeline and which synthesizer it's compatible with.

### 4a. FeatureEngineeringAgent / preprocess.py

```python
# What preprocess.py does:
df["call_category"] = df["call_category"].astype(str).str.strip().str.lower()
df = df[df["call_category"] == "tenant support"]          # Filters by call_category
df["clean_text"] = df["transcript"].apply(extract_tenant_speech)  # Reads 'transcript' column

def extract_tenant_speech(transcript):
    lines = transcript.split("\n")
    for line in lines:
        if line.lower().startswith("tenant:"):       # Extracts only Tenant: lines
            content = line.split(":", 1)[1].strip()
            tenant_lines.append(content)
    return " ".join(tenant_lines).lower()
```

| | V2 | V4 |
|-|----|----|
| Has `call_category` column | ✅ | ❌ has `ticket_type` |
| Has `transcript` column | ✅ | ❌ has `ticket_details` |
| Has `Tenant:` speaker labels | ✅ | ❌ plain text |
| **preprocess.py compatible** | ✅ **YES** | ❌ **NO — extracts 0 text** |

### 4b. SentimentAnalysisAgent / data_preparation.py

```python
if 'transcript' not in df.columns:
    raise ValueError("CSV must have 'transcript' column")
text = str(row['transcript'])
```

| | V2 | V4 |
|-|----|----|
| **data_preparation.py compatible** | ✅ **YES** | ❌ **NO — raises ValueError** |

### 4c. Sentiment Steps (step1, step2, step3)

- **step1_deduplicate.py**: Expects `transcript` column → V2 ✅, V4 ❌
- **step2_augment.py**: Expects `transcript` column, outputs `proxy_sentiment`, `proxy_urgency`, `proxy_keywords_str` + 10 text features → V2 ✅, V4 ❌
- **step3_compare_models.py**: Expects `proxy_sentiment` column from step2 → V2 ✅, V4 ❌

### 4d. Backend Sentiment Service (api.py + inference.py)

```python
class TextInput(BaseModel):
    text: str           # Accepts plain text at inference time

result = predictor.predict(input.text)   # Passes raw text to RoBERTa
```

At **inference time** (production), the sentiment service accepts plain text via API — no speaker labels needed. This is because by the time a complaint reaches the API, Whisper has already transcribed the audio into plain text, or the user typed text directly in the form.

| | V2 | V4 |
|-|----|----|
| **Inference API compatible** | ✅ (after preprocess extracts tenant speech) | ✅ (text is already plain) |

**However:** The model must be **trained** before it can serve inference. Training requires step1→step2→step3, which only works with V2 format. V4 format cannot produce the trained model that the service loads.

### 4e. Frontend (CustomerFillForm.jsx)

```javascript
// Text complaint: user types in textarea → sent as { text: message }
const sentiment = await analyzeSentiment(message);

// Audio complaint: recorded → Whisper transcribes → plain text
const data = await transcribeAudio(blob, filename);
// data.transcript is plain text (Whisper output, no speaker labels)
await analyzeCombinedSentiment(data.transcript, data.audio_features);
```

The frontend sends **plain text** to the sentiment API. Neither format matters here — the frontend doesn't use the training dataset directly.

### 4f. Whisper Transcription Pipeline

```python
# whisper_transcribe.py output:
return " ".join(segment.text for segment in segments).strip()
# Returns: plain text, no speaker labels
```

In production, Whisper produces plain text without speaker labels. The V2 synthesizer's `Tenant:` / `Agent:` labels simulate the full call recording (both sides), but preprocess.py strips it down to tenant-only speech for training. At inference time, the model receives plain text.

**This is the key architectural insight:**

The training data needs `Tenant:` labels so that preprocess.py can extract **only the tenant's speech** (not the agent's). This is important because:
1. The agent's speech is formulaic ("I'm sorry to hear that", "We'll look into it") and carries no complaint sentiment
2. If the model trains on agent + tenant speech together, it learns "I'm sorry" = negative sentiment (wrong — that's the agent being polite, not the tenant being upset)
3. At inference time, the model receives only the tenant's text (either typed directly or Whisper-transcribed from a one-sided voice recording)

V4's plain text mixes complaint language with formulaic business English ("We would appreciate your assistance", "Kindly advise") in a way that doesn't separate who is expressing what.

### 4g. DSPy Priority Scoring

```python
# signals.py expects these from the sentiment service:
text_sentiment: float    # From RoBERTa
audio_sentiment: float   # From audio_sentiment_combiner
urgency: float          # From RoBERTa
keywords: List[str]     # From RoBERTa
```

DSPy consumes the **outputs** of the sentiment model, not the raw text. It doesn't care about the dataset format — it cares about the quality of the model's predictions, which depends on training data quality.

### 4h. Database (init.sql)

```sql
CREATE TABLE tickets (
    details             TEXT NOT NULL,       -- complaint text
    ticket_type         ticket_type,         -- 'Complaint' or 'Inquiry'
    sentiment_score     NUMERIC(4,3),        -- model output
    sentiment_label     TEXT,                -- model output
    model_priority      ticket_priority,     -- DSPy output
    ...
);
```

The database stores `details` (plain text) and model outputs. It doesn't store raw transcripts with speaker labels — by this point, preprocessing has already happened.

### 4i. Unified Complaint Analyzer

```python
# The full production pipeline:
# 1. Audio in → Whisper transcribes → plain text
# 2. librosa extracts audio features → audio_sentiment_combiner
# 3. Plain text → RoBERTa → text_sentiment + urgency + keywords
# 4. Combine text + audio sentiment (70/30 weight)
# 5. All signals → DSPy → priority score
```

The analyzer takes audio as input and produces structured outputs. The training data format affects step 3 (RoBERTa quality). V2's preprocessed tenant speech more closely matches what RoBERTa will see at inference time.

## 5. Augmentation Quality

| Aspect | V2 (with step2_augment.py) | V4 (with synthesizerv4/augment.py) |
|--------|---------------------------|-----------------------------------|
| **Synonym source** | Curated domain dictionary (80 word groups, intensity-matched) | Raw WordNet (context-blind) |
| **Augmentation cap** | Fixed 3x multiplier | Uncapped — some records get 95 copies |
| **Label preservation** | Proxy re-scoring with Gaussian noise (σ=0.04), drift rejection (>0.15) | Binary keyword matching ("halt" → high, "affect" → medium) |
| **Techniques** | 6: synonym replacement, word deletion, word insertion, sentence shuffle, ASR noise injection, template synthesis | 3: synonym replacement, word deletion, sentence shuffle |
| **Quality outcome** | Grammatically coherent augmentations | Produces broken text: "charitable rede us on the allow stairs", "We this can be address promptly", "benevolent rede us on allow steps" |

## 6. What V4 Lacks for the Pipeline

To use V4 format with the existing pipeline, you would need to rewrite:

1. **preprocess.py** — Remove `extract_tenant_speech()`, change column references from `transcript` → `ticket_details`, `call_category` → `ticket_type`, remove `tenant_tier`/`asset_type` dependency in `adjust_impact()`
2. **data_preparation.py** — Change `transcript` → `ticket_details`
3. **step1_deduplicate.py** — Change column reference
4. **step2_augment.py** — Change column reference, adjust proxy labeler (V4 text is formal business English vs V2's conversational complaint language)
5. **step3_compare_models.py** — Change column reference

Or equivalently, add a compatibility shim that renames columns. But the deeper issue remains: V4's text is fundamentally different from what the model will see at inference time (real complaints from frustrated tenants).

## 7. Verdict

**V2 is the correct choice for the InnovaCX project.** The reasons:

1. **Zero code changes needed** — V2 output feeds directly into preprocess.py → step1 → step2 → step3 → trained model → sentiment service → production. V4 requires rewriting multiple pipeline components.

2. **Architectural alignment** — The project was designed around a voice-first complaint pipeline: tenant calls → Whisper transcribes → RoBERTa analyzes tenant speech. V2's multi-speaker transcripts with `Tenant:` labels simulate this flow. V4's email-style tickets simulate a different product (written ticket system).

3. **Training/inference consistency** — V2's preprocess.py extracts tenant-only speech, which matches what RoBERTa sees at inference time (user-typed text or Whisper output). V4's formal business English ("We would appreciate your assistance in resolving this matter") doesn't match how real tenants speak when they're frustrated about a broken AC.

4. **Richer training signal** — V2 has 48 issue types, 4 conversation structures, 192 issue-specific phrases, emotional tone variation, and duration references. V4 has 20 issue types, 1 fixed template, and 0 issue-specific phrases.

5. **Augmentation quality** — V2's step2 uses a curated domain dictionary and produces coherent text. V4's augment.py uses raw WordNet and produces grammatically broken text.

6. **Metadata completeness** — V2 provides `tenant_tier`, `asset_type`, `location`, `issue_severity`, `is_recurring`, and `timestamp` which are used by preprocess.py's `adjust_impact()` function and could be valuable for the rule-based prioritization module. V4 has none of these.
