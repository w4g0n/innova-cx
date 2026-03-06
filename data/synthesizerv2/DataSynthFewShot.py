import pandas as pd
import requests
import json
from tqdm import tqdm

INPUT_FILE  = "Synth_DataSet_Preprocessed.csv"
OUTPUT_FILE = "Synth_DataSet_Labeled_Final.csv"
TEXT_COLUMN = "transcript"
OLLAMA_URL  = "http://localhost:11434/api/generate"
MODEL       = "gemma:2b"

# ── PROMPT ────────────────────────────────────────────────────────────────────
SYSTEM_PROMPT = """Classify the tenant complaint. Reply with JSON only: {"business_impact": "high"|"medium"|"low", "safety_concern": true|false}

Examples:
T: "We are facing security incident near the loading bay." -> {"business_impact": "high", "safety_concern": true}
T: "We are facing power outage in common area." -> {"business_impact": "high", "safety_concern": true}
T: "We are facing parking gate malfunction." -> {"business_impact": "medium", "safety_concern": false}
T: "We are facing air conditioning not working properly." -> {"business_impact": "medium", "safety_concern": false}
T: "We are facing water leakage in the unit." -> {"business_impact": "low", "safety_concern": false}
T: "We are facing cleaning services not done as scheduled." -> {"business_impact": "low", "safety_concern": false}
T: "We are facing noise disturbance from nearby unit." -> {"business_impact": "low", "safety_concern": false}
T: "We are facing lost item reported at reception." -> {"business_impact": "low", "safety_concern": false}
T: "We are facing access card stopped working." -> {"business_impact": "low", "safety_concern": false}

T: """

# ── HELPERS ───────────────────────────────────────────────────────────────────

def extract_json(text: str) -> str | None:
    """Extract the first {...} block, stripping markdown fences if present."""
    text = text.replace("```json", "").replace("```", "")
    try:
        start = text.index("{")
        end   = text.rindex("}") + 1
        return text[start:end]
    except ValueError:
        return None


def label_complaint(text: str) -> dict:
    prompt = SYSTEM_PROMPT + '"' + str(text).strip() + '" ->'

    response = requests.post(
        OLLAMA_URL,
        json={
            "model":  MODEL,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature":    0,
                "num_predict":    60,
                "top_k":          1,
                "repeat_penalty": 1.0,
            },
        },
        timeout=60,
    )
    response.raise_for_status()

    raw_output = response.json()["response"].strip()
    json_text  = extract_json(raw_output)

    if json_text is None:
        raise ValueError(f"No JSON found in output: {repr(raw_output)}")

    parsed = json.loads(json_text)

    impact = str(parsed.get("business_impact", "")).lower().strip()
    safety = parsed.get("safety_concern", False)

    if impact not in {"high", "medium", "low"}:
        raise ValueError(f"Unexpected business_impact value: {impact!r}")

    return {
        "business_impact": impact,
        "safety_concern":  bool(safety),
    }


# ── MAIN ──────────────────────────────────────────────────────────────────────

df = pd.read_csv(INPUT_FILE)
df_complaints = df[df["call_category"] == "complaint"].copy()
df_inquiries  = df[df["call_category"] == "inquiry"].copy()

print(f"Complaints : {len(df_complaints)}")
print(f"Inquiries  : {len(df_inquiries)}")

impacts, safety_flags = [], []

for text in tqdm(df_complaints[TEXT_COLUMN], desc="Labeling"):
    try:
        result = label_complaint(text)
        impacts.append(result["business_impact"])
        safety_flags.append(result["safety_concern"])
    except Exception as e:
        print(f"  Error: {e}")
        impacts.append(None)
        safety_flags.append(None)

df_complaints = df_complaints.copy()
df_complaints["business_impact"] = impacts
df_complaints["safety_concern"]  = safety_flags

df_inquiries = df_inquiries.copy()
df_inquiries["business_impact"] = None
df_inquiries["safety_concern"]  = None

df_final = pd.concat([df_complaints, df_inquiries]).reset_index(drop=True)

print("\nBusiness Impact Distribution:")
print(df_final["business_impact"].value_counts(dropna=False))

print("\nSafety Distribution:")
print(df_final["safety_concern"].value_counts(dropna=False))

df_final.to_csv(OUTPUT_FILE, index=False)
print(f"\nSaved to {OUTPUT_FILE}")