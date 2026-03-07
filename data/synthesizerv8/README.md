# Synthesizer V8

Generates a 10,000-row labeled complaint dataset for feature engineering training.

## What this produces

`output/final_dataset.csv` — 10,000 office-tenant complaints with 4 labels:

| Column | Values |
|--------|--------|
| `ticket_id` | V8-00000 … V8-09999 |
| `subject` | 3–8 word problem summary |
| `text` | full complaint body |
| `domain` | one of 15 office domains |
| `style` | one of 12 writing styles |
| `issue_hint` | issue type used at generation time |
| `issue_severity` | low / medium / high |
| `issue_urgency` | low / medium / high |
| `safety_concern` | True / False |
| `business_impact` | low / medium / high |

## Setup

```bash
pip install -r requirements.txt
huggingface-cli login          # required for Phi-4-mini-instruct (accept the license)
```

Accept the Phi-4-mini license at: https://huggingface.co/microsoft/Phi-4-mini-instruct

## Run

```bash
# Full run (unattended — ~8 hours on T4 GPU)
python run_pipeline.py

# If it crashes at any point, resume from last checkpoint:
python run_pipeline.py --resume

# Quick sanity check before committing to a full run:
python run_pipeline.py --dry-run
```

## Pipeline Phases

| Phase | Script | What it does | Time (T4) |
|-------|--------|-------------|-----------|
| 1 | `phase1_generate.py` | Phi-4-mini generates 10,000 complaints | ~3.5 hrs |
| 2 | `phase2_deduplicate.py` | TF-IDF removes near-duplicate complaints | ~2 mins |
| 3 | `phase3_label.py` | Phi-4-mini labels each complaint with 4 features | ~4.5 hrs |
| 4 | `phase4_validate.py` | Checks class balance, produces final_dataset.csv | ~30 secs |

**Total: ~8 hours.** Each phase checkpoints every 100 rows — if interrupted, re-run with `--resume`.

## Checkpoints and Resume

Both generation (Phase 1) and labeling (Phase 3) checkpoint to disk every 100 rows:

```
output/phase1_checkpoint.csv   ← generation progress
output/phase3_checkpoint.csv   ← labeling progress
```

If the process crashes, simply re-run:
```bash
python run_pipeline.py --resume
```

The pipeline will detect which phases are complete (by checking for output files) and skip them. Phases 1 and 3 will resume from their last checkpoint row.

## Other useful commands

```bash
# Start from a specific phase (previous phase outputs must exist)
python run_pipeline.py --resume --start-phase 3

# Skip a phase entirely (use existing output)
python run_pipeline.py --resume --skip-phase 2

# Run phases individually
python phase1_generate.py --resume
python phase2_deduplicate.py
python phase3_label.py --resume
python phase4_validate.py
```

## Output files

```
output/
├── phase1_checkpoint.csv      ← generation progress (overwritten on resume)
├── phase1_complete.csv        ← all generated complaints
├── phase2_deduplicated.csv    ← after near-duplicate removal
├── phase2_stats.json          ← dedup statistics
├── phase3_checkpoint.csv      ← labeling progress (overwritten on resume)
├── phase3_complete.csv        ← all labeled complaints
├── phase4_report.json         ← validation results (PASS/WARN/FAIL per check)
└── final_dataset.csv          ← THE DELIVERABLE
```

## Validation checks (Phase 4)

Phase 4 will exit with an error if any check FAILS:

| Check | Threshold | Status |
|-------|-----------|--------|
| Row count | ≥ 10,000 = PASS, ≥ 9,500 = WARN | FAIL if < 9,500 |
| Label value coverage | all 3 values present per label | FAIL if any missing |
| Class balance | no class < 8% within a label | WARN if below |
| Safety rate | 15%–40% = PASS | WARN if outside |
| Domain coverage | all domains ≥ 0.5% | WARN if low |

## Hardware requirements

- **GPU**: T4 (16GB VRAM) or better. The pipeline auto-selects 8-bit (Phase 1) or 4-bit (Phase 3) quantization to fit within 16GB.
- **CPU fallback**: supported but extremely slow (~50× slower than GPU).
- **Disk**: ~2GB for model cache + ~200MB for output files.
- **RAM**: 8GB minimum.

## Why V8 over previous synthesizers

| Issue in V1–V7 | Fix in V8 |
|---------------|-----------|
| Template-based → model memorizes phrases | Phi-4-mini generates fully original text |
| V4: wrong format (no `Tenant:` labels needed) | Plain text — matches Orchestrator's Feature Engineering agent input |
| V7: 25% rows wasted on inquiries | Complaints only — 100% of 10K rows are useful |
| V7: DeBERTa zero-shot labels are inconsistent | Phi-4 few-shot labels are consistent (same model used in training) |
| No resume on generation crash | Phase 1 and 3 checkpoint every 100 rows |
| Dedup was a separate disconnected step | Built into Phase 2 |
| No class balance validation | Phase 4 checks all label distributions |
| V7-Phase2: only 2,000 complaints | 10,000 complaints |
