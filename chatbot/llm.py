from transformers import pipeline

print("Loading local LLM... this may take a moment.")

# TEMPORARY local model (free, CPU-friendly)
_model = pipeline(
    "text-generation",
    model="gpt2",
)

print("LLM loaded.")

def generate_response(prompt: str) -> str:
    """
    Single abstraction point for text generation.
    Falcon will replace this implementation later.
    """
    response = _model(
        prompt,
        max_new_tokens=30,
        do_sample=False,
    )
    return response[0]["generated_text"]