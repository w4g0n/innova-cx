"""
Phase 3 — Few-Shot Labeling with Phi-4-mini-instruct
=====================================================
Assigns 4 labels to every complaint using Phi-4-mini few-shot prompting:

    issue_severity   low | medium | high
    issue_urgency    low | medium | high
    safety_concern   True | False
    business_impact  low | medium | high

Key design decisions:
- Phi-4-mini few-shot is used (not zero-shot DeBERTa) — empirically produces
  more consistent labels for edge cases and safety classification.
- Deterministic decoding (do_sample=False) ensures the same complaint always
  gets the same label, which is critical for training data consistency.
- Rows where labeling fails 3× are kept with null labels rather than dropped,
  so the row count stays predictable. Phase 4 validation will flag high null rates.

Checkpoints every 100 labeled rows to output/phase3_checkpoint.csv.
Resume with --resume to skip already-labeled rows (matched by ticket_id).

Usage:
    python phase3_label.py
    python phase3_label.py --resume
    python phase3_label.py --dry-run        # label 10 rows only
    python phase3_label.py --input output/phase2_deduplicated.csv
"""

import argparse
import json
import re
import time
from pathlib import Path

import pandas as pd
import torch
from tqdm import tqdm
from transformers import AutoModelForCausalLM, AutoTokenizer

# ── Phi-4 compatibility shims ──────────────────────────────────────────────────
try:
    import transformers.cache_utils as _cu
    if not hasattr(_cu, "SlidingWindowCache") and hasattr(_cu, "DynamicCache"):
        _cu.SlidingWindowCache = _cu.DynamicCache
except Exception:
    pass

try:
    import transformers.utils as _tu
    if not hasattr(_tu, "LossKwargs"):
        from typing import TypedDict

        class _LossKwargs(TypedDict, total=False):
            pass

        _tu.LossKwargs = _LossKwargs
except Exception:
    pass

try:
    from transformers import BitsAndBytesConfig
except ImportError:
    BitsAndBytesConfig = None  # type: ignore[assignment]

# ── Paths ──────────────────────────────────────────────────────────────────────
BASE_DIR         = Path(__file__).resolve().parent
OUTPUT_DIR       = BASE_DIR / "output"
DEFAULT_INPUT    = OUTPUT_DIR / "phase2_deduplicated.csv"
CHECKPOINT_PATH  = OUTPUT_DIR / "phase3_checkpoint.csv"
COMPLETE_PATH    = OUTPUT_DIR / "phase3_complete.csv"

MODEL_NAME       = "microsoft/Phi-4-mini-instruct"
LABEL_COLS       = ["issue_severity", "issue_urgency", "safety_concern", "business_impact"]
CHECKPOINT_EVERY = 100

VALID_LABELS = {
    "issue_severity":  {"low", "medium", "high"},
    "issue_urgency":   {"low", "medium", "high"},
    "business_impact": {"low", "medium", "high"},
}

# ── Few-shot examples ──────────────────────────────────────────────────────────
# Covers all 3 classes for severity/urgency/impact and both True/False for safety.
# Sourced from V7-Phase2 label.py (proven to work well with Phi-4-mini).
FEW_SHOT_EXAMPLES = [
    {
        "text":   "The bin in the kitchen hasn't been emptied in three days. It's starting to smell.",
        "labels": {"issue_severity": "low", "issue_urgency": "low",
                   "safety_concern": False, "business_impact": "low"},
    },
    {
        "text":   "Our office HVAC has been broken for two days. It's 32 degrees in here and staff are struggling to concentrate. We need this fixed today.",
        "labels": {"issue_severity": "high", "issue_urgency": "high",
                   "safety_concern": True, "business_impact": "high"},
    },
    {
        "text":   "The projector in meeting room 3B stopped working this morning. We have client presentations scheduled all week and cannot use that room.",
        "labels": {"issue_severity": "medium", "issue_urgency": "medium",
                   "safety_concern": False, "business_impact": "medium"},
    },
    {
        "text":   "There is a water leak coming through the ceiling above our server room. Water is dripping onto equipment right now.",
        "labels": {"issue_severity": "high", "issue_urgency": "high",
                   "safety_concern": True, "business_impact": "high"},
    },
    {
        "text":   "The lobby directory still shows our old company name from six months ago. Can this be updated when convenient?",
        "labels": {"issue_severity": "low", "issue_urgency": "low",
                   "safety_concern": False, "business_impact": "low"},
    },
    {
        "text":   "Our internet connection has been dropping intermittently since yesterday. It comes back after a few minutes but it is disruptive to video calls.",
        "labels": {"issue_severity": "medium", "issue_urgency": "medium",
                   "safety_concern": False, "business_impact": "medium"},
    },
    {
        "text":   "The fire alarm went off this morning with no apparent cause and staff had to evacuate. This is the third time this month.",
        "labels": {"issue_severity": "high", "issue_urgency": "high",
                   "safety_concern": True, "business_impact": "high"},
    },
    {
        "text":   "We were charged twice for our December service fee. Please review our account and issue a refund for the duplicate charge.",
        "labels": {"issue_severity": "medium", "issue_urgency": "medium",
                   "safety_concern": False, "business_impact": "medium"},
    },
    {
        "text":   "The carpet in the corridor outside our office has a small stain near the entrance. Not urgent but would appreciate it being cleaned.",
        "labels": {"issue_severity": "low", "issue_urgency": "low",
                   "safety_concern": False, "business_impact": "low"},
    },
    {
        "text":   "Our access cards stopped working this morning and none of our team can get into the office. We have lost a full day of work.",
        "labels": {"issue_severity": "high", "issue_urgency": "high",
                   "safety_concern": False, "business_impact": "high"},
    },
]


# ── Prompt builder ─────────────────────────────────────────────────────────────

def build_system_prompt() -> str:
    examples_block = ""
    for ex in FEW_SHOT_EXAMPLES:
        examples_block += f'Text: "{ex["text"]}"\n'
        examples_block += f'Labels: {json.dumps(ex["labels"])}\n\n'

    return f"""You are a labeling assistant for an office leasing and tenant support system.

Given a customer complaint, assign exactly four labels:

- issue_severity:   low | medium | high
- issue_urgency:    low | medium | high
- safety_concern:   true | false
- business_impact:  low | medium | high

DEFINITIONS:
issue_severity:
  low    = cosmetic or minor issue, core systems unaffected
  medium = one system or area affected, work can continue with effort
  high   = critical failure, entire office or core systems down

issue_urgency:
  low    = no time pressure, schedule when convenient
  medium = needs attention within a few days, growing frustration
  high   = same-day or immediate action required

safety_concern:
  true  = explicit physical danger, injury risk, fire, flooding, electrical hazard, structural
  false = operational, administrative, or service quality issue only

business_impact:
  low    = no effect on productivity, cosmetic or administrative matter
  medium = partial disruption, work continues with workarounds
  high   = operations stopped, staff cannot work, clients directly affected

EXAMPLES:
{examples_block}Respond with a single JSON object only. No explanation, no extra text."""


def build_user_prompt(text: str) -> str:
    return f'Text: "{text}"\nLabels:'


# ── Model loader ───────────────────────────────────────────────────────────────

def load_model(model_name: str) -> tuple:
    print(f"\nLoading {model_name}...")
    tokenizer = AutoTokenizer.from_pretrained(model_name, trust_remote_code=True)
    use_cuda  = torch.cuda.is_available()

    if use_cuda and BitsAndBytesConfig is not None:
        try:
            quant = BitsAndBytesConfig(
                load_in_4bit=True,
                bnb_4bit_compute_dtype=torch.float16,
                bnb_4bit_use_double_quant=True,
            )
            model = AutoModelForCausalLM.from_pretrained(
                model_name,
                quantization_config=quant,
                device_map="auto",
                trust_remote_code=True,
            )
            print("Model mode: 4-bit quantized (CUDA)")
        except Exception as e:
            print(f"[WARN] 4-bit load failed ({e}), falling back to full precision...")
            use_cuda = False  # trigger fallback below

    if not (use_cuda and BitsAndBytesConfig is not None):
        if use_cuda:
            print("[WARN] BitsAndBytesConfig unavailable — using full precision.")
        model = AutoModelForCausalLM.from_pretrained(
            model_name, trust_remote_code=True
        )
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        model.to(device)
        print(f"Model mode: full precision ({device.type.upper()})")

    model.eval()
    if torch.cuda.is_available():
        print(f"VRAM used: {torch.cuda.memory_allocated() / 1e9:.1f}GB")
    return tokenizer, model


# ── Single-ticket labeler ──────────────────────────────────────────────────────

def label_ticket(
    tokenizer,
    model,
    system_prompt: str,
    text: str,
    retries: int = 3,
) -> dict | None:
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user",   "content": build_user_prompt(text)},
    ]

    for attempt in range(retries):
        try:
            input_ids = tokenizer.apply_chat_template(
                messages,
                add_generation_prompt=True,
                return_tensors="pt",
            ).to(model.device)
            attn_mask = torch.ones_like(input_ids)

            with torch.no_grad():
                output_ids = model.generate(
                    input_ids,
                    attention_mask=attn_mask,
                    max_new_tokens=80,
                    do_sample=False,       # Deterministic — labels must be consistent
                    temperature=1.0,
                    repetition_penalty=1.1,
                    pad_token_id=tokenizer.eos_token_id,
                )

            new_tokens = output_ids[0][input_ids.shape[-1]:]
            raw        = tokenizer.decode(new_tokens, skip_special_tokens=True).strip()

            # Extract JSON from response
            m = re.search(r"\{.*?\}", raw, re.DOTALL)
            if not m:
                raise ValueError(f"No JSON found in: {raw[:100]!r}")

            parsed = json.loads(m.group(0))
            result = {}

            # Validate categorical labels
            for col in ["issue_severity", "issue_urgency", "business_impact"]:
                val = str(parsed.get(col, "")).strip().lower()
                if val not in VALID_LABELS[col]:
                    raise ValueError(f"Invalid {col}: {val!r}")
                result[col] = val

            # Validate boolean safety_concern
            sc = parsed.get("safety_concern", "")
            if isinstance(sc, bool):
                result["safety_concern"] = sc
            elif str(sc).strip().lower() in ("true", "1", "yes"):
                result["safety_concern"] = True
            elif str(sc).strip().lower() in ("false", "0", "no"):
                result["safety_concern"] = False
            else:
                raise ValueError(f"Invalid safety_concern: {sc!r}")

            return result

        except (json.JSONDecodeError, ValueError, KeyError) as e:
            if attempt < retries - 1:
                time.sleep(0.3)
            else:
                print(f"  [WARN] Label failed after {retries} attempts: {e}")
                return None

    return None


# ── Distribution summary ───────────────────────────────────────────────────────

def print_distribution(df: pd.DataFrame) -> None:
    print(f"\n{'='*55}")
    print(f"LABEL DISTRIBUTION ({len(df)} rows)")
    print(f"{'='*55}")
    for col in LABEL_COLS:
        counts = df[col].value_counts(dropna=True)
        total  = counts.sum()
        if total == 0:
            continue
        print(f"\n{col}:")
        for val, count in counts.items():
            pct  = count / total * 100
            bar  = "█" * int(pct / 3)
            flag = "  ⚠ UNDERREPRESENTED" if pct < 8 else ""
            print(f"  {str(val):<10} {count:>6}  ({pct:4.1f}%)  {bar}{flag}")

    # Safety rate summary
    total_safety = df["safety_concern"].notna().sum()
    if total_safety:
        true_pct = (df["safety_concern"].astype(str).str.lower() == "true").sum() / total_safety * 100
        flag     = "  ⚠ LOW" if true_pct < 15 else ("  ⚠ HIGH" if true_pct > 40 else "")
        print(f"\nsafety_concern=True rate: {true_pct:.1f}% (target: 15%–40%){flag}")


# ── Main ───────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="V8 Phase 3: Phi-4 Few-Shot Labeling")
    parser.add_argument("--input",   default=str(DEFAULT_INPUT),
                        help="Path to deduplicated CSV from phase 2")
    parser.add_argument("--model",   default=MODEL_NAME)
    parser.add_argument("--resume",  action="store_true",
                        help="Resume from checkpoint (skips already-labeled ticket_ids)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Label only 10 rows (quick sanity check)")
    args = parser.parse_args()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # ── Load input ────────────────────────────────────────────────────────────
    print(f"Loading: {args.input}")
    df = pd.read_csv(args.input)
    print(f"Loaded {len(df)} rows")

    # Ensure ticket_id column exists (fallback if phase2 dropped it somehow)
    if "ticket_id" not in df.columns:
        df.insert(0, "ticket_id", [f"V8-{i:05d}" for i in range(len(df))])

    if args.dry_run:
        df = df.head(10).copy()
        print(f"[DRY RUN] Labeling {len(df)} rows")

    # ── Resume: load checkpoint and find unlabeled rows ───────────────────────
    labeled_rows: list[dict]   = []
    already_labeled_ids: set   = set()

    if args.resume and CHECKPOINT_PATH.exists():
        ckpt               = pd.read_csv(CHECKPOINT_PATH)
        labeled_rows       = ckpt.to_dict("records")
        already_labeled_ids = set(ckpt["ticket_id"].astype(str))
        print(f"[RESUME] Loaded {len(labeled_rows)} from checkpoint")

    remaining = df[~df["ticket_id"].astype(str).isin(already_labeled_ids)].copy()
    print(f"Rows to label: {len(remaining)}")

    if remaining.empty:
        print("All rows already labeled. Saving final output.")
        pd.DataFrame(labeled_rows).to_csv(COMPLETE_PATH, index=False)
        return

    # ── Load model ────────────────────────────────────────────────────────────
    tokenizer, model = load_model(args.model)
    system_prompt    = build_system_prompt()

    failed = 0

    for _, row in tqdm(remaining.iterrows(), total=len(remaining), desc="Labeling"):
        text   = str(row.get("text", ""))
        labels = label_ticket(tokenizer, model, system_prompt, text)

        if labels:
            labeled_rows.append({**row.to_dict(), **labels})
        else:
            # Keep the row — null labels are flagged by Phase 4 validation
            labeled_rows.append({**row.to_dict(), **{col: None for col in LABEL_COLS}})
            failed += 1

        # Checkpoint every 100 rows
        if len(labeled_rows) % CHECKPOINT_EVERY == 0:
            pd.DataFrame(labeled_rows).to_csv(CHECKPOINT_PATH, index=False)

    # ── Final save ────────────────────────────────────────────────────────────
    result_df = pd.DataFrame(labeled_rows)
    result_df.to_csv(CHECKPOINT_PATH, index=False)
    result_df.to_csv(COMPLETE_PATH, index=False)

    print(f"\n{'='*55}")
    print(f"Phase 3 complete")
    print(f"  Labeled  : {len(labeled_rows) - failed}")
    print(f"  Failed   : {failed} (null labels, kept in dataset)")
    print(f"  Total    : {len(labeled_rows)}")
    print(f"  Saved to : {COMPLETE_PATH}")

    print_distribution(result_df)


if __name__ == "__main__":
    main()
