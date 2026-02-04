from .llm import generate_response
from .retriever import retrieve_context

MAX_INQUIRY_ATTEMPTS = 3

def handle_complaint(user_text: str, state: dict) -> str:
    context = retrieve_context(user_text, mode="complaint")

    prompt = (
        "You are a calm customer support assistant.\n"
        "Acknowledge the user's frustration.\n"
        "Do NOT solve the issue.\n"
        "Guide them toward creating a complaint ticket.\n"
    )

    if context:
        prompt += f"\nRelevant company guidelines:\n{context}\n"

    prompt += f"\nUser: {user_text}\nAssistant:"

    return generate_response(prompt)


def handle_inquiry(user_text: str, state: dict) -> str:
    state["attempts"] += 1

    if state["attempts"] > MAX_INQUIRY_ATTEMPTS:
        return (
            "I’m not confident I can resolve this here. "
            "Let’s create a support ticket so the team can help you properly."
        )

    context = retrieve_context(user_text, mode="inquiry")

    prompt = (
        "You are a customer support assistant.\n"
        "Answer the user's inquiry clearly and briefly.\n"
    )

    if context:
        prompt += f"\nRelevant company information:\n{context}\n"

    prompt += f"\nUser: {user_text}\nAssistant:"

    return generate_response(prompt)
