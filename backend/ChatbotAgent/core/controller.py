from .llm import generate_response
from .retriever import retrieve_context

MAX_INQUIRY_ATTEMPTS = 3


def handle_complaint(user_text: str, state: dict | None = None) -> str:
    if state is None:
        state = {"attempts": 0}
    context = retrieve_context(user_text, mode="complaint")

    system_prompt = (
        "You are a calm customer support assistant.\n"
        "Acknowledge the user's frustration.\n"
        "Do NOT solve the issue.\n"
        "Guide them toward creating a complaint ticket."
    )

    if context:
        system_prompt += f"\n\nRelevant company guidelines:\n{context}"

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_text},
    ]

    return generate_response(messages)


def handle_inquiry(user_text: str, state: dict | None = None) -> str:
    if state is None:
        state = {"attempts": 0}

    state["attempts"] += 1

    if state["attempts"] > MAX_INQUIRY_ATTEMPTS:
        return (
            "I'm not confident I can resolve this here. "
            "Let's create a support ticket so the team can help you properly."
        )

    context = retrieve_context(user_text, mode="inquiry")

    system_prompt = (
        "You are a customer support assistant.\n"
        "Answer the user's inquiry clearly and briefly."
    )

    if context:
        system_prompt += f"\n\nRelevant company information:\n{context}"

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_text},
    ]

    return generate_response(messages)
