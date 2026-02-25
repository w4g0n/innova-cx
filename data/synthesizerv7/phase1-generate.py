"""
Phase 1 — Synthetic Ticket Generation using Phi-4
==================================================
Generates 2,500 support tickets (2,000 complaints + 500 inquiries)
across multiple domains with leasing/tenant support as the primary domain.

Requirements:
    pip install transformers torch accelerate pandas tqdm

Usage:
    python phase1_generate.py --dataset dataset.csv --output output/unlabeled.csv

    # Dry run (generates 10 tickets to test prompts/output)
    python phase1_generate.py --dataset dataset.csv --output output/unlabeled.csv --dry-run
"""

import argparse
import json
import random
import re
import time
import warnings
from pathlib import Path
from typing import Any

import pandas as pd
import torch
from tqdm import tqdm
from transformers import AutoModelForCausalLM, AutoTokenizer

warnings.filterwarnings("ignore")

# ─────────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────────

TARGET_COMPLAINTS = 2000
TARGET_INQUIRIES = 500

# Domain distribution (must sum to 1.0)
DOMAIN_DISTRIBUTION = {
    "office leasing and tenant support":              0.18,
    "office building management and facilities":      0.10,
    "commercial property and workspace rental":       0.08,
    "office utilities and building services":         0.08,
    "IT and office technology support":               0.07,
    "office parking and access control":              0.06,
    "shared workspace and coworking":                 0.06,
    "office security and visitor management":         0.06,
    "reception and front desk services":              0.05,
    "office cleaning and janitorial services":        0.05,
    "conference room and meeting space management":   0.05,
    "office fit-out and renovation":                  0.04,
    "business rates and property tax disputes":       0.04,
    "mail and courier services":                      0.04,
    "office health and safety compliance":            0.04,
}

# Writing style variations — sampled randomly per ticket
STYLES = [
    "very frustrated and emotional",
    "formal and professional",
    "casual and conversational",
    "brief and to the point",
    "detailed and thorough",
    "polite but firm",
    "confused and asking for help",
    "angry and demanding",
    "disappointed but calm",
    "urgent and stressed",
    "sarcastic",
    "apologetic but persistent",
]

# Office leasing-specific issue types — sampled to encourage coverage
LEASING_ISSUES = [
    "office rent payment dispute",
    "office lease renewal or termination",
    "maintenance request that was ignored or delayed",
    "security deposit or retainer deduction",
    "noise complaint from neighboring tenant or floor",
    "unsafe office conditions such as broken HVAC, electrical issues, or structural damage",
    "eviction or lease termination notice",
    "landlord or building management accessing office without notice",
    "utility or service charge billing dispute",
    "office move-in or move-out process issue",
    "pest infestation in office space",
    "parking, loading bay, or common area dispute",
    "lease terms or square footage misrepresentation",
    "delayed repairs affecting office operations",
    "rent or service charge increase dispute",
    "elevator or building access system failure",
    "shared facilities such as bathrooms or kitchens not being maintained",
    "signage or branding rights dispute",
]

BASE_DIR = Path(__file__).resolve().parent
GENERATOR_MODEL_DIR = BASE_DIR / "models" / "generator" / "phi-4"
REMOTE_MODEL_NAME = "microsoft/phi-4"
MODEL_NAME = str(GENERATOR_MODEL_DIR) if GENERATOR_MODEL_DIR.exists() else REMOTE_MODEL_NAME
PRIMARY_DOMAIN = "office leasing and tenant support"
LENGTH_HINTS = (
    "Write 1-2 sentences only.",
    "Write 2-4 sentences.",
    "Write a short paragraph (4-6 sentences).",
)
PHASE2_LABEL_COLUMNS = (
    "issue_severity",
    "issue_urgency",
    "safety_concern",
    "business_impact",
)
CHECKPOINT_EVERY = 100


# ─────────────────────────────────────────────
# PROMPT BUILDER
# ─────────────────────────────────────────────

def build_system_prompt(reference_transcripts: list[str]) -> str:
    """
    System prompt passed once. Includes reference transcripts for domain
    context — model is explicitly told NOT to copy their style or content.
    """
    sample = random.sample(reference_transcripts, min(15, len(reference_transcripts)))
    ref_block = "\n---\n".join(f"[Reference {i+1}]: {t[:400]}" for i, t in enumerate(sample))

    return f"""You are a data generation assistant creating realistic customer support tickets for a training dataset.

REFERENCE TRANSCRIPTS (for domain context ONLY):
The following are real support transcripts. Read them to understand the domain vocabulary, types of issues, and context. 
Do NOT copy, paraphrase, or replicate their style, phrasing, or specific details.

{ref_block}

YOUR TASK:
Generate synthetic customer support tickets that are:
- Completely original — no resemblance to the reference transcripts above
- Realistic and human-sounding
- Diverse in writing style, tone, length, and vocabulary
- Representative of the assigned domain and ticket type

OUTPUT FORMAT:
Always respond with a single valid JSON object and nothing else:
{{
  "subject": "<3 to 8 word summary of the specific issue>",
  "text": "<the full ticket text>"
}}"""


def build_user_prompt(
    ticket_type: str,
    domain: str,
    style: str,
    issue_hint: str | None = None,
) -> str:
    """
    Per-ticket user prompt. issue_hint is only used for leasing domain
    to encourage coverage of all issue types.
    """
    issue_line = f"- The ticket should relate to: {issue_hint}\n" if issue_hint else ""
    length_hint = random.choice(LENGTH_HINTS)

    return f"""Generate a customer support {ticket_type} for the domain: {domain}

Requirements:
- Writing style: {style}
- {length_hint}
{issue_line}- The subject must be a short specific phrase (3-8 words) describing the exact issue in the text
- The text must sound like it was written by a real customer, not an AI
- Do not use generic filler phrases like "I hope this message finds you well"
- Do not include any labels, categories, or metadata in the text itself

Respond with JSON only."""


# ─────────────────────────────────────────────
# MODEL LOADER
# ─────────────────────────────────────────────

def load_model(model_name: str):
    print(f"\nLoading {model_name}...")
    tokenizer = AutoTokenizer.from_pretrained(model_name, trust_remote_code=True)

    model = AutoModelForCausalLM.from_pretrained(
        model_name,
        torch_dtype=torch.bfloat16 if torch.cuda.is_available() else torch.float32,
        device_map="auto",
        trust_remote_code=True,
    )
    model.eval()
    print(f"Model loaded on: {next(model.parameters()).device}")
    return tokenizer, model


# ─────────────────────────────────────────────
# GENERATION
# ─────────────────────────────────────────────

def parse_generated_json(raw: str) -> dict[str, Any]:
    json_match = re.search(r"\{.*\}", raw, re.DOTALL)
    if not json_match:
        raise ValueError("No JSON object found in response")

    parsed = json.loads(json_match.group(0))
    if "subject" not in parsed or "text" not in parsed:
        raise ValueError("Missing 'subject' or 'text' in JSON")
    if len(parsed["text"].strip()) < 20:
        raise ValueError("Generated text too short")
    return parsed

def generate_ticket(
    tokenizer,
    model,
    system_prompt: str,
    user_prompt: str,
    max_new_tokens: int = 512,
    retries: int = 3,
) -> dict | None:
    """
    Calls Phi-4 with the given prompts and parses the JSON response.
    Retries up to `retries` times on parse failure.
    """
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

            with torch.no_grad():
                output_ids = model.generate(
                    input_ids,
                    max_new_tokens=max_new_tokens,
                    do_sample=True,
                    temperature=0.9,       # High temperature = more diversity
                    top_p=0.95,
                    repetition_penalty=1.1,
                    pad_token_id=tokenizer.eos_token_id,
                )

            # Decode only the newly generated tokens
            new_tokens = output_ids[0][input_ids.shape[-1]:]
            raw = tokenizer.decode(new_tokens, skip_special_tokens=True).strip()
            return parse_generated_json(raw)

        except (json.JSONDecodeError, ValueError) as e:
            if attempt < retries - 1:
                time.sleep(0.5)
                continue
            print(f"  [WARN] Failed after {retries} attempts: {e}")
            return None


# ─────────────────────────────────────────────
# DOMAIN SAMPLER
# ─────────────────────────────────────────────

def build_generation_plan(n_complaints: int, n_inquiries: int) -> list[dict]:
    """
    Builds the full list of (ticket_type, domain) assignments before generation.
    Ensures domain distribution is respected across both ticket types.
    """
    plan = []

    for ticket_type, total in [("complaint", n_complaints), ("inquiry", n_inquiries)]:
        domain_counts = {
            domain: max(1, round(ratio * total))
            for domain, ratio in DOMAIN_DISTRIBUTION.items()
        }

        # Adjust rounding errors to hit exact total
        diff = total - sum(domain_counts.values())
        domain_counts[PRIMARY_DOMAIN] += diff

        for domain, count in domain_counts.items():
            plan.extend({"ticket_type": ticket_type, "domain": domain} for _ in range(count))

    random.shuffle(plan)
    return plan


# ─────────────────────────────────────────────
# LEASING ISSUE TRACKER
# (ensures all leasing issue types get covered)
# ─────────────────────────────────────────────

class LeasingIssueSampler:
    def __init__(self):
        self.queue = []
        self._refill()

    def _refill(self):
        shuffled = LEASING_ISSUES.copy()
        random.shuffle(shuffled)
        self.queue.extend(shuffled)

    def next(self) -> str:
        if not self.queue:
            self._refill()
        return self.queue.pop(0)


def build_result_row(ticket_type: str, domain: str, generated: dict[str, Any]) -> dict[str, Any]:
    return {
        "ticket_type": ticket_type,
        "subject": generated["subject"].strip(),
        "text": generated["text"].strip(),
        "domain": domain,
        # Phase 2 labels — to be filled in phase2_classify.py
        **{column: None for column in PHASE2_LABEL_COLUMNS},
    }


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Phase 1: Synthetic ticket generation with Phi-4")
    parser.add_argument("--dataset",    required=True,  help="Path to dataset.csv (must have 'transcript' column)")
    parser.add_argument("--output",     default="output/unlabeled.csv", help="Path to save generated CSV")
    parser.add_argument("--model",      default=MODEL_NAME, help="HuggingFace model name")
    parser.add_argument("--dry-run",    action="store_true", help="Generate only 10 tickets for testing")
    parser.add_argument("--complaints", type=int, default=TARGET_COMPLAINTS)
    parser.add_argument("--inquiries",  type=int, default=TARGET_INQUIRIES)
    args = parser.parse_args()

    # ── Load reference dataset ──
    print(f"Loading reference dataset from: {args.dataset}")
    ref_df = pd.read_csv(args.dataset)
    if "transcript" not in ref_df.columns:
        raise ValueError("dataset.csv must have a 'transcript' column")
    transcripts = ref_df["transcript"].dropna().astype(str).tolist()
    print(f"Loaded {len(transcripts)} reference transcripts")

    # ── Dry run override ──
    n_complaints = 5 if args.dry_run else args.complaints
    n_inquiries  = 5 if args.dry_run else args.inquiries
    if args.dry_run:
        print("\n[DRY RUN] Generating 10 tickets only")

    # ── Build generation plan ──
    plan = build_generation_plan(n_complaints, n_inquiries)
    print(f"\nGeneration plan: {n_complaints} complaints + {n_inquiries} inquiries = {len(plan)} total")

    # ── Load model ──
    tokenizer, model = load_model(args.model)

    # ── Build system prompt (uses random sample of reference transcripts) ──
    system_prompt = build_system_prompt(transcripts)

    # ── Setup ──
    leasing_sampler = LeasingIssueSampler()
    results = []
    failed = 0

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # ── Generate ──
    for item in tqdm(plan, desc="Generating tickets"):
        ticket_type = item["ticket_type"]
        domain      = item["domain"]
        style       = random.choice(STYLES)

        # For leasing domain, cycle through issue types to ensure coverage
        issue_hint = None
        if domain == PRIMARY_DOMAIN:
            issue_hint = leasing_sampler.next()

        user_prompt = build_user_prompt(ticket_type, domain, style, issue_hint)

        result = generate_ticket(tokenizer, model, system_prompt, user_prompt)

        if result:
            results.append(build_result_row(ticket_type, domain, result))
        else:
            failed += 1

        # Checkpoint every 100 rows
        if results and len(results) % CHECKPOINT_EVERY == 0:
            pd.DataFrame(results).to_csv(output_path, index=False)

    # ── Save final output ──
    df = pd.DataFrame(results)
    df.to_csv(output_path, index=False)

    print(f"\n{'='*50}")
    print(f"Generation complete")
    print(f"  Successful : {len(results)}")
    print(f"  Failed     : {failed}")
    print(f"  Saved to   : {output_path}")
    print(f"\nDomain distribution:")
    print(df.groupby(["ticket_type", "domain"]).size().to_string())


if __name__ == "__main__":
    main()
