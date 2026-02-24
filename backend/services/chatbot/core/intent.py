from .llm import generate_response


# ── Parsing helpers ───────────────────────────────────────────────────────────

def _extract_label(text: str, valid: set[str]) -> str:
    """
    Search the model output for any valid label, left-to-right.
    More robust than splitting on the first token — handles cases where
    Falcon prefixes with punctuation, arrows, or whitespace before the label.
    """
    cleaned = text.strip().lower()
    # Direct match first (cheapest)
    if cleaned in valid:
        return cleaned
    # Scan tokens
    for token in cleaned.split():
        token = token.strip(".:->\"',()")
        if token in valid:
            return token
    return "unknown"


def _extract_aggression(text: str) -> tuple[bool, float]:
    """
    Parse aggression classifier output.
    Looks for YES/NO and a float score anywhere in the response.
    """
    import re
    upper = text.strip().upper()
    label = "NO"
    score = 0.0

    if "YES" in upper:
        label = "YES"
    elif "NO" in upper:
        label = "NO"

    match = re.search(r"\b(0\.\d+|1\.0+|0|1)\b", text)
    if match:
        try:
            score = float(match.group(1))
        except ValueError:
            score = 0.0

    return (label == "YES" and score >= 0.75), score


# ── Classifiers ───────────────────────────────────────────────────────────────

def classify_primary_intent(user_text: str, history: list) -> str:
    """
    Classifies whether the user wants to follow up on an existing ticket
    or create a new one.

    Returns: 'follow_up' | 'create_ticket' | 'unknown'
    """
    system = (
        "You are an intent classifier for a support ticketing system.\n"
        "Your only job is to output a single label. Do not explain. Do not repeat the question. "
        "Do not add punctuation or arrows. Output the label only.\n\n"
        "Valid labels:\n"
        "  follow_up\n"
        "  create_ticket\n"
        "  unknown\n\n"
        "Rules:\n"
        "  Use follow_up when the user mentions an existing ticket, ticket ID, ticket status, "
        "or wants an update.\n"
        "  Use create_ticket when the user describes a problem, fault, question, or wants to "
        "raise or submit a ticket.\n"
        "  Use unknown only when the message has no clear intent.\n\n"
        "Examples:\n"
        "  User: What is the status of my ticket\n"
        "  Label: follow_up\n\n"
        "  User: My laptop will not connect to the VPN\n"
        "  Label: create_ticket\n\n"
        "  User: Ticket 482 update please\n"
        "  Label: follow_up\n\n"
        "  User: I need to log a new issue\n"
        "  Label: create_ticket\n\n"
        "  User: Hello\n"
        "  Label: unknown\n\n"
        "Now classify the following."
    )
    messages = [
        {"role": "system", "content": system},
        *history[-4:],
        {"role": "user", "content": user_text},
        # Priming the assistant turn nudges Falcon to continue with the label
        {"role": "assistant", "content": "Label:"},
    ]
    output = generate_response(messages)
    return _extract_label(output, {"follow_up", "create_ticket", "unknown"})


def classify_secondary_intent(user_text: str, history: list) -> str:
    """
    Classifies whether the user's issue is an inquiry or a complaint.

    Returns: 'inquiry' | 'complaint' | 'unknown'
    """
    system = (
        "You are an intent classifier for a support ticketing system.\n"
        "Your only job is to output a single label. Do not explain. Do not repeat the question. "
        "Do not add punctuation or arrows. Output the label only.\n\n"
        "Valid labels:\n"
        "  inquiry\n"
        "  complaint\n"
        "  unknown\n\n"
        "Rules:\n"
        "  Use inquiry when the user is asking a question, requesting information, or needs "
        "guidance — there is no fault or failure being reported.\n"
        "  Use complaint when the user is reporting a fault, breakage, failure, outage, or "
        "expressing dissatisfaction with a service or physical asset.\n"
        "  Use unknown only when genuinely impossible to determine.\n\n"
        "Examples:\n"
        "  User: How do I reset my access card\n"
        "  Label: inquiry\n\n"
        "  User: The air conditioning in the warehouse has been broken for two weeks\n"
        "  Label: complaint\n\n"
        "  User: What are the opening hours for the retail office\n"
        "  Label: inquiry\n\n"
        "  User: There is a leak in the roof\n"
        "  Label: complaint\n\n"
        "  User: I am not sure\n"
        "  Label: unknown\n\n"
        "Now classify the following."
    )
    messages = [
        {"role": "system", "content": system},
        *history[-4:],
        {"role": "user", "content": user_text},
        {"role": "assistant", "content": "Label:"},
    ]
    output = generate_response(messages)
    return _extract_label(output, {"inquiry", "complaint", "unknown"})


def detect_aggression(user_text: str, history: list) -> tuple[bool, float]:
    """
    Detects whether the user message is aggressive, hostile, or extremely impatient.
    Runs as an overlay on every turn.

    Returns: (is_aggressive: bool, confidence_score: float 0.0–1.0)
    Escalation triggers when is_aggressive is True (score >= 0.75 threshold built in).
    """
    system = (
        "You are a tone classifier for a customer support system.\n"
        "Assess whether the user message is aggressive, hostile, threatening, or extremely impatient.\n"
        "Output exactly two items on one line: a label and a confidence score.\n"
        "Label must be YES or NO. Score must be a decimal between 0.0 and 1.0.\n"
        "Do not output anything else. No explanation. No punctuation other than the decimal point.\n\n"
        "Scoring guide:\n"
        "  0.0 to 0.4 — calm, neutral, or mildly frustrated\n"
        "  0.4 to 0.7 — noticeably frustrated or impatient but not aggressive\n"
        "  0.7 to 1.0 — aggressive, threatening, hostile, or abusive\n\n"
        "Examples:\n"
        "  User: This is absolutely ridiculous fix it NOW\n"
        "  Output: YES 0.93\n\n"
        "  User: I have been waiting three weeks this is completely unacceptable\n"
        "  Output: YES 0.82\n\n"
        "  User: I am frustrated but I understand you are trying to help\n"
        "  Output: NO 0.38\n\n"
        "  User: Can you help me please\n"
        "  Output: NO 0.04\n\n"
        "  User: I swear if this is not fixed today I will escalate to your manager\n"
        "  Output: YES 0.78\n\n"
        "Now classify the following."
    )
    messages = [
        {"role": "system", "content": system},
        *history[-2:],
        {"role": "user", "content": user_text},
        {"role": "assistant", "content": "Output:"},
    ]
    raw = generate_response(messages)
    return _extract_aggression(raw)