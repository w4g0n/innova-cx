from transformers import pipeline

print("Loading local LLM...")

_model = pipeline(
    "text-generation",
    model="gpt2",
)

print("LLM loaded.")

def generate_response(prompt: str) -> str:
    result = _model(
        prompt,
        max_new_tokens=40,
        do_sample=False,
    )

    full_text = result[0]["generated_text"]
    return full_text[len(prompt):].strip()
