import pandas as pd
import requests
import json
from tqdm import tqdm

INPUT_FILE = "Synth_DataSet_Preprocessed.csv"
OUTPUT_FILE = "Synth_DataSet_Labeled_Final.csv"

TEXT_COLUMN = "transcript"

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "gemma:2b"

SYSTEM_PROMPT = """
You are classifying tenant complaint transcripts for an industrial property management system.

Based strictly on the operational situation described, assign:

1) business_impact

- "high" → serious issue that meaningfully disrupts business operations, is unresolved, recurring, urgent, security-related with operational disruption, or significantly affects daily work.
- "medium" → issue affects operations but disruption is limited or manageable.
- "low" → minor inconvenience, routine maintenance issue, or no significant operational impact.

2) safety_concern

Return true ONLY if there is explicit physical danger such as:
fire, sparks, exposed wiring, gas leak, flooding near electrical systems,
structural collapse risk, injury hazard, electrical shock risk.

Security or access issues alone are NOT safety hazards.

Respond ONLY with valid JSON in this format:

{
  "business_impact": "...",
  "safety_concern": true/false
}
"""

def extract_json(text):
    try:
        start = text.index("{")
        end = text.rindex("}") + 1
        return text[start:end]
    except ValueError:
        return None

def label_complaint(text):
    prompt = SYSTEM_PROMPT + "\n\nComplaint Transcript:\n" + str(text)

    response = requests.post(
        OLLAMA_URL,
        json={
            "model": MODEL,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0,
                "num_predict": 120
            }
        }
    )

    raw_output = response.json()["response"].strip()
    json_text = extract_json(raw_output)

    if json_text is None:
        raise ValueError("No JSON found")

    return json.loads(json_text)

# =============================
# MAIN
# =============================

df = pd.read_csv(INPUT_FILE)

df_complaints = df[df["call_category"] == "complaint"].copy()
df_inquiries = df[df["call_category"] == "inquiry"].copy()

print("Complaints:", len(df_complaints))
print("Inquiries:", len(df_inquiries))

impacts = []
safety_flags = []

for text in tqdm(df_complaints[TEXT_COLUMN]):
    try:
        result = label_complaint(text)
        impacts.append(result["business_impact"])
        safety_flags.append(result["safety_concern"])
    except:
        impacts.append(None)
        safety_flags.append(None)

df_complaints["business_impact"] = impacts
df_complaints["safety_concern"] = safety_flags

df_inquiries["business_impact"] = None
df_inquiries["safety_concern"] = None

df_final = pd.concat([df_complaints, df_inquiries]).reset_index(drop=True)

print("Business Impact Distribution:")
print(df_final["business_impact"].value_counts(dropna=False))

print("Safety Distribution:")
print(df_final["safety_concern"].value_counts(dropna=False))

df_final.to_csv(OUTPUT_FILE, index=False)

print("LLM labeling complete.")