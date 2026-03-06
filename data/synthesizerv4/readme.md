# Synthetic Tenant Ticket Dataset Generator

## Overview

This system generates a large-scale, structured dataset of tenant support tickets designed for machine learning experimentation. It produces realistic complaint and inquiry texts with embedded business impact and safety signals derived directly from language content.

The dataset is suitable for training and evaluating:

- Complaint vs Inquiry classifiers
- Business Impact prediction models (low / medium / high)
- Safety Concern detection models (true / false)
- Embedding-based similarity systems
- Multi-label and hierarchical classification pipelines

The system emphasizes linguistic realism, statistical coherence, and controlled label correlation.

---

## Dataset Structure

Each record contains:

| Column | Description |
|---------|-------------|
| `ticket_id` | Unique ticket identifier (e.g., cx00001) |
| `ticket_type` | Complaint or Inquiry |
| `ticket_details` | Full natural-language tenant message |
| `issue_category` | Operational category label |
| `business_impact` | low / medium / high (null for inquiries) |
| `safety_concern` | true / false (null for inquiries) |

Inquiries do not contain business impact or safety labels by design.

---

## Design Philosophy

### 1. Text-Driven Labeling

Business impact and safety concern are embedded in the language itself. No structured metadata (tenant tier, asset type, recurrence flags) influences labels.

This ensures:

- Labels are derivable from text alone
- No hidden leakage
- No deterministic category → label mapping
- Realistic classification difficulty

---

### 2. Narrative Realism

Tickets are generated as natural, email-style messages rather than short structured fragments.

Each complaint may include:

- Greeting or framing
- Context and background
- Clarification details
- Operational consequences
- Safety signals (when present)
- Expectation or closing statements

This improves:

- Embedding realism
- Linguistic diversity
- Contextual depth
- Model generalization

---

### 3. Controlled Statistical Correlation

Safety concern and business impact are correlated probabilistically.

- High-impact complaints are more likely to contain safety language.
- Low-impact complaints are less likely to contain safety language.
- Overlap exists between categories to prevent deterministic coupling.

This creates:

- Realistic operational patterns
- Measurable statistical association
- Non-trivial classification behavior

---

### 4. Balanced Class Distribution

Augmentation is performed per class with controlled target ratios.

This prevents:

- Complaint dominance
- Inquiry underrepresentation
- Classifier bias due to imbalance
- Artificial distribution drift

Final ratios are configurable.

---

### 5. Safe Augmentation Strategy

The augmentation pipeline applies:

- WordNet-based synonym replacement
- Minor word deletion
- Sentence reordering
- Conservative re-scoring of labels

Augmented samples are only retained if:

- Business impact remains consistent
- Safety label remains consistent

This preserves label integrity while increasing linguistic variance.

---

## Intended Use Cases

This dataset is designed for:

- Prototyping ML classification systems
- Evaluating embedding models
- Testing multi-label pipelines
- Simulating operational tenant ticket flows
- Benchmarking NLP models in controlled environments

It is not intended to replicate any real tenant data.

---

## Statistical Properties

- Complaint and inquiry classes are balanced.
- Business impact is distributed across low, medium, and high categories.
- Safety concern correlates with impact but is not deterministically derived.
- No exact duplicate ticket texts remain.
- Issue categories do not dominate specific impact labels.

---

## Why This Approach

This system was designed to avoid common synthetic dataset flaws:

- No template-only short sentences
- No category-to-label shortcuts
- No metadata leakage
- No perfect label separability
- No uncontrolled augmentation bias

The result is a clean, structurally coherent dataset that supports realistic NLP experimentation while maintaining controlled statistical behavior.

---

## Output Files

- `synthetic_dataset.csv` — Base generated dataset
- `synthetic_dataset_augmented.csv` — Balanced, augmented dataset

---

## Summary

This system produces a linguistically realistic, statistically controlled synthetic dataset for tenant support ticket modeling. Labels are embedded in natural language, distributions are balanced, and correlations reflect plausible operational patterns.

The dataset is ready for downstream modeling, evaluation, and embedding experimentation.