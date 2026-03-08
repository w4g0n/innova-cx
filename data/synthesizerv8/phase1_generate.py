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
    python phase1_generate.py --dry-run --dry-run-count 5
    python phase1_generate.py --complaints 500   # custom count
"""

import argparse
import collections
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
try:
    from transformers import BitsAndBytesConfig
except Exception:
    BitsAndBytesConfig = None  # type: ignore[assignment]

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

# Patch: some transformers releases pass a list into get_expanded_tied_weights_keys
# which calls .keys() expecting a dict — crashes with AttributeError on 'list'.
# This affects Phi-4-mini on transformers versions where tied_weights_keys is a list.
try:
    from transformers import modeling_utils as _mu
    _orig_get_expanded = _mu.PreTrainedModel.get_expanded_tied_weights_keys

    def _patched_get_expanded(self, all_submodels=True):
        try:
            return _orig_get_expanded(self, all_submodels)
        except AttributeError:
            # Return empty dict — callers like mark_tied_weights_as_initialized
            # call .keys() on the result, so {} is required (not set()).
            return {}

    _mu.PreTrainedModel.get_expanded_tied_weights_keys = _patched_get_expanded
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
LABEL_COLS           = ["issue_severity", "issue_urgency", "safety_concern", "business_impact"]
LEVEL_VALUES         = {"low", "medium", "high"}
MAX_RECENT_TEXTS     = 250
MAX_JACCARD_SIMILARITY = 0.75
DEPARTMENTS = [
    "Facilities Management",
    "Legal & Compliance",
    "Safety & Security",
    "HR",
    "Leasing",
    "Maintenance",
    "IT",
]

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


# ── Few-shot labeling guidance (same logic used in Phase 3 labeling) ──────────
FEW_SHOT_EXAMPLES = [
    {
        "text": "The bin in the kitchen hasn't been emptied in three days. It's starting to smell.",
        "labels": {"issue_severity": "low", "issue_urgency": "low", "safety_concern": False, "business_impact": "low"},
    },
    {
        "text": "Our office HVAC has been broken for two days. It's 32 degrees in here and staff are struggling to concentrate. We need this fixed today.",
        "labels": {"issue_severity": "high", "issue_urgency": "high", "safety_concern": True, "business_impact": "high"},
    },
    {
        "text": "The projector in meeting room 3B stopped working this morning. We have client presentations scheduled all week and cannot use that room.",
        "labels": {"issue_severity": "medium", "issue_urgency": "medium", "safety_concern": False, "business_impact": "medium"},
    },
    {
        "text": "There is a water leak coming through the ceiling above our server room. Water is dripping onto equipment right now.",
        "labels": {"issue_severity": "high", "issue_urgency": "high", "safety_concern": True, "business_impact": "high"},
    },
]


def build_system_prompt() -> str:
    examples_block = ""
    for ex in FEW_SHOT_EXAMPLES:
        examples_block += f'Text: "{ex["text"]}"\n'
        examples_block += f'Labels: {json.dumps(ex["labels"])}\n\n'

    return f"""You are a data generation assistant creating realistic customer complaint tickets.

YOUR TASK:
Generate ONE original customer complaint for an office leasing and property management system.
Generate complaint text and labels together so labels match the text exactly.

IMPORTANT RULES:
- Generate a COMPLAINT only. Do NOT generate questions, inquiries, or requests for information.
- The complaint must sound like a real office tenant wrote it — frustrated, specific, and human.
- Do NOT include category labels or metadata inside the complaint text.
- Do NOT copy wording from the examples; use fresh phrasing every time.
- Be specific about the problem — vague complaints are useless training data.

LABEL DEFINITIONS:
- issue_severity: low | medium | high
  low = cosmetic/minor issue, medium = one system affected, high = critical failure
- issue_urgency: low | medium | high
  low = no time pressure, medium = within days, high = immediate/same-day
- safety_concern: true | false
  true only for explicit physical hazard (fire/electrical/flood/structural/injury risk)
- business_impact: low | medium | high
  low = minimal productivity impact, medium = partial disruption, high = major outage/blocked operations

EXAMPLES:
{examples_block}OUTPUT FORMAT:
Respond with a single valid JSON object only. No markdown, no code fences, no extra text.
Start with '{{' and end with '}}'.

{{
  "subject": "<3 to 8 word summary of the specific problem>",
  "text": "<the full complaint text>",
  "department": "Facilities Management|Legal & Compliance|Safety & Security|HR|Leasing|Maintenance|IT",
  "issue_severity": "low|medium|high",
  "issue_urgency": "low|medium|high",
  "safety_concern": true|false,
  "business_impact": "low|medium|high"
}}"""


SYSTEM_PROMPT = build_system_prompt()


def build_user_prompt(
    domain: str,
    style: str,
    issue_hint: str | None,
    length_hint: str,
    target_labels: dict,
) -> str:
    hint_line = f"- The complaint must be about: {issue_hint}\n" if issue_hint else ""
    label_line = (
        "- Label targets to enforce:\n"
        f"  - department: {target_labels['department']}\n"
        f"  - issue_severity: {target_labels['issue_severity']}\n"
        f"  - issue_urgency: {target_labels['issue_urgency']}\n"
        f"  - safety_concern: {str(target_labels['safety_concern']).lower()}\n"
        f"  - business_impact: {target_labels['business_impact']}\n"
    )
    return (
        f"Generate a customer complaint for the domain: {domain}\n\n"
        f"Requirements:\n"
        f"- Writing style: {style}\n"
        f"- {length_hint}\n"
        f"{hint_line}"
        f"{label_line}"
        f"- Subject: 3-8 words describing the specific problem\n"
        f"- Text: must sound like a real frustrated tenant, not an AI\n\n"
        f"- Use wording that is distinct from common template/example phrasing\n"
        f"Respond with JSON only and ensure labels are consistent with the complaint text."
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

def load_model(model_name: str, quantize: str = "none") -> tuple:
    _check_versions()
    print(f"\nLoading {model_name}...")
    tokenizer = AutoTokenizer.from_pretrained(model_name, trust_remote_code=True)
    has_cuda  = torch.cuda.is_available()

    model = None
    # Attempt 1: GPU quantized (optional)
    if has_cuda and quantize in {"4bit", "8bit"} and BitsAndBytesConfig is not None:
        try:
            if quantize == "4bit":
                qcfg = BitsAndBytesConfig(
                    load_in_4bit=True,
                    bnb_4bit_quant_type="nf4",
                    bnb_4bit_compute_dtype=torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16,
                    bnb_4bit_use_double_quant=True,
                )
            else:
                qcfg = BitsAndBytesConfig(load_in_8bit=True)
            model = AutoModelForCausalLM.from_pretrained(
                model_name,
                quantization_config=qcfg,
                device_map="auto",
                trust_remote_code=True,
            )
            print(f"Model backend: {quantize} quantized (CUDA)")
        except Exception as e:
            print(f"[WARN] {quantize} quantized load failed ({e}), trying non-quantized GPU...")

    if has_cuda and quantize in {"4bit", "8bit"} and BitsAndBytesConfig is None:
        print(f"[WARN] quantize={quantize} requested but BitsAndBytesConfig unavailable; using non-quantized backend")

    # Attempt 2: GPU (prefer bf16 for stability, fallback to fp16)
    if has_cuda:
        try:
            if model is not None:
                pass
            else:
                gpu_dtype = torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16
                model = AutoModelForCausalLM.from_pretrained(
                    model_name,
                    dtype=gpu_dtype,
                    low_cpu_mem_usage=False,
                    trust_remote_code=True,
                )
                model = model.to("cuda")
                print(f"Model backend: {str(gpu_dtype).replace('torch.', '')} (CUDA)")
        except Exception as e:
            print(f"[WARN] GPU load failed ({e}), falling back to CPU...")

    # Attempt 3: CPU fallback
    if model is None:
        model = AutoModelForCausalLM.from_pretrained(
            model_name,
            dtype=torch.float32,
            low_cpu_mem_usage=False,
            trust_remote_code=True,
        )
        print("Model backend: fp32 (CPU) — generation will be slow")

    model.eval()
    if torch.cuda.is_available():
        print(f"Model on device: {next(model.parameters()).device} | "
              f"VRAM: {torch.cuda.memory_allocated() / 1e9:.1f}GB")
    _repair_phi_meta_buffers(model)
    return tokenizer, model


# ── JSON parsing ───────────────────────────────────────────────────────────────


def _parse_bool(value) -> bool | None:
    if isinstance(value, bool):
        return value
    v = str(value).strip().lower()
    if v in ("true", "1", "yes"):
        return True
    if v in ("false", "0", "no"):
        return False
    return None


def _extract_labels(parsed: dict) -> dict | None:
    dept = str(parsed.get("department", "")).strip()
    sev = str(parsed.get("issue_severity", "")).strip().lower()
    urg = str(parsed.get("issue_urgency", "")).strip().lower()
    imp = str(parsed.get("business_impact", "")).strip().lower()
    saf = _parse_bool(parsed.get("safety_concern"))
    if dept not in DEPARTMENTS:
        return None
    if sev not in LEVEL_VALUES or urg not in LEVEL_VALUES or imp not in LEVEL_VALUES:
        return None
    if saf is None:
        return None
    return {
        "department": dept,
        "issue_severity": sev,
        "issue_urgency": urg,
        "safety_concern": saf,
        "business_impact": imp,
    }


def parse_json_response(raw: str) -> dict | None:
    cleaned = raw.strip().replace("```json", "").replace("```", "").strip()

    # Primary: extract full JSON object
    m = re.search(r"\{.*\}", cleaned, re.DOTALL)
    if m:
        try:
            parsed  = json.loads(m.group(0))
            subject = str(parsed.get("subject", "")).strip()
            text    = str(parsed.get("text", "")).strip()
            labels  = _extract_labels(parsed)
            if labels and len(subject) >= MIN_SUBJECT_LEN and len(text) >= MIN_TEXT_LEN:
                return {"subject": subject, "text": text, **labels}
        except json.JSONDecodeError:
            pass

    return None


def _looks_like_json(value: str) -> bool:
    v = str(value).strip().lower()
    return v.startswith("{") or ('"subject"' in v and '"text"' in v)


def _normalized_tokens(text: str) -> set[str]:
    cleaned = re.sub(r"[^a-z0-9\s]", " ", str(text).lower())
    return {t for t in cleaned.split() if len(t) > 2}


def _jaccard_similarity(a: str, b: str) -> float:
    ta = _normalized_tokens(a)
    tb = _normalized_tokens(b)
    if not ta or not tb:
        return 0.0
    inter = len(ta & tb)
    union = len(ta | tb)
    return inter / union if union else 0.0


def _is_too_similar(text: str, references: list[str], threshold: float = MAX_JACCARD_SIMILARITY) -> bool:
    return any(_jaccard_similarity(text, ref) >= threshold for ref in references)


def _repair_phi_meta_buffers(model) -> int:
    """
    Phi-4 remote code can leave rotary buffers (original_inv_freq) on meta
    tensors in some torch/transformers combinations. Materialize them from
    inv_freq so generation can run.
    """
    repaired = 0
    try:
        device = next(model.parameters()).device
    except Exception:
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    for module in model.modules():
        if not hasattr(module, "original_inv_freq"):
            continue
        original = getattr(module, "original_inv_freq", None)
        if not (torch.is_tensor(original) and getattr(original, "is_meta", False)):
            continue

        inv = getattr(module, "inv_freq", None)
        if torch.is_tensor(inv) and not getattr(inv, "is_meta", False):
            restored = inv.detach().clone().to(device)
            try:
                module.register_buffer("original_inv_freq", restored, persistent=False)
            except Exception:
                setattr(module, "original_inv_freq", restored)
            repaired += 1

    if repaired:
        print(f"[PATCH] Repaired {repaired} meta rotary buffer(s) for Phi-4 compatibility")
    return repaired


# ── Single complaint generation ────────────────────────────────────────────────

def generate_complaint(
    tokenizer,
    model,
    user_prompt: str,
    expected_labels: dict | None = None,
    recent_texts: list[str] | None = None,
    enforce_diversity: bool = True,
    max_new_tokens: int = 256,
    retries: int = 3,
    do_sample: bool = False,
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

            with torch.inference_mode():
                if isinstance(chat_inputs, torch.Tensor):
                    inputs     = chat_inputs.to(model.device)
                    prompt_len = inputs.shape[-1]
                    output_ids = model.generate(
                        inputs,
                        max_new_tokens=current_max,
                        do_sample=do_sample,
                        temperature=temperature,
                        top_p=top_p,
                        use_cache=True,
                        repetition_penalty=1.1,
                        pad_token_id=tokenizer.eos_token_id,
                    )
                else:
                    inputs = chat_inputs.to(model.device)
                    prompt_len = inputs["input_ids"].shape[-1]
                    output_ids = model.generate(
                        **inputs,
                        max_new_tokens=current_max,
                        do_sample=do_sample,
                        temperature=temperature,
                        top_p=top_p,
                        use_cache=True,
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
            if enforce_diversity:
                if _is_too_similar(text, [ex["text"] for ex in FEW_SHOT_EXAMPLES]):
                    raise ValueError("Generated text too close to few-shot examples")
                if recent_texts and _is_too_similar(text, recent_texts):
                    raise ValueError("Generated text too similar to recent outputs")
            if expected_labels:
                for key, expected_value in expected_labels.items():
                    if parsed.get(key) != expected_value:
                        raise ValueError(f"{key} mismatch: got={parsed.get(key)!r}, expected={expected_value!r}")

            return {"subject": subject, "text": text, **{k: parsed[k] for k in ["department", *LABEL_COLS]}}

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
        except NotImplementedError as e:
            if "meta tensor" in str(e).lower() and attempt < retries - 1:
                _repair_phi_meta_buffers(model)
                time.sleep(0.2)
                continue
            raise

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

    # Attach balanced label targets, including equal department spread.
    dept_sampler = _RoundRobinSampler(DEPARTMENTS)
    sev_sampler = _RoundRobinSampler(["low", "medium", "high"])
    urg_sampler = _RoundRobinSampler(["low", "medium", "high"])
    imp_sampler = _RoundRobinSampler(["low", "medium", "high"])

    safety_true_target = max(1, round(0.50 * n))
    safety_flags = [True] * safety_true_target + [False] * max(0, n - safety_true_target)
    random.shuffle(safety_flags)

    for i, item in enumerate(plan):
        item["target_department"] = dept_sampler.next()
        item["target_issue_severity"] = sev_sampler.next()
        item["target_issue_urgency"] = urg_sampler.next()
        item["target_business_impact"] = imp_sampler.next()
        item["target_safety_concern"] = bool(safety_flags[i]) if i < len(safety_flags) else False
        if item.get("safety_override", False):
            item["target_safety_concern"] = True
            # Keep safety rows coherent with higher urgency/severity by default.
            item["target_issue_severity"] = random.choice(["medium", "high"])
            item["target_issue_urgency"] = random.choice(["medium", "high"])
            item["target_business_impact"] = random.choice(["medium", "high"])

    return plan


# ── Main ───────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="V8 Phase 1: Complaint Generation")
    parser.add_argument("--complaints",     type=int,   default=TARGET_COMPLAINTS,
                        help=f"Number of complaints to generate (default: {TARGET_COMPLAINTS})")
    parser.add_argument("--model",          default=MODEL_NAME)
    parser.add_argument("--max-new-tokens", type=int,   default=256)
    parser.add_argument("--retries",        type=int,   default=3)
    parser.add_argument("--do-sample",      action="store_true",
                        help="Enable stochastic decoding (disabled by default for stability)")
    parser.add_argument("--temperature",    type=float, default=0.2)
    parser.add_argument("--top-p",          type=float, default=0.9)
    parser.add_argument("--resume",         action="store_true",
                        help="Resume from existing checkpoint")
    parser.add_argument("--quantize",       choices=["none", "8bit", "4bit"], default="none",
                        help="Optional GPU quantization mode")
    parser.add_argument("--dry-run",        action="store_true",
                        help="Quick test mode")
    parser.add_argument("--dry-run-count",  type=int, default=50,
                        help="Number of complaints in dry-run mode (default: 50)")
    args = parser.parse_args()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # ── Resume: load existing checkpoint ──────────────────────────────────────
    results: list[dict] = []
    if args.resume and CHECKPOINT_PATH.exists():
        existing = pd.read_csv(CHECKPOINT_PATH)
        results  = existing.to_dict("records")
        print(f"[RESUME] Loaded {len(results)} rows from checkpoint")

    target    = args.dry_run_count if args.dry_run else args.complaints
    remaining = max(0, target - len(results))
    start_idx = len(results)  # for ticket_id assignment

    if args.dry_run:
        print(f"[DRY RUN] Generating {remaining} complaints")

    if remaining == 0:
        print(f"Target of {target} already reached. Saving and exiting.")
        pd.DataFrame(results).to_csv(COMPLETE_PATH, index=False)
        return

    plan = build_plan(remaining)

    # Faster defaults for quick smoke tests.
    effective_max_new_tokens = args.max_new_tokens
    effective_retries = args.retries
    enforce_diversity = True
    if args.dry_run:
        effective_max_new_tokens = min(args.max_new_tokens, 96)
        effective_retries = min(args.retries, 1)
        enforce_diversity = False

    # ── Load model ────────────────────────────────────────────────────────────
    tokenizer, model = load_model(args.model, quantize=args.quantize)
    leasing_sampler  = _RoundRobinSampler(LEASING_ISSUES)
    safety_sampler   = _RoundRobinSampler(SAFETY_ISSUES)

    stats = {"accepted": 0, "failed": 0}
    recent_texts = collections.deque(maxlen=MAX_RECENT_TEXTS)

    for item in tqdm(plan, desc="Generating complaints"):
        domain          = item["domain"]
        style           = random.choice(STYLES)
        length_hint     = random.choice(LENGTH_HINTS)
        safety_override = item.get("safety_override", False)

        if item["target_safety_concern"]:
            issue_hint = safety_sampler.next()
        elif domain == PRIMARY_DOMAIN:
            issue_hint = leasing_sampler.next()
        else:
            issue_hint = None

        target_labels = {
            "department": item["target_department"],
            "issue_severity": item["target_issue_severity"],
            "issue_urgency": item["target_issue_urgency"],
            "safety_concern": item["target_safety_concern"],
            "business_impact": item["target_business_impact"],
        }
        user_prompt = build_user_prompt(domain, style, issue_hint, length_hint, target_labels)

        result = generate_complaint(
            tokenizer, model, user_prompt,
            expected_labels=target_labels,
            recent_texts=(list(recent_texts) if enforce_diversity else None),
            enforce_diversity=enforce_diversity,
            max_new_tokens=effective_max_new_tokens,
            retries=effective_retries,
            do_sample=args.do_sample,
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
                "department": result["department"],
                "issue_severity": result["issue_severity"],
                "issue_urgency": result["issue_urgency"],
                "safety_concern": result["safety_concern"],
                "business_impact": result["business_impact"],
            })
            recent_texts.append(result["text"])
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
    print(f"\nDepartment breakdown:")
    print(df.groupby("department").size().sort_values(ascending=False).to_string())
    safety_rows = df[df["issue_hint"].isin(SAFETY_ISSUES)]
    print(f"\nSafety-seeded rows: {len(safety_rows)} ({len(safety_rows)/len(df)*100:.1f}%)")


if __name__ == "__main__":
    main()
