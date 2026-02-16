# Synthetic Complaint Classification Pipeline

## Overview

This project builds a labeled dataset for training ML models to predict:

* business_impact (low / medium / high)
* safety_concern (true / false)

Data source: industrial property tenant call transcripts.

The pipeline is divided into two stages:

1. Preprocessing
2. Complaint-only LLM labeling

## Project Files

DataSet_SentimentAnalysis.csv
preprocess.py
llm.py
Synth_DataSet_Preprocessed.csv
Synth_DataSet_Labeled_Final.csv

## Stage 1 – Preprocessing

Run:
python preprocess.py

What it does:

* Creates a frequency column (counts duplicate transcripts)
* Removes duplicate transcripts (prevents data leakage and memorization)
* Extracts tenant-only speech into user_text
* Normalizes call_category:
  Leasing Inquiry → inquiry
  Tenant Support → complaint
* Assigns tenant_tier:
  inquiry → Prospective
  complaint → Standard / Premium / VIP (60/30/10 weighted)

Output:
Synth_DataSet_Preprocessed.csv

## Stage 2 – LLM Labeling

Run:
python llm.py

Important rule:
The LLM runs ONLY on complaints.

Inquiries are explicitly set to:
business_impact = None
safety_concern = None

This prevents severity misclassification of leasing calls.

## Model Configuration

Model: gemma:2b
Runtime: Ollama (local)
Temperature: 0
Output: strict JSON

business_impact logic:

* high → meaningful operational disruption
* medium → partial/manageable disruption
* low → minor inconvenience

safety_concern logic:
True only if explicit physical hazard exists:
fire, sparks, exposed wiring, gas leak,
flooding near electrical systems,
structural collapse risk,
injury hazard,
electrical shock risk

Security or access issues alone are NOT safety hazards.

## Output

Synth_DataSet_Labeled_Final.csv

Each run prints:

* Complaint count
* Inquiry count
* Business impact distribution
* Safety distribution

## Engineering Decisions

* Duplicate removal before labeling
* Strict complaint vs inquiry separation
* Deterministic LLM output
* Explicit hazard constraints
* Distribution validation after each run

## Known Limitations

* Small 2B parameter model
* Tendency toward class collapse (e.g., all medium)
* Limited complaint sample size
* Severity classification is inherently subjective
