"""
label.py — Label 2000 tickets using Phi-4-mini-instruct (few-shot)
===================================================================
Reads unlabeled.csv, uses Phi-4-mini to assign:
    issue_severity  (low / medium / high)   — complaints only
    issue_urgency   (low / medium / high)   — complaints only
    safety_concern  (True / False)          — complaints only
    business_impact (low / medium / high)   — complaints only

Inquiries pass through with null labels.

Usage:
    python label.py --input unlabeled.csv --output labeled.csv
    python label.py --input unlabeled.csv --output labeled.csv --dry-run
    python label.py --input unlabeled.csv --output labeled.csv --max-complaints 200
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

# Compatibility shims for Phi-4 remote code across nearby transformers versions.
try:
    import transformers.cache_utils as _cache_utils
    if not hasattr(_cache_utils, "SlidingWindowCache") and hasattr(_cache_utils, "DynamicCache"):
        _cache_utils.SlidingWindowCache = _cache_utils.DynamicCache
except Exception:
    pass

try:
    import transformers.utils as _transformers_utils
    if not hasattr(_transformers_utils, "LossKwargs"):
        from typing import Dict, Any
        _transformers_utils.LossKwargs = Dict[str, Any]
except Exception:
    pass

try:
    from transformers import BitsAndBytesConfig
except Exception:
    BitsAndBytesConfig = None

# ─────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────

MODEL_NAME  = "microsoft/Phi-4-mini-instruct"
LABEL_COLS  = ["issue_severity", "issue_urgency", "safety_concern", "business_impact"]
VALID_LABELS = {
    "issue_severity":  {"low", "medium", "high"},
    "issue_urgency":   {"low", "medium", "high"},
    "safety_concern":  {True, False},
    "business_impact": {"low", "medium", "high"},
}

# ─────────────────────────────────────────────
# FEW-SHOT EXAMPLES
# Covers all classes across all labels
# ─────────────────────────────────────────────

FEW_SHOT_EXAMPLES = [
    {
        "text": "The bin in the kitchen hasn't been emptied in three days. It's starting to smell.",
        "labels": {"issue_severity": "low", "issue_urgency": "low", "safety_concern": False, "business_impact": "low"}
    },
    {
        "text": "Our office HVAC has been broken for two days. It's 32 degrees in here and staff are struggling to concentrate. We need this fixed today.",
        "labels": {"issue_severity": "high", "issue_urgency": "high", "safety_concern": True, "business_impact": "high"}
    },
    {
        "text": "The projector in meeting room 3B stopped working this morning. We have client presentations scheduled all week and cannot use that room.",
        "labels": {"issue_severity": "medium", "issue_urgency": "medium", "safety_concern": False, "business_impact": "medium"}
    },
    {
        "text": "There is a water leak coming through the ceiling above our server room. Water is dripping onto equipment right now.",
        "labels": {"issue_severity": "high", "issue_urgency": "high", "safety_concern": True, "business_impact": "high"}
    },
    {
        "text": "The lobby directory still shows our old company name from six months ago. Can this be updated when convenient?",
        "labels": {"issue_severity": "low", "issue_urgency": "low", "safety_concern": False, "business_impact": "low"}
    },
    {
        "text": "Our internet connection has been dropping intermittently since yesterday. It comes back after a few minutes but it is disruptive to video calls.",
        "labels": {"issue_severity": "medium", "issue_urgency": "medium", "safety_concern": False, "business_impact": "medium"}
    },
    {
        "text": "The fire alarm went off this morning with no apparent cause and staff had to evacuate. This is the third time this month.",
        "labels": {"issue_severity": "high", "issue_urgency": "high", "safety_concern": True, "business_impact": "high"}
    },
    {
        "text": "We were charged twice for our December service fee. Please review our account and issue a refund for the duplicate charge.",
        "labels": {"issue_severity": "medium", "issue_urgency": "medium", "safety_concern": False, "business_impact": "medium"}
    },
    {
        "text": "The carpet in the corridor outside our office has a small stain near the entrance. Not urgent but would appreciate it being cleaned.",
        "labels": {"issue_severity": "low", "issue_urgency": "low", "safety_concern": False, "business_impact": "low"}
    },
    {
        "text": "Our access cards stopped working this morning and none of our team can get into the office. We have lost a full day of work.",
        "labels": {"issue_severity": "high", "issue_urgency": "high", "safety_concern": False, "business_impact": "high"}
    },
]


# ─────────────────────────────────────────────
# PROMPT BUILDER
# ─────────────────────────────────────────────

def build_system_prompt() -> str:
    examples_block = ""
    for ex in FEW_SHOT_EXAMPLES:
        examples_block += f'Text: "{ex["text"]}"\n'
        examples_block += f'Labels: {json.dumps(ex["labels"])}\n\n'

    return f"""You are a labeling assistant for an office leasing and tenant support system.

Given a customer complaint, assign exactly these four labels:

- issue_severity:  low | medium | high
- issue_urgency:   low | medium | high  
- safety_concern:  true | false
- business_impact: low | medium | high

DEFINITIONS:
issue_severity:
  low    = cosmetic or minor issue, core systems unaffected
  medium = one system or area affected, work can continue
  high   = critical failure, entire office or core systems down

issue_urgency:
  low    = no time pressure, schedule when convenient
  medium = needs attention within a few days
  high   = same-day or immediate action required

safety_concern:
  true  = explicit physical danger, injury risk, fire, flooding, electrical, structural
  false = operational, administrative, or service quality issue only

business_impact:
  low    = no effect on productivity, cosmetic or admin matter
  medium = partial disruption, work continues with workarounds
  high   = operations stopped, staff cannot work, clients affected

EXAMPLES:
{examples_block}
Respond with a single JSON object only. No explanation, no extra text."""


def build_user_prompt(text: str) -> str:
    return f'Text: "{text}"\nLabels:'


# ─────────────────────────────────────────────
# MODEL
# ─────────────────────────────────────────────

def load_model(model_name: str):
    print(f"\nLoading {model_name}...")

    tokenizer = AutoTokenizer.from_pretrained(model_name, trust_remote_code=True)
    use_cuda = torch.cuda.is_available()
    use_4bit = use_cuda and BitsAndBytesConfig is not None

    if use_4bit:
        quant_config = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_compute_dtype=torch.float16,
            bnb_4bit_use_double_quant=True,
        )
        model = AutoModelForCausalLM.from_pretrained(
            model_name,
            quantization_config=quant_config,
            device_map="auto",
            trust_remote_code=True,
        )
        print("Model mode: 4-bit quantized (CUDA)")
    else:
        if use_cuda and BitsAndBytesConfig is None:
            print("[WARN] BitsAndBytesConfig unavailable. Falling back to full precision.")
        if not use_cuda:
            print("[WARN] CUDA not available. Falling back to CPU/full precision.")
        model = AutoModelForCausalLM.from_pretrained(
            model_name,
            trust_remote_code=True,
        )
        target_device = torch.device("cuda" if use_cuda else "cpu")
        model.to(target_device)
        print(f"Model mode: full precision ({target_device.type.upper()})")

    model.eval()
    if torch.cuda.is_available():
        print(f"Model loaded - VRAM used: {torch.cuda.memory_allocated() / 1e9:.1f}GB")
    else:
        print("Model loaded - CUDA memory reporting skipped (CPU mode)")
    return tokenizer, model


# ─────────────────────────────────────────────
# LABEL A SINGLE TICKET
# ─────────────────────────────────────────────

def label_ticket(tokenizer, model, system_prompt: str, text: str, retries: int = 3) -> dict | None:
    user_prompt = build_user_prompt(text)
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user",   "content": user_prompt},
    ]

    for attempt in range(retries):
        try:
            input_ids = tokenizer.apply_chat_template(
                messages,
                add_generation_prompt=True,
                return_tensors="pt",
            ).to(model.device)
            attention_mask = torch.ones_like(input_ids)

            with torch.no_grad():
                output_ids = model.generate(
                    input_ids,
                    attention_mask=attention_mask,
                    max_new_tokens=80,
                    do_sample=False,        # Deterministic — labeling not generation
                    temperature=1.0,
                    repetition_penalty=1.1,
                    pad_token_id=tokenizer.eos_token_id,
                )

            new_tokens = output_ids[0][input_ids.shape[-1]:]
            raw = tokenizer.decode(new_tokens, skip_special_tokens=True).strip()

            # Extract JSON
            json_match = re.search(r'\{.*?\}', raw, re.DOTALL)
            if not json_match:
                raise ValueError(f"No JSON found in: {raw[:100]}")

            parsed = json.loads(json_match.group(0))

            # Normalise and validate
            result = {}

            for col in ["issue_severity", "issue_urgency", "business_impact"]:
                val = str(parsed.get(col, "")).strip().lower()
                if val not in VALID_LABELS[col]:
                    raise ValueError(f"Invalid {col}: '{val}'")
                result[col] = val

            sc = parsed.get("safety_concern", "")
            if isinstance(sc, bool):
                result["safety_concern"] = sc
            elif str(sc).strip().lower() in ("true", "1", "yes"):
                result["safety_concern"] = True
            elif str(sc).strip().lower() in ("false", "0", "no"):
                result["safety_concern"] = False
            else:
                raise ValueError(f"Invalid safety_concern: '{sc}'")

            return result

        except (json.JSONDecodeError, ValueError, KeyError) as e:
            if attempt < retries - 1:
                time.sleep(0.3)
            else:
                print(f"  [WARN] Failed after {retries} attempts: {e}")
                return None


# ─────────────────────────────────────────────
# DISTRIBUTION AUDIT
# ─────────────────────────────────────────────

def print_distribution(df: pd.DataFrame):
    complaints = df[df["ticket_type"] == "complaint"]
    print(f"\n{'='*50}")
    print(f"LABEL DISTRIBUTION ({len(complaints)} complaints)")
    print(f"{'='*50}")
    for col in LABEL_COLS:
        counts = complaints[col].value_counts()
        total  = counts.sum()
        print(f"\n{col}:")
        for val, count in counts.items():
            bar  = "█" * int((count / total) * 30)
            pct  = count / total * 100
            flag = "  ⚠️  UNDERREPRESENTED" if pct < 10 else ""
            print(f"  {str(val):<10} {count:>5}  ({pct:4.1f}%)  {bar}{flag}")


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Label tickets using Phi-4-mini few-shot")
    parser.add_argument("--input",   default="unlabeled.csv",  help="Path to unlabeled CSV")
    parser.add_argument("--output",  default="labeled.csv",    help="Path to save labeled CSV")
    parser.add_argument("--model",   default=MODEL_NAME)
    parser.add_argument("--dry-run", action="store_true",      help="Run on first 10 complaints only")
    parser.add_argument("--max-complaints", type=int, default=None,
                        help="Limit number of complaint rows to label (cost control)")
    args = parser.parse_args()

    # ── Load ──
    print(f"Loading: {args.input}")
    df = pd.read_csv(args.input)
    print(f"Loaded {len(df)} rows")

    if args.dry_run:
        idx = df[df["ticket_type"] == "complaint"].head(10).index
        df  = df.loc[idx].copy().reset_index(drop=True)
        print(f"[DRY RUN] Processing {len(df)} rows")

    # ── Setup ──
    complaint_mask = df["ticket_type"] == "complaint"
    inquiry_df     = df[~complaint_mask].copy()
    complaint_df   = df[complaint_mask].copy()

    if args.max_complaints is not None:
        complaint_df = complaint_df.head(args.max_complaints).copy()
        print(f"[SAFETY] Capped complaints to {len(complaint_df)} rows (--max-complaints)")

    for col in LABEL_COLS:
        inquiry_df[col] = None

    # ── Load model ──
    tokenizer, model = load_model(args.model)
    system_prompt    = build_system_prompt()

    # ── Label ──
    labeled_rows = []
    failed       = 0
    output_path  = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    for _, row in tqdm(complaint_df.iterrows(), total=len(complaint_df), desc="Labeling"):
        labels = label_ticket(tokenizer, model, system_prompt, row["text"])

        if labels:
            labeled_rows.append({**row.to_dict(), **labels})
        else:
            # Keep row with null labels rather than dropping it
            labeled_rows.append({**row.to_dict(), **{col: None for col in LABEL_COLS}})
            failed += 1

        # Checkpoint every 100 rows
        if len(labeled_rows) % 100 == 0:
            pd.DataFrame(labeled_rows).to_csv(output_path, index=False)

    # ── Combine and save ──
    labeled_df = pd.DataFrame(labeled_rows)
    final_df   = pd.concat([labeled_df, inquiry_df], ignore_index=True)

    col_order = ["ticket_type", "subject", "text", "domain"] + LABEL_COLS
    final_df  = final_df[[c for c in col_order if c in final_df.columns]]
    final_df.to_csv(output_path, index=False)

    print(f"\n{'='*50}")
    print(f"Labeling complete")
    print(f"  Labeled  : {len(labeled_rows) - failed}")
    print(f"  Failed   : {failed}")
    print(f"  Saved to : {output_path}")

    print_distribution(final_df)


if __name__ == "__main__":
    main()
