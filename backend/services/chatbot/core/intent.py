import re

from .llm import generate_response, llm_available


# Parsing helpers

def _extract_label(text: str, valid: set[str]) -> str:
    cleaned = text.strip().lower()
    if cleaned in valid:
        return cleaned
    for token in cleaned.split():
        token = token.strip(".:->\"',()")
        if token in valid:
            return token
    return "unknown"


def _extract_aggression(text: str) -> tuple[bool, float]:
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


# Keyword-based classifiers (fast, no LLM needed)

_FOLLOW_UP_SIGNALS = [
    "follow up", "follow-up", "followup", "existing ticket", "ticket status",
    "update on", "update of", "update about", "update for",
    "status of", "my ticket", "track", "check on", "check the",
    "ticket id", "cx-", "where is my", "any update", "progress on",
    "what happened", "resolution", "been waiting", "still open",
    "not resolved", "check status", "look up", "lookup",
    "previous ticket", "previous complaint", "previous inquiry",
    "earlier ticket", "earlier complaint", "old ticket",
    "submitted earlier", "submitted before", "raised earlier",
    "my complaint", "my inquiry", "my request", "my issue",
    "pending ticket", "open ticket", "last ticket",
]

_CREATE_SIGNALS = [
    "new ticket", "new complaint", "new inquiry",
    "create a", "create ticket", "submit a", "submit ticket",
    "report a", "report problem", "log a", "raise a", "file a",
    "make a complaint", "make a ticket", "make a report",
    "i have a problem", "i have an issue",
    "i want to complain", "i want to report", "i want to create",
    "i want to submit", "i want to raise", "i want to file",
    "broken", "fault", "not working",
    "need help with", "damaged",
    "leaking", "out of order", "malfunction", "defective",
    "down", "outage", "failed",
    "how do i", "how can i", "can you help",
    "question about", "inquiry about", "ask about",
]

_INQUIRY_SIGNALS = [
    "question", "inquiry", "how do i", "how can i", "what is",
    "where is", "when is", "can you tell", "information",
    "help me understand", "guidance", "advice", "explain",
    "opening hours", "policy", "procedure", "process",
    "schedule", "available", "who do i contact",
]

_COMPLAINT_SIGNALS = [
    "complaint", "broken", "fault", "not working", "damaged",
    "leaking", "out of order", "malfunction", "defective",
    "outage", "failed", "problem", "issue with", "frustrated",
    "unacceptable", "terrible", "worst", "disgusting",
    "reporting", "fire", "flood", "mold", "pest",
    "safety", "hazard", "dangerous", "ac", "air conditioning",
    "elevator", "lift", "plumbing", "electrical", "parking",
    "wifi", "wi-fi", "network", "printer", "cctv", "window",
    "door", "lock", "alarm", "cleaning", "restroom",
    "toxic", "explod", "smoke", "fumes", "smell", "spill",
    "overflow", "crack", "burst", "collapse", "stuck", "blocked",
    "noise", "loud", "broken into", "vandal", "graffiti", "flood",
]

_AGGRESSION_WORDS = {
    "fuck", "shit", "damn", "hell", "ass", "idiot", "stupid",
    "incompetent", "useless", "pathetic", "ridiculous",
    "unacceptable", "disgusting", "horrible", "terrible",
    "worst", "garbage", "trash", "sue", "lawyer", "legal",
    "threatening", "kill", "die", "hate",
    "furious", "outrageous", "irate", "appalling", "atrocious",
    "infuriating", "fuming", "livid", "enraged", "outraged",
}

_THREAT_PHRASES = [
    "i will sue", "i'll sue", "get a lawyer", "take legal",
    "go to the press", "go to media", "report you",
    "escalate to", "speak to your manager", "your supervisor",
    "fire you", "get you fired",
    "want a human", "speak to a human", "talk to a human",
    "real person", "actual person", "human agent", "human now",
]


def _keyword_score(text: str, signals: list[str]) -> int:
    text_lower = text.strip().lower()
    return sum(1 for s in signals if s in text_lower)


def _keyword_primary_intent(user_text: str) -> str:
    follow_score = _keyword_score(user_text, _FOLLOW_UP_SIGNALS)
    create_score = _keyword_score(user_text, _CREATE_SIGNALS)

    # Check for ticket ID patterns — strong follow_up signal
    if re.search(r"\bCX-[A-Z0-9-]+\b", user_text, re.IGNORECASE):
        follow_score += 3
    if re.search(r"\b[0-9a-f]{8}-[0-9a-f]{4}-", user_text, re.IGNORECASE):
        follow_score += 3

    if follow_score > create_score:
        return "follow_up"
    if create_score > follow_score:
        return "create_ticket"
    if follow_score > 0:
        return "follow_up"
    return "unknown"


def _keyword_secondary_intent(user_text: str) -> str:
    inquiry_score = _keyword_score(user_text, _INQUIRY_SIGNALS)
    complaint_score = _keyword_score(user_text, _COMPLAINT_SIGNALS)

    if complaint_score > inquiry_score:
        return "complaint"
    if inquiry_score > complaint_score:
        return "inquiry"
    if complaint_score > 0:
        return "complaint"
    return "unknown"


def _keyword_aggression(user_text: str) -> tuple[bool, float]:
    text_lower = user_text.strip().lower()
    words = set(re.findall(r"\b\w+\b", text_lower))

    aggression_hits = len(words & _AGGRESSION_WORDS)
    threat_hits = sum(1 for p in _THREAT_PHRASES if p in text_lower)

    # Caps ratio (shouting)
    alpha_chars = [c for c in user_text if c.isalpha()]
    caps_ratio = sum(1 for c in alpha_chars if c.isupper()) / max(len(alpha_chars), 1)

    # Exclamation density
    excl_count = user_text.count("!")

    score = 0.0
    score += min(aggression_hits * 0.25, 0.5)
    score += min(threat_hits * 0.35, 0.5)
    if caps_ratio > 0.6 and len(alpha_chars) > 10:
        score += 0.2
    score += min(excl_count * 0.05, 0.15)
    score = min(score, 1.0)

    return (score >= 0.75), round(score, 4)


# LLM-based classifiers (used when LLM is available)

def _llm_classify_primary(user_text: str, history: list) -> str:
    system = (
        "You are an intent classifier for a support ticketing system.\n"
        "Output a single label only. No explanation.\n\n"
        "Valid labels: follow_up, create_ticket, unknown\n\n"
        "Rules:\n"
        "  follow_up: user mentions existing ticket, ticket ID, status, or wants update.\n"
        "  create_ticket: user describes problem, fault, question, or wants to raise a ticket.\n"
        "  unknown: no clear intent.\n\n"
        "Examples:\n"
        "  User: What is the status of my ticket → Label: follow_up\n"
        "  User: My laptop will not connect → Label: create_ticket\n"
        "  User: Hello → Label: unknown\n\n"
        "Now classify:"
    )
    messages = [
        {"role": "system", "content": system},
        *history[-4:],
        {"role": "user", "content": user_text},
        {"role": "assistant", "content": "Label:"},
    ]
    output = generate_response(messages, max_new_tokens=5, do_sample=False)
    return _extract_label(output, {"follow_up", "create_ticket", "unknown"})


def _llm_classify_secondary(user_text: str, history: list) -> str:
    system = (
        "You are an intent classifier for a support ticketing system.\n"
        "Output a single label only. No explanation.\n\n"
        "Valid labels: inquiry, complaint, unknown\n\n"
        "Rules:\n"
        "  inquiry: user asking a question, requesting information.\n"
        "  complaint: user reporting a fault, breakage, failure, or dissatisfaction.\n"
        "  unknown: genuinely impossible to determine.\n\n"
        "Examples:\n"
        "  User: How do I reset my access card → Label: inquiry\n"
        "  User: The AC has been broken for two weeks → Label: complaint\n"
        "  User: I am not sure → Label: unknown\n\n"
        "Now classify:"
    )
    messages = [
        {"role": "system", "content": system},
        *history[-4:],
        {"role": "user", "content": user_text},
        {"role": "assistant", "content": "Label:"},
    ]
    output = generate_response(messages, max_new_tokens=5, do_sample=False)
    return _extract_label(output, {"inquiry", "complaint", "unknown"})


def _llm_detect_aggression(user_text: str, history: list) -> tuple[bool, float]:
    system = (
        "You are a tone classifier. Output YES/NO and a score 0.0-1.0.\n"
        "YES = aggressive/hostile/threatening. NO = calm/neutral.\n\n"
        "Examples:\n"
        "  User: Fix it NOW → Output: YES 0.93\n"
        "  User: Can you help please → Output: NO 0.04\n\n"
        "Now classify:"
    )
    messages = [
        {"role": "system", "content": system},
        *history[-2:],
        {"role": "user", "content": user_text},
        {"role": "assistant", "content": "Output:"},
    ]
    raw = generate_response(messages, max_new_tokens=8, do_sample=False)
    return _extract_aggression(raw)


# Public API (auto-selects keyword or LLM)

# Short greetings that must never reach the LLM.  Qwen 0.5B misclassifies
# them as follow_up; intercept here and return "unknown" so the controller
# asks the user to state their actual intent.
_GREETING_WORDS = {
    "hello", "hi", "hey", "greetings", "howdy", "hiya", "yo", "sup",
    "good morning", "good afternoon", "good evening", "good day",
}


def _is_greeting(user_text: str) -> bool:
    normalized = user_text.strip().lower().rstrip("!.,?")
    if normalized in _GREETING_WORDS:
        return True
    first_word = normalized.split()[0] if normalized.split() else ""
    return first_word in _GREETING_WORDS


def classify_primary_intent(user_text: str, history: list) -> str:
    """
    Classifies whether the user wants to follow up or create a ticket.
    Uses fast keyword matching first; falls back to LLM if keywords are ambiguous.
    """
    result = _keyword_primary_intent(user_text)
    if result != "unknown":
        return result
    # Greetings must not reach the LLM — the small model misclassifies them.
    if _is_greeting(user_text):
        return "unknown"
    # Keywords inconclusive — try LLM if available
    if llm_available():
        return _llm_classify_primary(user_text, history)
    return "unknown"


def classify_secondary_intent(user_text: str, history: list) -> str:
    """
    Classifies whether the user's issue is an inquiry or a complaint.
    Uses fast keyword matching first; falls back to LLM if keywords are ambiguous.
    """
    result = _keyword_secondary_intent(user_text)
    if result != "unknown":
        return result
    if llm_available():
        return _llm_classify_secondary(user_text, history)
    return "unknown"


def detect_aggression(user_text: str, history: list) -> tuple[bool, float]:
    """
    Detects aggressive/hostile tone. Keyword-based first, LLM fallback.
    Returns: (is_aggressive: bool, confidence_score: float 0.0–1.0)
    """
    is_agg, score = _keyword_aggression(user_text)
    # If keyword score is in the grey zone (0.3-0.7), consult LLM for better accuracy
    if 0.3 <= score <= 0.7 and llm_available():
        return _llm_detect_aggression(user_text, history)
    return is_agg, score


_HUMAN_ESCALATION_PHRASES = [
    "want a human", "need a human", "speak to a human", "talk to a human",
    "speak with a human", "talk with a human", "want to speak to a human",
    "want to talk to a human", "real person", "actual person", "live agent",
    "human agent", "human support", "human now", "speak to someone",
    "talk to someone", "speak to an agent", "talk to an agent",
    "speak to a person", "talk to a person", "connect me to a human",
    "transfer me", "escalate this", "want to escalate",
]


def is_human_escalation_request(user_text: str) -> bool:
    """
    Detects explicit requests to speak with a human agent.
    Always runs regardless of state — never subject to aggression threshold.
    """
    text_lower = user_text.strip().lower()
    return any(phrase in text_lower for phrase in _HUMAN_ESCALATION_PHRASES)


_CANCELLATION_PHRASES = [
    "changed my mind", "change my mind", "never mind", "nevermind",
    "forget it", "forget about it", "forget this", "cancel",
    "start over", "start again", "restart", "reset",
    "actually no", "actually never mind", "don't want to", "dont want to",
    "don't bother", "dont bother", "no thanks", "not anymore",
    "stop", "quit", "exit", "go back", "nvm",
]


def is_cancellation_request(user_text: str) -> bool:
    """
    Detects when the user wants to cancel the current flow and start fresh.
    Only meaningful when the user is mid-flow (collecting fields, etc.).
    """
    text_lower = user_text.strip().lower()
    return any(phrase in text_lower for phrase in _CANCELLATION_PHRASES)
