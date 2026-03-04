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
LABEL_COLS = ["safety_concern", "business_impact", "issue_severity", "issue_urgency"]
ANSI_ESCAPE_RE = re.compile(r"\x1B\[[0-?]*[ -/]*[@-~]")


def build_prompt(safety: str, impact: str, severity: str, urgency: str) -> str:
    return f"""You are generating synthetic tenant complaints for a property management system.

Generate one complaint with these internal labels:
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
7. Output only the complaint text, no JSON, no labels, no explanation.
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


def extract_text(generated: str) -> str | None:
    text = generated.strip()
    # If model still returns JSON occasionally, try extracting text field first.
    if text.startswith("{"):
        try:
            parsed = json.loads(text)
            candidate = str(parsed.get("text", "")).strip()
            if candidate:
                return candidate
        except Exception:
            pass
    text = ANSI_ESCAPE_RE.sub("", text)
    text = re.sub(r"\s+", " ", text).strip()
    text = text.strip("\"'")
    if not text or len(text) < 24:
        return None
    return text


def generate_one(
    tokenizer,
    model,
    safety: str,
    impact: str,
    severity: str,
    urgency: str,
    max_new_tokens: int = 120,
) -> dict | None:
    prompt = build_prompt(safety, impact, severity, urgency)
    messages = [
        {"role": "system", "content": "Return only complaint text."},
        {"role": "user", "content": prompt},
    ]
    model_inputs = tokenizer.apply_chat_template(
        messages,
        add_generation_prompt=True,
        return_tensors="pt",
        return_dict=True,
    ).to(model.device)

    with torch.no_grad():
        output = model.generate(
            **model_inputs,
            max_new_tokens=max_new_tokens,
            do_sample=True,
            temperature=0.9,
            top_p=0.9,
            repetition_penalty=1.05,
            pad_token_id=tokenizer.eos_token_id,
            eos_token_id=tokenizer.eos_token_id,
        )

    prompt_len = model_inputs["input_ids"].shape[-1]
    decoded = tokenizer.decode(output[0][prompt_len:], skip_special_tokens=True)
    text = extract_text(decoded)
    if not text:
        return None
    return {
        "text": text,
        "safety_concern": safety,
        "business_impact": impact,
        "issue_severity": severity,
        "issue_urgency": urgency,
    }


def build_combinations() -> list[tuple[str, str, str, str]]:
    safety = ["true", "false"]
    tri = ["low", "medium", "high"]
    return list(itertools.product(safety, tri, tri, tri))


def write_dataset(records: list[dict], output: Path, seed: int) -> pd.DataFrame:
    df = pd.DataFrame(records)
    if len(df) > 0:
        df = df.sample(frac=1.0, random_state=seed).reset_index(drop=True)
    df.to_csv(output, index=False)
    return df


def load_existing_records(output: Path, combinations: set[tuple[str, str, str, str]]) -> list[dict]:
    if not output.exists():
        return []
    df = pd.read_csv(output)
    if df.empty:
        return []
    required = ["text"] + LABEL_COLS
    missing = [c for c in required if c not in df.columns]
    if missing:
        print(f"[WARN] Existing output missing columns {missing}; ignoring resume file.")
        return []
    records = []
    for _, row in df.iterrows():
        rec = {
            "text": str(row["text"]).strip(),
            "safety_concern": str(row["safety_concern"]).strip().lower(),
            "business_impact": str(row["business_impact"]).strip().lower(),
            "issue_severity": str(row["issue_severity"]).strip().lower(),
            "issue_urgency": str(row["issue_urgency"]).strip().lower(),
        }
        combo = (
            rec["safety_concern"],
            rec["business_impact"],
            rec["issue_severity"],
            rec["issue_urgency"],
        )
        if rec["text"] and combo in combinations:
            records.append(rec)
    print(f"[INFO] Resume mode loaded {len(records)} existing rows from {output}")
    return records


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
    parser.add_argument("--max-attempts-per-row", type=int, default=3)
    parser.add_argument("--max-new-tokens", type=int, default=120)
    parser.add_argument("--save-every", type=int, default=25, help="Persist intermediate progress every N accepted rows")
    parser.add_argument("--resume", action="store_true", help="Resume from existing --output CSV if present")
    parser.add_argument("--max-combo-attempts", type=int, default=5000, help="Hard cap attempts per label combination")
    parser.add_argument("--dry-run", action="store_true", help="Generate 54 rows, one per combination")
    args = parser.parse_args()

    torch.manual_seed(args.seed)

    output = Path(args.output)
    report = Path(args.report)
    output.parent.mkdir(parents=True, exist_ok=True)
    report.parent.mkdir(parents=True, exist_ok=True)

    combinations = build_combinations()
    combo_set = set(combinations)
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

    records = load_existing_records(output, combo_set) if args.resume else []
    seen_text = {r["text"].lower() for r in records}
    current_counts = {}
    for combo in combinations:
        current_counts[combo] = 0
    for rec in records:
        combo = (
            rec["safety_concern"],
            rec["business_impact"],
            rec["issue_severity"],
            rec["issue_urgency"],
        )
        if combo in current_counts:
            current_counts[combo] += 1

    done_rows = min(sum(min(current_counts[c], targets[c]) for c in combinations), rows_target)
    pbar = tqdm(total=rows_target, desc="Generating", leave=False, initial=done_rows)
    since_last_save = 0

    for combo in combinations:
        safety, impact, severity, urgency = combo
        need = targets[combo]
        created = current_counts.get(combo, 0)
        combo_attempts = 0

        while created < need:
            combo_attempts += 1
            if combo_attempts > max(args.max_combo_attempts, 1):
                raise RuntimeError(
                    f"Exceeded max attempts for combo={combo}. "
                    f"Created={created}, needed={need}. "
                    f"Try increasing --max-combo-attempts or reducing --rows."
                )
            generated = None
            for _ in range(max(args.max_attempts_per_row, 1)):
                generated = generate_one(
                    tokenizer,
                    model,
                    safety,
                    impact,
                    severity,
                    urgency,
                    max_new_tokens=max(args.max_new_tokens, 32),
                )
                if generated is not None:
                    break
                time.sleep(0.05)

            if generated is None:
                continue
            text_key = generated["text"].lower()
            if text_key in seen_text:
                continue

            records.append(generated)
            seen_text.add(text_key)
            created += 1
            pbar.update(1)
            since_last_save += 1

            if args.save_every > 0 and since_last_save >= args.save_every:
                df_partial = write_dataset(records, output, args.seed)
                write_balance_report(df_partial, report)
                since_last_save = 0

    pbar.close()

    df = write_dataset(records, output, args.seed)
    write_balance_report(df, report)

    print(f"Saved dataset: {output}")
    print(f"Saved report : {report}")
    print(f"Rows         : {len(df)}")


if __name__ == "__main__":
    main()
