# Synthetic Complaint Classification Pipeline

## Overview

This project builds a labeled dataset for training ML models to predict:
- `business_impact` (low / medium / high)
- `safety_concern` (true / false)

**Data source:** Industrial property tenant call transcripts.

The pipeline runs in a **single script** (`preprocess.py`) that handles all preprocessing and labeling in one pass.

---

## Project Files

```
DataSet_SentimentAnalysis.csv     ← raw input
preprocess.py                     ← single pipeline script
Synth_DataSet_Labeled_Final.csv   ← final output
```

---

## Pipeline – Single Script

Run:
```bash
python preprocess.py
```

### What it does (in order):

1. **Frequency count** — counts duplicate transcripts before removal
2. **Transcript deduplication** — removes duplicate transcripts to prevent data leakage
3. **Tenant speech extraction** — isolates tenant-only lines into `user_text` (one line per sentence)
4. **Normalize `call_category`**
   - `Leasing Inquiry` → `inquiry`
   - `Tenant Support` → `complaint`
5. **Assign `tenant_tier`**
   - `inquiry` → `Prospective`
   - `complaint` → `Standard / Premium / VIP` (60/30/10 weighted, seed=42)
6. **Extract `issue`** — captures all sentences starting with "we are facing" from `user_text` (complaints only)
7. **Issue deduplication + recount** — deduplicates on `issue`, recounts frequency per unique issue
8. **Apply manual labels** — matches `issue` against hardcoded labels by substring (complaints only)
9. **Null labels for inquiries** — `business_impact` and `safety_concern` are explicitly set to `None`

---

## Labeling Approach

Labels are **manually assigned** by matching the extracted `issue` against a hardcoded keyword dictionary.

```
No LLM. No external API. Fully deterministic.
```

### Why not LLM?

`gemma:2b` was tested for automated labeling but consistently failed to produce valid JSON output, defaulting to markdown-style responses regardless of prompt engineering or few-shot examples. The model is too small for reliable structured output.

### Manual Label Map

| Issue Type             | business_impact | safety_concern |
|------------------------|-----------------|----------------|
| security incident      | high            | true           |
| power outage           | high            | true           |
| parking gate malfunction | medium        | false          |
| air conditioning       | medium          | false          |
| cleaning services      | low             | false          |
| water leakage          | low             | false          |
| noise disturbance      | low             | false          |
| lost item              | low             | false          |
| access card            | low             | false          |

To add a new issue: insert a new entry into `MANUAL_LABELS` at the top of `preprocess.py`.

### Label Decisions

- **Water leakage** → `low` — minor inconvenience unless explicitly near electrical systems
- **Access card** → `low` — access/security issues alone are not safety hazards
- **Recurrence is ignored** — labels are based solely on issue type, not whether the issue was previously reported

---

## Output

**`Synth_DataSet_Labeled_Final.csv`**

Each run prints:
- Complaint and inquiry counts
- Business impact distribution
- Safety concern distribution
- Any unmatched complaints (issues that hit no keyword — add a rule for these)

---

## Engineering Decisions

- Single-script pipeline — preprocessing and labeling in one pass
- Duplicate removal at both transcript and issue level
- Strict complaint vs. inquiry separation throughout
- Manual labels over LLM — deterministic, auditable, zero latency
- Unmatched complaint surfacing — new issue types are flagged at runtime

---

## Known Limitations

- Small complaint sample size (9 unique complaints)
- Keyword matching will miss paraphrased or novel issue descriptions
- Severity classification is inherently subjective — labels reflect one set of business rules
- `issue` extraction depends on "we are facing" phrasing — transcripts that deviate from this pattern will not be labeled

---

## Dataset Findings

These were discovered during preprocessing and shaped the final pipeline design.

**Only 9 unique complaints exist in the entire dataset.**
The raw CSV contained 401 total rows — 392 of which were inquiries. Of the remaining complaints, deduplication at the transcript level and then at the issue level reduced them to 9 unique issue types. This made LLM-based labeling unnecessary and manual labeling the most practical approach.

**All complaints follow a rigid template.**
Every complaint transcript follows the exact same structure:
```
Tenant: We are facing [issue].
Tenant: This was reported earlier but hasn't been resolved.
Agent: I see the ticket is still open.
Tenant: This is affecting our daily operations.
```
Because every transcript contained identical recurrence and impact language, these phrases carried zero signal for classification. The only meaningful input was the issue type in the first line — which is why labels are based solely on issue type and recurrence is explicitly ignored.

**The "all medium" collapse was a model size problem, not a prompt problem.**
Significant effort was spent engineering prompts for `gemma:2b` — zero-shot with rules, zero-shot with a lookup table, few-shot with 9 examples, and a stripped-down compact format. All approaches failed. The model consistently ignored the JSON format instruction and returned markdown-style output. This was diagnosed as a fundamental limitation of 2B parameter models for structured output tasks, not a fixable prompt issue. A larger model (7B+) would likely work, but was not available in this environment.