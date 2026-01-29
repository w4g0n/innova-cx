import requests
import os

HF_TOKEN = os.getenv("HF_TOKEN")
if not HF_TOKEN:
    raise RuntimeError("HF_TOKEN environment variable not set")

API_URL = "https://router.huggingface.co/models/tiiuae/falcon-7b-instruct"

HEADERS = {
    "Authorization": f"Bearer {HF_TOKEN}",
    "Accept": "application/json",
    "Content-Type": "application/json",
}

payload = {
    "inputs": "You are a customer support assistant. Say hello briefly.",
    "parameters": {
        "max_new_tokens": 50,
        "temperature": 0.3,
    }
}

response = requests.post(API_URL, headers=HEADERS, json=payload)

print("STATUS:", response.status_code)
print("RAW RESPONSE:")
print(response.text)