TENANT_URGENCY_BONUS = {
    "prospective": -0.05,
    "standard": 0.0,
    "premium": 0.1,
    "vip": 0.2
}

TICKET_TYPE_BONUS = {
    "complaint": 0.0,
    "inquiry": -0.2
}

def compute_urgency(
    text_urgency,
    tenant_tier,
    ticket_type,
    is_recurring,
    safety_concern
):
    # Base urgency from language
    urgency = text_urgency * 0.5

    # Safety always increases urgency
    if safety_concern:
        urgency += 0.4
    # Recurring issues increase pressure
    elif is_recurring:
        urgency += 0.2

    # Tenant expectations
    urgency += TENANT_URGENCY_BONUS[tenant_tier]

    # Inquiries are less urgent by default
    urgency += TICKET_TYPE_BONUS[ticket_type]

    # Clamp to [0, 1]
    urgency_score = max(0.0, min(1.0, urgency))
    return urgency_score