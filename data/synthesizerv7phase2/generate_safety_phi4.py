"""
generate_safety_phi4.py — Generate a balanced synthetic safety dataset with Phi-4-mini.
"""

import argparse
import json
import random
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
        from typing import TypedDict

        class _LossKwargs(TypedDict, total=False):
            pass

        _transformers_utils.LossKwargs = _LossKwargs
except Exception:
    pass

try:
    from transformers import BitsAndBytesConfig
except Exception:
    BitsAndBytesConfig = None

MODEL_NAME = "microsoft/Phi-4-mini-instruct"
VALID_LEVELS = {"low", "medium", "high"}
DOMAINS = [
    "office leasing and tenant support",
    "office building management and facilities",
    "commercial property and workspace rental",
    "office utilities and building services",
    "it and office technology support",
    "office parking and access control",
    "shared workspace and coworking",
]


def load_model(model_name: str):
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
    else:
        model = AutoModelForCausalLM.from_pretrained(model_name, trust_remote_code=True)
        model.to(torch.device("cuda" if use_cuda else "cpu"))
    model.eval()
    return tokenizer, model


def build_system_prompt() -> str:
    return """You generate realistic office leasing complaint tickets as JSON.

Output exactly one JSON object with keys:
- ticket_type (always "complaint")
- subject (short title)
- text (2-4 sentence customer complaint)
- domain (office operations domain)
- issue_severity (low|medium|high)
- issue_urgency (low|medium|high)
- safety_concern (true|false)
- business_impact (low|medium|high)

Rules:
- If safety_concern=true: include explicit physical risk context (e.g., electrical hazard, smoke, flood, structural risk, injury risk).
- If safety_concern=false: issue may be urgent but must not imply physical danger.
- Keep the text varied and realistic; avoid repeated phrasing.
- Respond with a single JSON object only."""


def build_user_prompt(safety_target: bool, domain: str) -> str:
    return (
        f"Generate one complaint with safety_concern={'true' if safety_target else 'false'} "
        f"in domain '{domain}'."
    )


def normalize_and_validate(record: dict, safety_target: bool) -> dict:
    out = {
        "ticket_type": "complaint",
        "subject": str(record.get("subject", "")).strip(),
        "text": str(record.get("text", "")).strip(),
        "domain": str(record.get("domain", "")).strip() or random.choice(DOMAINS),
        "issue_severity": str(record.get("issue_severity", "")).strip().lower(),
        "issue_urgency": str(record.get("issue_urgency", "")).strip().lower(),
        "business_impact": str(record.get("business_impact", "")).strip().lower(),
    }

    sc = record.get("safety_concern", safety_target)
    if isinstance(sc, bool):
        out["safety_concern"] = sc
    else:
        out["safety_concern"] = str(sc).strip().lower() in ("true", "1", "yes")

    # Enforce requested balance exactly.
    out["safety_concern"] = bool(safety_target)

    if out["issue_severity"] not in VALID_LEVELS:
        raise ValueError(f"Invalid issue_severity: {out['issue_severity']}")
    if out["issue_urgency"] not in VALID_LEVELS:
        raise ValueError(f"Invalid issue_urgency: {out['issue_urgency']}")
    if out["business_impact"] in ("none", "false", ""):
        out["business_impact"] = "low"
    if out["business_impact"] not in VALID_LEVELS:
        raise ValueError(f"Invalid business_impact: {out['business_impact']}")
    if not out["subject"] or not out["text"]:
        raise ValueError("Missing subject/text")
    return out


def generate_one(tokenizer, model, system_prompt: str, safety_target: bool, domain: str, retries: int = 4):
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": build_user_prompt(safety_target, domain)},
    ]
    for _ in range(retries):
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
                    max_new_tokens=220,
                    do_sample=True,
                    temperature=0.8,
                    top_p=0.9,
                    repetition_penalty=1.1,
                    pad_token_id=tokenizer.eos_token_id,
                )

            new_tokens = output_ids[0][input_ids.shape[-1]:]
            raw = tokenizer.decode(new_tokens, skip_special_tokens=True).strip()
            m = re.search(r"\{.*\}", raw, re.DOTALL)
            if not m:
                raise ValueError("No JSON object found")
            parsed = json.loads(m.group(0))
            return normalize_and_validate(parsed, safety_target)
        except Exception:
            time.sleep(0.25)
    return None


def main():
    parser = argparse.ArgumentParser(description="Generate balanced safety dataset with Phi-4-mini")
    parser.add_argument("--output", default="output/safety_synth_1000.csv")
    parser.add_argument("--rows", type=int, default=1000)
    parser.add_argument("--model", default=MODEL_NAME)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--checkpoint-every", type=int, default=50)
    args = parser.parse_args()

    random.seed(args.seed)
    if args.rows % 2 != 0:
        raise ValueError("--rows must be even for 50/50 true/false split")

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    tokenizer, model = load_model(args.model)
    system_prompt = build_system_prompt()

    targets = [True] * (args.rows // 2) + [False] * (args.rows // 2)
    random.shuffle(targets)

    rows = []
    failures = 0
    for i, target in enumerate(tqdm(targets, desc="Generating safety dataset"), start=1):
        rec = generate_one(tokenizer, model, system_prompt, target, random.choice(DOMAINS))
        if rec is None:
            failures += 1
            continue
        rec["source"] = "phi4_safety_synth"
        rows.append(rec)
        if i % args.checkpoint_every == 0:
            pd.DataFrame(rows).to_csv(output_path, index=False)

    df = pd.DataFrame(rows)
    if len(df) == 0:
        raise RuntimeError("No rows generated")

    # Rebalance to exact 50/50 if failures skewed the output.
    true_df = df[df["safety_concern"] == True]
    false_df = df[df["safety_concern"] == False]
    target_half = min(len(true_df), len(false_df))
    df_balanced = pd.concat([
        true_df.sample(n=target_half, random_state=args.seed),
        false_df.sample(n=target_half, random_state=args.seed),
    ], ignore_index=True).sample(frac=1.0, random_state=args.seed).reset_index(drop=True)

    df_balanced.to_csv(output_path, index=False)
    print(f"Saved: {output_path}")
    print(f"Rows generated: {len(df_balanced)}")
    print(f"Failures: {failures}")
    print(f"safety_concern=True: {int(df_balanced['safety_concern'].eq(True).sum())}")
    print(f"safety_concern=False: {int(df_balanced['safety_concern'].eq(False).sum())}")


if __name__ == "__main__":
    main()
