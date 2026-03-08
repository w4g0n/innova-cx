import re
from .intent import classify_primary_intent, classify_secondary_intent, detect_aggression
from .llm import generate_response
from .logger import log_bot_response, log_user_message
from .retriever import retrieve_context
from .session import append_history, load_session, save_session, transition
from .sql_agent import get_open_tickets, get_ticket_status, resolve_ticket_id_from_hint
from .ticket import create_ticket

MAX_INQUIRY_ATTEMPTS = 3
URGENCY_HINTS = (
    "urgent", "urgently", "asap", "immediately", "right now",
    "emergency", "critical", "priority", "today", "now",
)
_GENERIC_INQUIRY_INPUTS = {
    "inquiry", "question", "help", "support",
    "create ticket", "creating a ticket", "create a ticket",
    "complaint", "follow up", "follow-up", "followup",
}


# ── Main entry point ──────────────────────────────────────────────────────────

def handle_message(session_id: str, user_id: str, user_text: str) -> dict:
    session = load_session(session_id)
    state   = session["current_state"]
    history = session["history"]

    is_init = user_text == "__init__"

    # ── Aggression check (skip on init and early states where false positives are high) ──
    is_aggressive, agg_score = False, 0.0
    if not is_init and state not in ("greeting", "await_primary_intent"):
        is_aggressive, agg_score = detect_aggression(user_text, history)

    # ── Log and append user message ───────────────────────────────────────────
    if not is_init:
        log_user_message(
            session_id=session_id,
            user_id=user_id,
            message=user_text,
            aggression_flag=is_aggressive,
            aggression_score=agg_score,
        )
        append_history(session, "user", user_text)

    # ── Escalation ────────────────────────────────────────────────────────────
    if is_aggressive:
        response = (
            "I completely understand your frustration and I sincerely apologise "
            "for the inconvenience. Would you like me to immediately create a ticket "
            "or track an existing one for you? You can also continue chatting if you prefer."
        )
        # Do not transition state — user may choose to keep chatting
        _log_and_save(session, response, "escalation")
        return _result(response, "escalation", session_id,
                       buttons=["create_ticket", "track_ticket"])

    # ── State machine ─────────────────────────────────────────────────────────

    # GREETING
    if state == "greeting":
        if not is_init:
            # Real message arrived while state was greeting.
            # Transition and continue in the same call to avoid duplicate user logging.
            transition(session, "await_primary_intent")
            state = "await_primary_intent"

        else:
            response = (
                "Hi! I'm Nova, your AI support assistant. How can I help you today?\n\n"
                "You can:\n"
                "  1. Follow up on an existing ticket\n"
                "  2. Create a new ticket (complaint or inquiry)\n\n"
                "Just describe what you need and I'll take it from there."
            )
            transition(session, "await_primary_intent")
            _log_and_save(session, response, "greeting")
            return _result(response, "greeting", session_id)

    # AWAIT PRIMARY INTENT
    if state == "await_primary_intent":
        intent = classify_primary_intent(user_text, history)

        if intent == "follow_up":
            transition(session, "await_ticket_id")
            response = (
                "Sure, I can help with that. Could you please provide your ticket ID? "
                "If you do not have it, just say so and I will look up your open tickets."
            )
            _log_and_save(session, response, "prompt_ticket_id")
            return _result(response, "prompt_ticket_id", session_id)

        if intent == "create_ticket":
            transition(session, "await_secondary_intent")
            response = (
                "Of course. To help you better, is this an inquiry (you have a question) "
                "or a complaint (you are reporting a problem or fault)?"
            )
            _log_and_save(session, response, "prompt_ticket_type")
            return _result(response, "prompt_ticket_type", session_id)

        # unknown — re-prompt without changing state
        response = (
            "I did not quite catch that. Are you looking to follow up on an existing "
            "ticket, or would you like to create a new one?"
        )
        _log_and_save(session, response, "clarify")
        return _result(response, "clarify", session_id)

    # AWAIT TICKET ID
    if state == "await_ticket_id":
        tid = _extract_ticket_id(user_text)
        if not tid:
            hint_result = resolve_ticket_id_from_hint(user_text, user_id)
            if hint_result.get("found"):
                tid = hint_result.get("ticket_id")
        if not tid and _looks_urgent(user_text):
            last_tid = session["context"].get("last_ticket_id")
            if last_tid:
                tid = last_tid

        if tid:
            result   = get_ticket_status(tid, user_id)
            response = (
                result.get("raw", "I could not retrieve that ticket. Please check the ID and try again.")
                if result.get("found")
                else "I could not retrieve that ticket. Please check the ID and try again."
            )
            if result.get("ticket_found"):
                session["context"]["last_ticket_id"] = result.get("ticket_code") or tid
            transition(session, "resolved")
            _log_and_save(session, response, "ticket_status",
                          sql_query=result.get("query"))
        else:
            # No ID in message — list open tickets and stay in this state
            # so the user can reply with the ID they want
            result = get_open_tickets(user_id)
            if result.get("found") and result.get("raw"):
                response = (
                    "No problem. Here are your open tickets:\n\n"
                    + result["raw"]
                    + "\n\nPlease reply with the ticket ID you would like to follow up on "
                    + "(for example, CX-123456). You can also paste part of the ticket subject."
                )
                # Stay in await_ticket_id — do not transition
                _log_and_save(session, response, "open_tickets_list",
                              sql_query=result.get("query"))
            else:
                response = "I could not find any open tickets for your account."
                transition(session, "resolved")
                _log_and_save(session, response, "no_open_tickets")

        return _result(response, "ticket_lookup", session_id)

    # AWAIT SECONDARY INTENT (inquiry vs complaint)
    if state == "await_secondary_intent":
        intent = classify_secondary_intent(user_text, history)

        if intent == "inquiry":
            transition(session, "inquiry")
            return _handle_inquiry(session, user_text)

        if intent == "complaint":
            transition(session, "complaint")
            return _handle_complaint(session, user_id, user_text)

        response = (
            "Could you clarify — is this a question you need answered, "
            "or are you reporting a problem or fault?"
        )
        _log_and_save(session, response, "clarify")
        return _result(response, "clarify", session_id)

    # INQUIRY
    if state == "inquiry":
        return _handle_inquiry(session, user_text)

    # INQUIRY CONFIRM — waiting for yes/no after an answer was given
    if state == "inquiry_confirm":
        return _handle_inquiry_confirm(session, user_id, user_text)

    # COMPLAINT
    if state == "complaint":
        return _handle_complaint(session, user_id, user_text)

    # TICKET FIELD COLLECTION
    if state in ("collecting_inquiry_ticket", "collecting_complaint"):
        return _collect_ticket_fields(session, user_id, user_text)

    # POST TICKET CREATED / RESOLVED:
    # User sent a new message after closure. Re-enter primary intent handling
    # in the same turn so we do not discard their latest message.
    if state in ("ticket_created", "resolved"):
        transition(session, "await_primary_intent")
        if _looks_urgent(user_text):
            last_tid = session["context"].get("last_ticket_id")
            if last_tid:
                response = (
                    f"I understand this is urgent. I can keep tracking ticket {last_tid} with you. "
                    "Please share the immediate impact (for example, safety risk or service downtime), "
                    "and I will help you log an urgent complaint update."
                )
                _log_and_save(session, response, "urgency_follow_up")
                return _result(response, "urgency_follow_up", session_id)

        intent = classify_primary_intent(user_text, history)

        if intent == "follow_up":
            transition(session, "await_ticket_id")
            response = (
                "Sure, I can help with that. Could you please provide your ticket ID? "
                "If you do not have it, just say so and I will look up your open tickets."
            )
            _log_and_save(session, response, "prompt_ticket_id")
            return _result(response, "prompt_ticket_id", session_id)

        if intent == "create_ticket":
            transition(session, "await_secondary_intent")
            response = (
                "Of course. To help you better, is this an inquiry (you have a question) "
                "or a complaint (you are reporting a problem or fault)?"
            )
            _log_and_save(session, response, "prompt_ticket_type")
            return _result(response, "prompt_ticket_type", session_id)

        response = "Is there anything else I can help you with today?"
        _log_and_save(session, response, "post_resolved_prompt")
        return _result(response, "post_resolved_prompt", session_id)

    # FALLBACK — should never be reached in normal operation
    response = (
        "I am not sure how to help with that. "
        "Would you like to follow up on a ticket or create a new one?"
    )
    transition(session, "await_primary_intent")
    _log_and_save(session, response, "fallback")
    return _result(response, "fallback", session_id)


# ── Inquiry handler ───────────────────────────────────────────────────────────

def _handle_inquiry(session: dict, user_text: str) -> dict:
    session_id = session["session_id"]
    context    = session["context"]

    attempts = context.get("inquiry_attempts", 0) + 1
    context["inquiry_attempts"] = attempts

    if attempts > MAX_INQUIRY_ATTEMPTS:
        response = (
            "I have not been able to resolve this for you through chat. "
            "Let me create a support ticket so the team can follow up. "
            "What type of asset does this relate to — Office, Warehouse, or Retail?"
        )
        context["category"] = "inquiry"
        transition(session, "collecting_inquiry_ticket")
        _log_and_save(session, response, "inquiry_escalate_to_ticket")
        return _result(response, "inquiry_escalate_to_ticket", session_id)

    kb_context = retrieve_context(user_text, mode="inquiry")

    if kb_context:
        system = (
            "You are a helpful support assistant. "
            "Answer the user question using the provided context. "
            "Be concise and clear.\n\nContext:\n" + kb_context
        )
        messages = [
            {"role": "system", "content": system},
            *session["history"][-4:],
            {"role": "user", "content": user_text},
        ]
        response = generate_response(messages)
        rtype    = "inquiry_kb_answer"
    else:
        system = (
            "You are a support assistant. "
            "Answer if you can, but be honest about uncertainty. "
            "If you do not know, say so clearly and do not guess."
        )
        messages = [
            {"role": "system", "content": system},
            *session["history"][-4:],
            {"role": "user", "content": user_text},
        ]
        response = generate_response(messages)
        rtype    = "inquiry_falcon_fallback"
        response = "[Not fully certain] " + response

    # Do not force binary follow-up prompts; allow natural conversation.
    transition(session, "await_primary_intent")
    _log_and_save(session, response, rtype)
    return _result(response, rtype, session_id)


def _handle_inquiry_confirm(session: dict, user_id: str, user_text: str) -> dict:
    """
    Handles the user's yes/no response after an inquiry answer was given.
      Yes → resolved, offer further help.
      No  → return to inquiry state and try again (or escalate if attempts exhausted).
    """
    session_id  = session["session_id"]
    text_clean  = user_text.strip()
    text_lower  = text_clean.lower()
    # Treat as explicit confirmation only when the whole message is essentially
    # yes/no feedback. If user includes details after "yeah"/"no", continue handling
    # it as a substantive inquiry message.
    positive_only = bool(
        re.fullmatch(
            r"\s*(yes|yeah|yep|yup|correct|perfect|great|thanks|thank you|solved|sorted|resolved)[\s!.,-]*",
            text_lower,
        )
    )
    negative_only = bool(
        re.fullmatch(
            r"\s*(no|nope|nah|not really|not exactly|not quite)[\s!.,-]*",
            text_lower,
        )
    )
    is_positive = positive_only and not negative_only

    if is_positive:
        response = "Great, glad I could help! Is there anything else I can assist you with?"
        transition(session, "await_primary_intent")
        _log_and_save(session, response, "inquiry_resolved")
        return _result(response, "inquiry_resolved", session_id)

    # Not resolved — if user included new detail, use it; otherwise recover last question.
    clarification = re.sub(
        r"^\s*(no|nope|nah|not really|not exactly|not quite)\b[\s,.:;-]*",
        "",
        text_clean,
        flags=re.IGNORECASE,
    ).strip()
    next_question = clarification if len(clarification) >= 4 else _recover_original_question(session["history"])
    if _is_generic_inquiry_input(next_question):
        next_question = ""
    if not next_question:
        response = (
            "Thanks for clarifying. Please tell me the exact information you need "
            "(for example pricing, availability, lease terms, or move-in timeline)."
        )
        transition(session, "inquiry")
        _log_and_save(session, response, "clarify")
        return _result(response, "clarify", session_id)

    transition(session, "inquiry")
    return _handle_inquiry(session, next_question)


def _recover_original_question(history: list) -> str:
    """
    Walk backwards through history to find the last substantive user message
    that is not a yes/no confirmation reply.
    """
    noise = {"yes", "no", "yeah", "nope", "yep", "yup", "nah",
             "correct", "thanks", "thank you", "ok", "okay"} | _GENERIC_INQUIRY_INPUTS
    for entry in reversed(history):
        if entry.get("role") == "user":
            content = entry.get("content", "").strip().lower()
            if content not in noise and len(content) > 4:
                return entry["content"]
    return ""


def _is_generic_inquiry_input(text: str) -> bool:
    t = (text or "").strip().lower()
    return not t or t in _GENERIC_INQUIRY_INPUTS


# ── Complaint handler ─────────────────────────────────────────────────────────

def _handle_complaint(session: dict, user_id: str, user_text: str) -> dict:
    session_id = session["session_id"]
    context    = session["context"]

    if not context.get("deescalated", False):
        # De-escalation turn — acknowledge, do not solve, ask for issue details
        kb_context = retrieve_context(user_text, mode="complaint")
        system = (
            "You are a calm, empathetic customer support assistant. "
            "Acknowledge the user's frustration with genuine empathy. "
            "Do NOT attempt to solve the issue. "
            "Reassure them it will be addressed and encourage them to share more detail."
        )
        if kb_context:
            system += f"\n\nGuidelines:\n{kb_context}"

        messages = [
            {"role": "system", "content": system},
            *session["history"][-4:],
            {"role": "user", "content": user_text},
        ]
        response  = generate_response(messages)
        response += "\n\nTo raise this as a complaint ticket, please describe the issue in as much detail as you can."
        context["deescalated"] = True
        context["category"]    = "complaint"
        transition(session, "collecting_complaint")
        _log_and_save(session, response, "complaint_deescalate")
        return _result(response, "complaint_deescalate", session_id)

    # de-escalation already done — move to field collection
    return _collect_ticket_fields(session, user_id, user_text)


# ── Ticket field collection ───────────────────────────────────────────────────

def _collect_ticket_fields(session: dict, user_id: str, user_text: str) -> dict:
    session_id = session["session_id"]
    context    = session["context"]
    category   = context.get("category", "complaint")

    # Step 1: collect description
    if "description" not in context:
        if not user_text.strip():
            response = "Could you describe the issue in a bit more detail please?"
            _log_and_save(session, response, "prompt_description_retry")
            return _result(response, "prompt_description_retry", session_id)
        context["description"] = user_text.strip()

    # Step 3: create ticket
    result = create_ticket(
        user_id=user_id,
        session_id=session_id,
        category=category,
        description=context["description"],
    )

    if result["success"]:
        response = (
            f"Your ticket has been created successfully. "
            f"Your ticket ID is {result['ticket_id']}. "
            "A member of the team will be in touch shortly."
        )
        transition(session, "ticket_created")
        rtype = "ticket_created"
    else:
        response = (
            f"I encountered an issue creating your ticket: {result['error']}. "
            "Please try again."
        )
        rtype = "ticket_create_error"

    _log_and_save(session, response, rtype)
    return _result(response, rtype, session_id)


# ── Utility helpers ───────────────────────────────────────────────────────────

def _extract_ticket_id(text: str) -> str | None:
    uuid_match = re.search(
        r"\b[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}\b",
        text.lower(),
    )
    if uuid_match:
        return uuid_match.group(0)
    code_match = re.search(r"\b(CX-[A-Z0-9-]{4,32}|[A-Z]{0,3}\d{3,8})\b", text.upper())
    return code_match.group(1) if code_match else None


def _looks_urgent(text: str) -> bool:
    t = (text or "").strip().lower()
    if not t:
        return False
    return any(h in t for h in URGENCY_HINTS)


def _log_and_save(
    session: dict,
    response: str,
    rtype: str,
    kb_score: float = None,
    sql_query: str = None,
) -> None:
    append_history(session, "assistant", response)
    log_bot_response(
        session_id=session["session_id"],
        response=response,
        response_type=rtype,
        state_at_time=session["current_state"],
        sql_query=sql_query,
        kb_score=kb_score,
    )
    save_session(session)


def _result(
    response: str,
    rtype: str,
    session_id: str,
    buttons: list | None = None,
) -> dict:
    return {
        "response":      response,
        "response_type": rtype,
        "show_buttons":  buttons or [],
        "session_id":    session_id,
    }

# ── Backward-compatible wrappers (used by local_model_test.py) ────────────────

def handle_inquiry(user_text: str, state: dict | None = None) -> str:
    del state
    context       = retrieve_context(user_text, mode="inquiry")
    system_prompt = (
        "You are a customer support assistant.\n"
        "Answer the user's inquiry clearly and briefly."
    )
    if context:
        system_prompt += f"\n\nRelevant company information:\n{context}"
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user",   "content": user_text},
    ]
    return generate_response(messages)


def handle_complaint(user_text: str, state: dict | None = None) -> str:
    del state
    context       = retrieve_context(user_text, mode="complaint")
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
        {"role": "user",   "content": user_text},
    ]
    return generate_response(messages)
