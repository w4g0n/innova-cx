"""
Phase 1 — Synthetic Complaint Generation using Phi-4-mini-instruct
===================================================================
Generates complaints for the office tenant/leasing domain.
Complaints only — no inquiries.

Checkpoints every 100 accepted rows to output/phase1_checkpoint.csv.
Supports --resume to continue from an interrupted run.

Usage:
    python phase1_generate.py
    python phase1_generate.py --resume
    python phase1_generate.py --dry-run          # 50 rows only
    python phase1_generate.py --complaints 500   # custom count
"""

import argparse
import importlib
import json
import random
import re
import time
import warnings
from pathlib import Path

import pandas as pd
import torch
from tqdm import tqdm
from transformers import AutoModelForCausalLM, AutoTokenizer

# ── Phi-4 compatibility shims ──────────────────────────────────────────────────
# Some transformers releases dropped/renamed internal classes that Phi-4's
# remote code references. These shims keep the import from crashing.
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

warnings.filterwarnings("ignore")

# ── Paths ──────────────────────────────────────────────────────────────────────
BASE_DIR        = Path(__file__).resolve().parent
OUTPUT_DIR      = BASE_DIR / "output"
CHECKPOINT_PATH = OUTPUT_DIR / "phase1_checkpoint.csv"
COMPLETE_PATH   = OUTPUT_DIR / "phase1_complete.csv"

# Local cache for model (populated by setup_models.py if run first).
LOCAL_MODEL_DIR = BASE_DIR / "models" / "generator" / "phi-4-mini-instruct"
REMOTE_MODEL    = "microsoft/Phi-4-mini-instruct"
MODEL_NAME      = str(LOCAL_MODEL_DIR) if LOCAL_MODEL_DIR.exists() else REMOTE_MODEL

# ── Generation config ──────────────────────────────────────────────────────────
TARGET_COMPLAINTS    = 10_000
CHECKPOINT_EVERY     = 100
SAFETY_OVERSAMPLE_RATE = 0.08  # 8% of rows get explicit safety-scenario hints
MIN_SUBJECT_LEN      = 3
MIN_TEXT_LEN         = 20

# Version checks (Phi-4 mini requires recent transformers)
MIN_TRANSFORMERS = (4, 55, 0)
MIN_ACCELERATE   = (0, 34, 0)
MIN_TOKENIZERS   = (0, 21, 0)

# ── Domain distribution ────────────────────────────────────────────────────────
# Weights reflect a realistic office-leasing complaint mix.
# Must sum to 1.0.
DOMAIN_DISTRIBUTION: dict[str, float] = {
    "office leasing and tenant support":              0.22,
    "office building management and facilities":      0.12,
    "commercial property and workspace rental":       0.10,
    "office utilities and building services":         0.10,
    "IT and office technology support":               0.08,
    "office parking and access control":              0.06,
    "shared workspace and coworking":                 0.06,
    "office security and visitor management":         0.05,
    "reception and front desk services":              0.04,
    "office cleaning and janitorial services":        0.04,
    "conference room and meeting space management":   0.04,
    "office fit-out and renovation":                  0.03,
    "business rates and property tax disputes":       0.02,
    "mail and courier services":                      0.02,
    "office health and safety compliance":            0.02,
}

PRIMARY_DOMAIN = "office leasing and tenant support"

# ── Writing styles ─────────────────────────────────────────────────────────────
STYLES: list[str] = [
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

# ── Length hints ───────────────────────────────────────────────────────────────
LENGTH_HINTS: list[str] = [
    "Write 1-2 sentences only.",
    "Write 2-4 sentences.",
    "Write a short paragraph (4-6 sentences).",
]

# ── Issue types for primary leasing domain ─────────────────────────────────────
# Cycled round-robin so all types get covered evenly.
LEASING_ISSUES: list[str] = [
    "office rent payment dispute",
    "office lease renewal or termination",
    "maintenance request that was ignored or delayed",
    "security deposit or retainer deduction dispute",
    "noise complaint from neighboring tenant or floor",
    "unsafe office conditions (broken HVAC, electrical issues, structural damage)",
    "eviction or lease termination notice received unexpectedly",
    "landlord or management accessing office without prior notice",
    "utility or service charge billing dispute",
    "office move-in or move-out process issue",
    "pest infestation in office space",
    "parking, loading bay, or common area dispute",
    "lease terms or square footage misrepresentation",
    "delayed repairs affecting office operations",
    "rent or service charge increase dispute",
    "elevator or building access system failure",
    "shared facilities (bathrooms, kitchens) not being maintained",
    "signage or branding rights dispute",
]

# ── Safety-specific issue hints ────────────────────────────────────────────────
# Used to oversample safety=True scenarios. Without these, safety_concern=True
# is underrepresented because most routine complaints are not safety-related.
SAFETY_ISSUES: list[str] = [
    "gas leak or carbon monoxide smell detected in office",
    "electrical fault causing sparks, burning smell, or tripped circuits",
    "structural damage to ceiling, walls, or floor posing collapse risk",
    "fire or smoke detected inside the office building",
    "flooding or water ingress near electrical panels or server equipment",
    "mold growth causing respiratory symptoms in staff",
    "asbestos exposure concern during renovation or repair work",
    "blocked or broken fire exit doors preventing safe evacuation",
    "faulty smoke or fire alarm not triggering during monthly test",
    "exposed live electrical wiring accessible to office staff",
]


# ── System prompt ──────────────────────────────────────────────────────────────
SYSTEM_PROMPT = """You are a data generation assistant creating realistic customer complaint tickets.

YOUR TASK:
Generate ONE original customer complaint for an office leasing and property management system.
A complaint is a report of a problem, failure, or bad experience.

IMPORTANT RULES:
- Generate a COMPLAINT only. Do NOT generate questions, inquiries, or requests for information.
- The complaint must sound like a real office tenant wrote it — frustrated, specific, and human.
- Do NOT use generic filler like "I hope this message finds you well" or "I am writing to inform you".
- Do NOT include category labels, metadata, or structured fields inside the complaint text itself.
- Be specific about the problem — vague complaints are useless training data.

OUTPUT FORMAT:
Respond with a single valid JSON object only. No markdown, no code fences, no extra text.
Start with '{' and end with '}'.

{
  "subject": "<3 to 8 word summary of the specific problem>",
  "text": "<the full complaint text>"
}"""


def build_user_prompt(domain: str, style: str, issue_hint: str | None, length_hint: str) -> str:
    hint_line = f"- The complaint must be about: {issue_hint}\n" if issue_hint else ""
    return (
        f"Generate a customer complaint for the domain: {domain}\n\n"
        f"Requirements:\n"
        f"- Writing style: {style}\n"
        f"- {length_hint}\n"
        f"{hint_line}"
        f"- Subject: 3-8 words describing the specific problem\n"
        f"- Text: must sound like a real frustrated tenant, not an AI\n\n"
        f"Respond with JSON only."
    )


# ── Model version check ────────────────────────────────────────────────────────

def _parse_version(value: str) -> tuple[int, ...]:
    parts = []
    for token in re.split(r"[.+-]", value):
        if token.isdigit():
            parts.append(int(token))
        else:
            break
    return tuple(parts)


def _check_versions() -> None:
    for pkg, minimum in [
        ("transformers", MIN_TRANSFORMERS),
        ("accelerate",   MIN_ACCELERATE),
        ("tokenizers",   MIN_TOKENIZERS),
    ]:
        mod = importlib.import_module(pkg)
        got = _parse_version(getattr(mod, "__version__", "0"))
        if got < minimum:
            min_str = ".".join(str(n) for n in minimum)
            raise RuntimeError(
                f"{pkg}=={getattr(mod, '__version__', '?')} is too old. "
                f"Required >= {min_str}. Run: pip install -r requirements.txt"
            )


# ── Model loader ───────────────────────────────────────────────────────────────

def load_model(model_name: str) -> tuple:
    _check_versions()
    print(f"\nLoading {model_name}...")
    tokenizer = AutoTokenizer.from_pretrained(model_name, trust_remote_code=True)
    has_cuda  = torch.cuda.is_available()

    model = None
    # Attempt 1: 8-bit quantization (CUDA only)
    if has_cuda:
        try:
            from transformers import BitsAndBytesConfig
            bnb_cfg = BitsAndBytesConfig(load_in_8bit=True)
            model = AutoModelForCausalLM.from_pretrained(
                model_name,
                quantization_config=bnb_cfg,
                device_map="auto",
                trust_remote_code=True,
            )
            print("Model backend: 8-bit quantized (CUDA)")
        except Exception as e:
            print(f"[WARN] 8-bit load failed ({e}), trying fp16...")

    # Attempt 2: fp16 GPU
    if model is None and has_cuda:
        try:
            model = AutoModelForCausalLM.from_pretrained(
                model_name,
                torch_dtype=torch.float16,
                device_map="auto",
                trust_remote_code=True,
            )
            print("Model backend: fp16 (CUDA)")
        except Exception as e:
            print(f"[WARN] fp16 GPU load failed ({e}), falling back to CPU...")

    # Attempt 3: CPU fallback
    if model is None:
        model = AutoModelForCausalLM.from_pretrained(
            model_name,
            torch_dtype=torch.float32,
            trust_remote_code=True,
        )
        print("Model backend: fp32 (CPU) — generation will be slow")

    model.eval()
    if torch.cuda.is_available():
        print(f"Model on device: {next(model.parameters()).device} | "
              f"VRAM: {torch.cuda.memory_allocated() / 1e9:.1f}GB")
    return tokenizer, model


# ── JSON parsing ───────────────────────────────────────────────────────────────

def _unescape_json_string(value: str) -> str:
    return json.loads(f'"{value}"')


def parse_json_response(raw: str) -> dict | None:
    cleaned = raw.strip().replace("```json", "").replace("```", "").strip()

    # Primary: extract full JSON object
    m = re.search(r"\{.*\}", cleaned, re.DOTALL)
    if m:
        try:
            parsed  = json.loads(m.group(0))
            subject = str(parsed.get("subject", "")).strip()
            text    = str(parsed.get("text", "")).strip()
            if len(subject) >= MIN_SUBJECT_LEN and len(text) >= MIN_TEXT_LEN:
                return {"subject": subject, "text": text}
        except json.JSONDecodeError:
            pass

    # Fallback: field-level regex (handles partially malformed JSON)
    sm = re.search(r'"subject"\s*:\s*"((?:[^"\\]|\\.)*)"', cleaned, re.DOTALL)
    tm = re.search(r'"text"\s*:\s*"((?:[^"\\]|\\.)*)"', cleaned, re.DOTALL)
    if sm and tm:
        try:
            subject = _unescape_json_string(sm.group(1)).strip()
            text    = _unescape_json_string(tm.group(1)).strip()
            if len(subject) >= MIN_SUBJECT_LEN and len(text) >= MIN_TEXT_LEN:
                return {"subject": subject, "text": text}
        except Exception:
            pass

    return None


def _looks_like_json(value: str) -> bool:
    v = str(value).strip().lower()
    return v.startswith("{") or ('"subject"' in v and '"text"' in v)


# ── Single complaint generation ────────────────────────────────────────────────

def generate_complaint(
    tokenizer,
    model,
    user_prompt: str,
    max_new_tokens: int = 256,
    retries: int = 3,
    temperature: float = 0.7,
    top_p: float = 0.9,
) -> dict | None:
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user",   "content": user_prompt},
    ]
    current_max = max_new_tokens

    for attempt in range(retries):
        try:
            chat_inputs = tokenizer.apply_chat_template(
                messages,
                add_generation_prompt=True,
                return_tensors="pt",
            )

            with torch.no_grad():
                if isinstance(chat_inputs, torch.Tensor):
                    inputs     = chat_inputs.to(model.device)
                    attn_mask  = torch.ones_like(inputs)
                    prompt_len = inputs.shape[-1]
                    output_ids = model.generate(
                        inputs,
                        attention_mask=attn_mask,
                        max_new_tokens=current_max,
                        do_sample=True,
                        temperature=temperature,
                        top_p=top_p,
                        repetition_penalty=1.1,
                        pad_token_id=tokenizer.eos_token_id,
                    )
                else:
                    inputs = chat_inputs.to(model.device)
                    if "attention_mask" not in inputs:
                        inputs["attention_mask"] = torch.ones_like(inputs["input_ids"])
                    prompt_len = inputs["input_ids"].shape[-1]
                    output_ids = model.generate(
                        **inputs,
                        max_new_tokens=current_max,
                        do_sample=True,
                        temperature=temperature,
                        top_p=top_p,
                        repetition_penalty=1.1,
                        pad_token_id=tokenizer.eos_token_id,
                    )

            new_tokens = output_ids[0][prompt_len:]
            raw        = tokenizer.decode(new_tokens, skip_special_tokens=True).strip()
            parsed     = parse_json_response(raw)

            if parsed is None:
                raise ValueError(f"No valid JSON in output: {raw[:80]!r}")

            subject = " ".join(str(parsed["subject"]).split()).strip()
            text    = " ".join(str(parsed["text"]).split()).strip()

            if _looks_like_json(subject) or _looks_like_json(text):
                raise ValueError("Contaminated output — JSON leaked into text fields")
            if len(subject) < MIN_SUBJECT_LEN or len(text) < MIN_TEXT_LEN:
                raise ValueError("Generated fields are too short")

            return {"subject": subject, "text": text}

        except (json.JSONDecodeError, ValueError) as e:
            if attempt < retries - 1:
                time.sleep(0.3)
            else:
                print(f"  [WARN] Parse failed after {retries} attempts: {e}")
                return None

        except torch.OutOfMemoryError:
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            if attempt < retries - 1 and current_max > 64:
                current_max = max(64, current_max // 2)
                print(f"  [WARN] CUDA OOM — retrying with max_new_tokens={current_max}")
                time.sleep(0.5)
                continue
            print("  [WARN] CUDA OOM — skipping this row")
            return None

    return None


# ── Domain/issue samplers ──────────────────────────────────────────────────────

class _RoundRobinSampler:
    """Shuffled round-robin — every item gets drawn before any repeats."""
    def __init__(self, items: list[str]) -> None:
        self._items = items
        self._queue: list[str] = []
        self._refill()

    def _refill(self) -> None:
        shuffled = self._items.copy()
        random.shuffle(shuffled)
        self._queue.extend(shuffled)

    def next(self) -> str:
        if not self._queue:
            self._refill()
        return self._queue.pop(0)


# ── Plan builder ───────────────────────────────────────────────────────────────

def build_plan(n: int) -> list[dict]:
    """
    Build a shuffled list of generation assignments for n complaints.
    Each entry has: domain, and optionally safety_override=True for ~8% of rows.
    """
    plan: list[dict] = []
    for domain, ratio in DOMAIN_DISTRIBUTION.items():
        count = max(1, round(ratio * n))
        plan.extend({"domain": domain} for _ in range(count))

    # Adjust rounding error on primary domain
    diff = n - len(plan)
    if diff > 0:
        plan.extend({"domain": PRIMARY_DOMAIN} for _ in range(diff))
    elif diff < 0:
        plan = plan[:n]

    # Mark ~8% for safety oversampling
    n_safety     = max(1, round(SAFETY_OVERSAMPLE_RATE * n))
    safety_idxs  = random.sample(range(len(plan)), min(n_safety, len(plan)))
    for idx in safety_idxs:
        plan[idx]["safety_override"] = True

    random.shuffle(plan)
    return plan


# ── Main ───────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="V8 Phase 1: Complaint Generation")
    parser.add_argument("--complaints",     type=int,   default=TARGET_COMPLAINTS,
                        help=f"Number of complaints to generate (default: {TARGET_COMPLAINTS})")
    parser.add_argument("--model",          default=MODEL_NAME)
    parser.add_argument("--max-new-tokens", type=int,   default=256)
    parser.add_argument("--retries",        type=int,   default=3)
    parser.add_argument("--temperature",    type=float, default=0.7)
    parser.add_argument("--top-p",          type=float, default=0.9)
    parser.add_argument("--resume",         action="store_true",
                        help="Resume from existing checkpoint")
    parser.add_argument("--dry-run",        action="store_true",
                        help="Generate only 50 complaints (quick test)")
    args = parser.parse_args()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # ── Resume: load existing checkpoint ──────────────────────────────────────
    results: list[dict] = []
    if args.resume and CHECKPOINT_PATH.exists():
        existing = pd.read_csv(CHECKPOINT_PATH)
        results  = existing.to_dict("records")
        print(f"[RESUME] Loaded {len(results)} rows from checkpoint")

    target    = 50 if args.dry_run else args.complaints
    remaining = max(0, target - len(results))
    start_idx = len(results)  # for ticket_id assignment

    if args.dry_run:
        print(f"[DRY RUN] Generating {remaining} complaints")

    if remaining == 0:
        print(f"Target of {target} already reached. Saving and exiting.")
        pd.DataFrame(results).to_csv(COMPLETE_PATH, index=False)
        return

    plan = build_plan(remaining)

    # ── Load model ────────────────────────────────────────────────────────────
    tokenizer, model = load_model(args.model)
    leasing_sampler  = _RoundRobinSampler(LEASING_ISSUES)
    safety_sampler   = _RoundRobinSampler(SAFETY_ISSUES)

    stats = {"accepted": 0, "failed": 0}

    for item in tqdm(plan, desc="Generating complaints"):
        domain          = item["domain"]
        style           = random.choice(STYLES)
        length_hint     = random.choice(LENGTH_HINTS)
        safety_override = item.get("safety_override", False)

        if safety_override:
            issue_hint = safety_sampler.next()
        elif domain == PRIMARY_DOMAIN:
            issue_hint = leasing_sampler.next()
        else:
            issue_hint = None

        user_prompt = build_user_prompt(domain, style, issue_hint, length_hint)

        result = generate_complaint(
            tokenizer, model, user_prompt,
            max_new_tokens=args.max_new_tokens,
            retries=args.retries,
            temperature=args.temperature,
            top_p=args.top_p,
        )

        if result:
            ticket_id = f"V8-{start_idx + stats['accepted']:05d}"
            results.append({
                "ticket_id":  ticket_id,
                "subject":    result["subject"],
                "text":       result["text"],
                "domain":     domain,
                "style":      style,
                "issue_hint": issue_hint or "",
            })
            stats["accepted"] += 1
        else:
            stats["failed"] += 1

        # Checkpoint every 100 accepted rows
        if results and len(results) % CHECKPOINT_EVERY == 0:
            pd.DataFrame(results).to_csv(CHECKPOINT_PATH, index=False)

    # ── Final save ────────────────────────────────────────────────────────────
    df = pd.DataFrame(results)
    df.to_csv(CHECKPOINT_PATH, index=False)
    df.to_csv(COMPLETE_PATH, index=False)

    print(f"\n{'='*55}")
    print(f"Phase 1 complete")
    print(f"  Accepted  : {stats['accepted']}")
    print(f"  Failed    : {stats['failed']}")
    print(f"  Total     : {len(results)}")
    print(f"  Saved to  : {COMPLETE_PATH}")
    print(f"\nDomain breakdown:")
    print(df.groupby("domain").size().sort_values(ascending=False).to_string())
    safety_rows = df[df["issue_hint"].isin(SAFETY_ISSUES)]
    print(f"\nSafety-seeded rows: {len(safety_rows)} ({len(safety_rows)/len(df)*100:.1f}%)")


if __name__ == "__main__":
    main()
