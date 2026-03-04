"""
Generate a balanced synthetic complaint dataset using Phi-4-mini-instruct.

Outputs CSV columns:
- text
- safety_concern
- business_impact
- issue_severity
- issue_urgency
"""

import argparse
import itertools
import json
import math
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
VALID_SAFETY = {"true", "false"}
VALID_TRI = {"low", "medium", "high"}


def build_prompt(safety: str, impact: str, severity: str, urgency: str) -> str:
    return f"""You are generating synthetic tenant complaints for a property management system.

Generate a complaint with EXACTLY these labels:
  - safety_concern: {safety}
  - business_impact: {impact}
  - issue_severity: {severity}
  - issue_urgency: {urgency}

Rules:
1. Write 2-4 sentences as a real tenant would write it, casual tone
2. Do not make labels obvious from language
3. Prefer borderline and ambiguous complaints
4. safety_concern=false can still mention damage/discomfort
5. high business_impact does not require dramatic urgent words
6. Vary vocabulary and complaint type
7. Return JSON only:
{{"text":"...","safety_concern":"...","business_impact":"...","issue_severity":"...","issue_urgency":"..."}}
"""


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
        target_device = torch.device("cuda" if use_cuda else "cpu")
        model.to(target_device)

    model.eval()
    return tokenizer, model


def extract_json(text: str) -> dict | None:
    text = text.strip()
    try:
        return json.loads(text)
    except Exception:
        pass

    match = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if not match:
        return None

    try:
        return json.loads(match.group(0))
    except Exception:
        return None


def normalise_label(value: str) -> str:
    return str(value).strip().lower()


def validate_row(row: dict, safety: str, impact: str, severity: str, urgency: str) -> dict | None:
    text = str(row.get("text", "")).strip()
    if not text:
        return None

    row_safety = normalise_label(row.get("safety_concern", ""))
    row_impact = normalise_label(row.get("business_impact", ""))
    row_severity = normalise_label(row.get("issue_severity", ""))
    row_urgency = normalise_label(row.get("issue_urgency", ""))

    if row_safety not in VALID_SAFETY:
        return None
    if row_impact not in VALID_TRI or row_severity not in VALID_TRI or row_urgency not in VALID_TRI:
        return None

    # Force exact requested labels per combination-first strategy.
    if row_safety != safety or row_impact != impact or row_severity != severity or row_urgency != urgency:
        return None

    return {
        "text": text,
        "safety_concern": row_safety,
        "business_impact": row_impact,
        "issue_severity": row_severity,
        "issue_urgency": row_urgency,
    }


def generate_one(tokenizer, model, safety: str, impact: str, severity: str, urgency: str, max_new_tokens: int = 220) -> dict | None:
    prompt = build_prompt(safety, impact, severity, urgency)
    messages = [
        {"role": "system", "content": "Return only valid JSON."},
        {"role": "user", "content": prompt},
    ]
    input_ids = tokenizer.apply_chat_template(
        messages,
        add_generation_prompt=True,
        return_tensors="pt",
    )
    input_ids = input_ids.to(model.device)

    with torch.no_grad():
        output = model.generate(
            input_ids,
            max_new_tokens=max_new_tokens,
            do_sample=True,
            temperature=0.8,
            top_p=0.95,
            repetition_penalty=1.05,
        )

    decoded = tokenizer.decode(output[0][input_ids.shape[-1]:], skip_special_tokens=True)
    parsed = extract_json(decoded)
    if not parsed:
        return None
    return validate_row(parsed, safety, impact, severity, urgency)


def build_combinations() -> list[tuple[str, str, str, str]]:
    safety = ["true", "false"]
    tri = ["low", "medium", "high"]
    return list(itertools.product(safety, tri, tri, tri))


def write_balance_report(df: pd.DataFrame, out_path: Path) -> None:
    report = {
        "rows": len(df),
        "safety_concern": df["safety_concern"].value_counts().to_dict(),
        "business_impact": df["business_impact"].value_counts().to_dict(),
        "issue_severity": df["issue_severity"].value_counts().to_dict(),
        "issue_urgency": df["issue_urgency"].value_counts().to_dict(),
    }
    out_path.write_text(json.dumps(report, indent=2))


def main():
    parser = argparse.ArgumentParser(description="Generate balanced feature-engineering training data")
    parser.add_argument("--rows", type=int, default=2500)
    parser.add_argument("--output", default="Input/complaints_2500.csv")
    parser.add_argument("--report", default="output/balance_report.json")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--max-attempts-per-row", type=int, default=6)
    parser.add_argument("--dry-run", action="store_true", help="Generate 54 rows, one per combination")
    args = parser.parse_args()

    torch.manual_seed(args.seed)

    output = Path(args.output)
    report = Path(args.report)
    output.parent.mkdir(parents=True, exist_ok=True)
    report.parent.mkdir(parents=True, exist_ok=True)

    combinations = build_combinations()
    if args.dry_run:
        rows_target = len(combinations)
    else:
        rows_target = args.rows

    per_combo = rows_target // len(combinations)
    remainder = rows_target % len(combinations)

    targets = {}
    for idx, combo in enumerate(combinations):
        targets[combo] = per_combo + (1 if idx < remainder else 0)

    tokenizer, model = load_model(MODEL_NAME)

    records = []
    pbar = tqdm(total=rows_target, desc="Generating", leave=False)

    for combo in combinations:
        safety, impact, severity, urgency = combo
        need = targets[combo]
        created = 0

        while created < need:
            generated = None
            for _ in range(args.max_attempts_per_row):
                generated = generate_one(tokenizer, model, safety, impact, severity, urgency)
                if generated is not None:
                    break
                time.sleep(0.1)

            if generated is None:
                continue

            records.append(generated)
            created += 1
            pbar.update(1)

    pbar.close()

    df = pd.DataFrame(records)
    df = df.sample(frac=1.0, random_state=args.seed).reset_index(drop=True)
    df.to_csv(output, index=False)
    write_balance_report(df, report)

    print(f"Saved dataset: {output}")
    print(f"Saved report : {report}")
    print(f"Rows         : {len(df)}")


if __name__ == "__main__":
    main()
