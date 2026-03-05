"""
generate_balanced_phi4.py — Generate balanced labeled complaints with Phi-4-mini.

Balances targets across:
    - issue_severity: low/medium/high
    - issue_urgency: low/medium/high
    - business_impact: low/medium/high
    - safety_concern: true/false
"""

import argparse
import json
import random
import re
import time
from collections import defaultdict
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
LEVELS = ["low", "medium", "high"]
DOMAINS = [
    "office leasing and tenant support",
    "office building management and facilities",
    "commercial property and workspace rental",
    "office utilities and building services",
    "it and office technology support",
    "office parking and access control",
    "shared workspace and coworking",
]

HAZARD_TERMS = {
    "fire", "smoke", "flood", "flooding", "electrical", "electric shock", "sparking",
    "gas leak", "ceiling collapse", "fall risk", "slip hazard", "injury", "unsafe",
    "burn", "exposed wire", "short circuit", "overheating",
}
URGENT_TERMS = {
    "immediately", "urgent", "asap", "right now", "same day", "today", "now",
    "cannot wait", "critical deadline",
}
CRITICAL_TERMS = {
    "completely down", "entire office", "critical failure", "system-wide", "major outage",
    "unusable", "stopped working", "cannot operate", "operations halted",
}
HIGH_IMPACT_TERMS = {
    "clients affected", "lost revenue", "operations halted", "staff cannot work",
    "business disruption", "sla breach", "escalation", "blocked productivity",
}
LOW_IMPACT_TERMS = {
    "minor inconvenience", "cosmetic", "non-urgent", "when convenient", "small issue",
}


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
    return """You generate realistic office complaint tickets as JSON.

Output exactly one JSON object with keys:
- ticket_type (always "complaint")
- subject (short title)
- text (2-4 sentence customer complaint)
- domain (office operations domain)
- issue_severity (low|medium|high)
- issue_urgency (low|medium|high)
- safety_concern (true|false)
- business_impact (low|medium|high)

Follow the requested target labels exactly.
If safety_concern=true, include explicit physical hazard context.
If safety_concern=false, avoid physical hazard language.
The generated text must clearly reflect the requested labels, not generic wording.
Respond with JSON only."""


def build_user_prompt(target: dict, domain: str) -> str:
    safety_true = target["safety_concern"] is True
    safety_instruction = (
        "Include explicit physical hazard cues (e.g., electrical risk, smoke, leak, injury risk)."
        if safety_true else
        "Do NOT include any physical hazard cues (no fire/smoke/electrical/flood/injury risk language)."
    )
    severity_instruction = {
        "high": "Show critical/system-wide failure with major operational disruption.",
        "medium": "Show clear disruption but with workarounds still possible.",
        "low": "Show minor localized issue with limited disruption.",
    }[target["issue_severity"]]
    urgency_instruction = {
        "high": "Use immediate time pressure language (same-day/ASAP/right now).",
        "medium": "Needs attention soon, but not immediate emergency language.",
        "low": "No immediate time pressure; should be schedulable.",
    }[target["issue_urgency"]]
    impact_instruction = {
        "high": "State strong business impact (clients/staff blocked/revenue or operations impact).",
        "medium": "State moderate impact (partial productivity loss).",
        "low": "State minimal business impact; mostly inconvenience.",
    }[target["business_impact"]]
    return (
        "Generate one complaint with exactly these target labels:\n"
        f"- issue_severity: {target['issue_severity']}\n"
        f"- issue_urgency: {target['issue_urgency']}\n"
        f"- business_impact: {target['business_impact']}\n"
        f"- safety_concern: {'true' if target['safety_concern'] else 'false'}\n"
        f"Label constraints:\n"
        f"- {severity_instruction}\n"
        f"- {urgency_instruction}\n"
        f"- {impact_instruction}\n"
        f"- {safety_instruction}\n"
        f"Domain: {domain}\n"
        "Return JSON only."
    )


def build_targets(rows: int, seed: int) -> list[dict]:
    if rows % 2 != 0:
        raise ValueError("--rows must be even to keep safety true/false balanced")

    combos = []
    for sev in LEVELS:
        for urg in LEVELS:
            for biz in LEVELS:
                for saf in (False, True):
                    combos.append({
                        "issue_severity": sev,
                        "issue_urgency": urg,
                        "business_impact": biz,
                        "safety_concern": saf,
                    })

    base = rows // len(combos)
    rem = rows % len(combos)
    targets = combos * base

    # Keep safety balance for remainder by adding equal false/true combos.
    random.seed(seed)
    false_combos = [c for c in combos if c["safety_concern"] is False]
    true_combos = [c for c in combos if c["safety_concern"] is True]
    random.shuffle(false_combos)
    random.shuffle(true_combos)

    take_false = rem // 2
    take_true = rem - take_false
    targets.extend(false_combos[:take_false])
    targets.extend(true_combos[:take_true])
    random.shuffle(targets)
    return targets


def normalize_record(parsed: dict, target: dict, domain: str) -> dict:
    subject = str(parsed.get("subject", "")).strip()
    text = str(parsed.get("text", "")).strip()
    if not subject or not text:
        raise ValueError("Missing subject/text")

    return {
        "ticket_type": "complaint",
        "subject": subject,
        "text": text,
        "domain": str(parsed.get("domain", "")).strip().lower() or domain,
        # Enforce exact balanced labels from target.
        "issue_severity": target["issue_severity"],
        "issue_urgency": target["issue_urgency"],
        "business_impact": target["business_impact"],
        "safety_concern": target["safety_concern"],
        "source": "phi4_balanced_synth",
    }


def _text_signature(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]", " ", text.lower())).strip()


def _has_any(text: str, terms: set[str]) -> bool:
    t = text.lower()
    return any(term in t for term in terms)


def quality_gate(record: dict, target: dict, seen_signatures: set[str]) -> tuple[bool, str]:
    text = record["text"]
    t = text.lower()
    sig = _text_signature(text)

    if len(sig) < 80:
        return False, "too_short"
    if sig in seen_signatures:
        return False, "duplicate_text"

    has_hazard = _has_any(t, HAZARD_TERMS)
    has_urgent = _has_any(t, URGENT_TERMS)
    has_critical = _has_any(t, CRITICAL_TERMS)
    has_high_impact = _has_any(t, HIGH_IMPACT_TERMS)
    has_low_impact = _has_any(t, LOW_IMPACT_TERMS)

    if target["safety_concern"] and not has_hazard:
        return False, "safety_true_missing_hazard_cue"
    if (not target["safety_concern"]) and has_hazard:
        return False, "safety_false_has_hazard_cue"

    if target["issue_urgency"] == "high" and not has_urgent:
        return False, "urgency_high_missing_time_pressure"
    if target["issue_urgency"] == "low" and has_urgent:
        return False, "urgency_low_has_time_pressure"

    if target["issue_severity"] == "high" and not has_critical:
        return False, "severity_high_missing_critical_cue"
    if target["issue_severity"] == "low" and has_critical:
        return False, "severity_low_has_critical_cue"

    if target["business_impact"] == "high" and not has_high_impact:
        return False, "impact_high_missing_business_cue"
    if target["business_impact"] == "low" and has_high_impact and not has_low_impact:
        return False, "impact_low_has_high_impact_cue"

    return True, "ok"


def generate_one(
    tokenizer,
    model,
    system_prompt: str,
    target: dict,
    domain: str,
    seen_signatures: set[str],
    retries: int = 10,
) -> tuple[dict | None, str]:
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": build_user_prompt(target, domain)},
    ]
    last_reason = "generation_failed"
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
                    max_new_tokens=240,
                    do_sample=True,
                    temperature=0.85,
                    top_p=0.92,
                    repetition_penalty=1.1,
                    pad_token_id=tokenizer.eos_token_id,
                )

            new_tokens = output_ids[0][input_ids.shape[-1]:]
            raw = tokenizer.decode(new_tokens, skip_special_tokens=True).strip()
            m = re.search(r"\{.*\}", raw, re.DOTALL)
            if not m:
                raise ValueError("No JSON object found")
            parsed = json.loads(m.group(0))
            record = normalize_record(parsed, target, domain)
            ok, reason = quality_gate(record, target, seen_signatures)
            if not ok:
                last_reason = reason
                continue
            seen_signatures.add(_text_signature(record["text"]))
            return record, "ok"
        except Exception:
            last_reason = "parse_or_model_error"
            time.sleep(0.25)
    return None, last_reason


def print_distribution(df: pd.DataFrame):
    print("\nDistribution check:")
    for col in ["issue_severity", "issue_urgency", "business_impact", "safety_concern"]:
        counts = df[col].value_counts().to_dict()
        print(f"- {col}: {counts}")


def main():
    parser = argparse.ArgumentParser(description="Generate balanced labeled complaints with Phi-4-mini")
    parser.add_argument("--rows", type=int, default=2000)
    parser.add_argument("--output", default="output/balanced_synth_2000.csv")
    parser.add_argument("--model", default=MODEL_NAME)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--checkpoint-every", type=int, default=50)
    args = parser.parse_args()

    random.seed(args.seed)
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    targets = build_targets(args.rows, args.seed)
    tokenizer, model = load_model(args.model)
    system_prompt = build_system_prompt()

    rows = []
    failures = 0
    reject_reasons = defaultdict(int)
    seen_signatures: set[str] = set()
    for i, target in enumerate(tqdm(targets, desc="Generating balanced dataset"), start=1):
        domain = random.choice(DOMAINS)
        rec, reason = generate_one(
            tokenizer, model, system_prompt, target, domain, seen_signatures
        )
        if rec is None:
            failures += 1
            reject_reasons[reason] += 1
            continue
        rows.append(rec)
        if i % args.checkpoint_every == 0:
            pd.DataFrame(rows).to_csv(output_path, index=False)

    if not rows:
        raise RuntimeError("No rows generated")

    df = pd.DataFrame(rows)
    # If failures happened, trim to the largest even count and rebalance safety exactly.
    if len(df) % 2 != 0:
        df = df.iloc[:-1].copy()

    true_df = df[df["safety_concern"] == True]
    false_df = df[df["safety_concern"] == False]
    k = min(len(true_df), len(false_df))
    df = pd.concat([
        true_df.sample(n=k, random_state=args.seed),
        false_df.sample(n=k, random_state=args.seed),
    ], ignore_index=True).sample(frac=1.0, random_state=args.seed).reset_index(drop=True)

    df.to_csv(output_path, index=False)
    print(f"Saved: {output_path}")
    print(f"Rows generated: {len(df)}")
    print(f"Failures: {failures}")
    if reject_reasons:
        print("Top rejection reasons:")
        for reason, count in sorted(reject_reasons.items(), key=lambda x: x[1], reverse=True)[:10]:
            print(f"- {reason}: {count}")
    print_distribution(df)


if __name__ == "__main__":
    main()
