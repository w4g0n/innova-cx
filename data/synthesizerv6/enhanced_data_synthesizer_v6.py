"""
=============================================================================
ENHANCED DATA SYNTHESIZER V6
=============================================================================

Generates synthetic complaint and inquiry transcripts for the InnovaCX
sentiment analysis and prioritization pipeline.

CHANGES FROM V2:
    - Adds `issue_urgency` column (independent of issue_severity)
    - Breaks all structural correlations:
        * issue_type does NOT determine business_impact or safety_concern
        * issue_severity does NOT determine safety_concern
        * issue_severity does NOT determine business_impact directly
        * issue_urgency is assigned independently from issue_severity
        * asset_type and location do NOT influence any label
        * tenant_tier is assigned independently (not tied to severity)
    - business_impact and safety_concern are determined solely by
      the LANGUAGE embedded in the transcript text (consequence phrases
      and safety phrases), not by template metadata
    - issue_urgency is determined solely by DURATION LANGUAGE embedded
      in the transcript text
    - 60 issue templates (up from 48), balanced across severity buckets
    - Expanded narrative variety: 6 duration levels, 5 consequence tiers,
      explicit safety language injected probabilistically into text
    - All V2 pipeline column names preserved:
        call_id, timestamp, call_category, tenant_tier, asset_type,
        location, issue_type, issue_severity, issue_urgency,
        business_impact, safety_concern, is_recurring, transcript

ANTI-CORRELATION DESIGN:
    The model must learn labels FROM TEXT, not from structural shortcuts.
    To enforce this:
    1. Labels (business_impact, safety_concern, issue_urgency) are chosen
       FIRST as random independent targets.
    2. The transcript is then assembled using language pools that match
       those targets. The issue_type and issue_severity are present as
       context but do NOT gate which label is assigned.
    3. The same issue_type (e.g. "HVAC malfunction") can appear with
       low, medium, or high business_impact across different records.
    4. issue_urgency and issue_severity can diverge intentionally:
       a high-severity issue can be low-urgency (slow-burn, manageable)
       and a low-severity issue can be high-urgency (minor but overdue).

PIPELINE COMPATIBILITY:
    - step1_deduplicate.py  → reads 'transcript' column ✓
    - step2_augment.py      → reads 'transcript', all metadata columns ✓
    - preprocess.py         → reads 'call_category', 'transcript',
                              'tenant_tier', 'asset_type',
                              'business_impact', 'safety_concern' ✓
    - data_preparation.py   → reads 'transcript', 'issue_severity',
                              'business_impact', 'is_recurring',
                              'safety_concern', 'tenant_tier' ✓

USAGE:
    python enhanced_data_synthesizer_v6.py [num_records]
    Default: 2000 records

=============================================================================
"""

import pandas as pd
import random
from datetime import datetime, timedelta

random.seed(42)

# =============================================================================
# BASE CONFIGURATION
# =============================================================================

asset_types = ["Office", "Warehouse", "Retail Store"]

locations = [
    "Zone A – Corporate Offices",
    "Zone B – SME Offices",
    "Logistics Cluster North",
    "Logistics Cluster South",
    "Retail Plaza Central",
    "Community Retail Strip",
    "Tech Block"
]

tenant_tiers = ["Standard", "Premium", "VIP"]

# =============================================================================
# ISSUE TEMPLATES — 60 ISSUES
#
# CRITICAL DESIGN RULE:
#   Each template carries ONLY the issue description string.
#   It does NOT carry business_impact or safety_concern.
#   Those labels are assigned independently via language pools below.
#   issue_severity here is the physical/operational severity of the
#   problem type — it contributes to proxy scoring via data_preparation.py
#   but does NOT hardcode the business_impact or safety label.
# =============================================================================

service_issues = {

    # =========================================================================
    # CRITICAL — 10 issues
    # Physical severity is critical (life-safety or total shutdown risk)
    # business_impact and safety_concern are still assigned by TEXT LANGUAGE
    # =========================================================================
    "critical": [
        {"issue": "complete power outage affecting entire floor"},
        {"issue": "severe water flooding in the storage area"},
        {"issue": "fire alarm system not functioning"},
        {"issue": "main entrance security breach"},
        {"issue": "gas leak detected near the kitchen area"},
        {"issue": "ceiling collapse in the main corridor"},
        {"issue": "electrical sparking from exposed wiring in the server room"},
        {"issue": "sewage backup flooding the ground floor restrooms"},
        {"issue": "structural crack in load-bearing wall discovered"},
        {"issue": "emergency exit doors blocked and inoperable"},
    ],

    # =========================================================================
    # HIGH — 16 issues
    # =========================================================================
    "high": [
        {"issue": "air conditioning completely broken during summer"},
        {"issue": "persistent water leakage damaging office equipment"},
        {"issue": "loading dock gate stuck closed"},
        {"issue": "elevator breakdown in multi-story unit"},
        {"issue": "heating system failed completely during winter"},
        {"issue": "internet and phone lines down for the entire office"},
        {"issue": "rodent infestation found in the warehouse"},
        {"issue": "broken main water pipe causing low pressure building-wide"},
        {"issue": "access control system failure locking employees out"},
        {"issue": "warehouse roof leaking during heavy rain"},
        {"issue": "mold growth discovered in the ventilation ducts"},
        {"issue": "freight elevator out of service for warehouse operations"},
        {"issue": "backup generator failure during power interruption"},
        {"issue": "fire suppression system triggered incorrectly flooding the server room"},
        {"issue": "CCTV system completely offline across all zones"},
        {"issue": "pest infestation spreading across multiple units"},
    ],

    # =========================================================================
    # MEDIUM — 18 issues
    # =========================================================================
    "medium": [
        {"issue": "air conditioning not cooling properly"},
        {"issue": "parking gate malfunctioning intermittently"},
        {"issue": "slow internet connectivity in common areas"},
        {"issue": "lighting issues in parking area"},
        {"issue": "thermostat not responding to temperature adjustments"},
        {"issue": "toilet not flushing properly in the office restroom"},
        {"issue": "cracks appearing in the office wall"},
        {"issue": "foul smell coming from the ventilation system"},
        {"issue": "hot water not available in the office kitchen"},
        {"issue": "door lock on the main office entrance is jammed"},
        {"issue": "insufficient electrical outlets for office equipment"},
        {"issue": "window blinds broken and cannot be adjusted"},
        {"issue": "intercom system not functioning on the ground floor"},
        {"issue": "fire extinguisher inspection overdue"},
        {"issue": "communal printer room constantly overheating"},
        {"issue": "delivery bay door closing mechanism faulty"},
        {"issue": "water pressure fluctuating throughout the day"},
        {"issue": "shared meeting room AV system not working"},
    ],

    # =========================================================================
    # LOW — 16 issues
    # =========================================================================
    "low": [
        {"issue": "minor noise disturbance from nearby unit"},
        {"issue": "cleaning services missed one day"},
        {"issue": "lost and found item to report"},
        {"issue": "request for additional waste bins"},
        {"issue": "signage outside our unit is faded and hard to read"},
        {"issue": "vending machine in the break room is out of stock"},
        {"issue": "minor paint peeling on the corridor walls"},
        {"issue": "squeaky door hinge on the conference room"},
        {"issue": "request to adjust the shared hallway temperature"},
        {"issue": "garden area outside needs trimming"},
        {"issue": "recycling bins not being collected on schedule"},
        {"issue": "request to replace a burnt-out lightbulb in the stairwell"},
        {"issue": "communal kitchen sink draining slowly"},
        {"issue": "gym equipment in the shared fitness room needs servicing"},
        {"issue": "bird nesting near the entrance causing minor mess"},
        {"issue": "water cooler in the common area running low too often"},
    ],
}

# =============================================================================
# LANGUAGE POOLS — TEXT DRIVES LABELS
#
# Each pool is keyed by the TARGET LABEL VALUE.
# When generating a record:
#   1. Pick target business_impact, safety_concern, issue_urgency randomly
#   2. Pull consequence language, safety language, and duration language
#      that MATCHES those targets
#   3. Assemble transcript using that language
# This ensures the TEXT reliably signals the label without hardcoding
# the label to the issue type.
# =============================================================================

# --- CONSEQUENCE LANGUAGE → drives business_impact ---
CONSEQUENCE_PHRASES = {
    "low": [
        "While this has caused minor inconvenience, operations are still ongoing.",
        "The disruption remains limited and we can manage for now.",
        "It has not significantly affected our day-to-day work.",
        "The impact has been manageable and contained so far.",
        "Most of our operations are unaffected at this stage.",
        "This is a small inconvenience but nothing we cannot work around.",
        "The issue is noticeable but not preventing us from operating.",
    ],
    "medium": [
        "This has started to affect our daily workflow and coordination.",
        "Operational efficiency has been noticeably impacted.",
        "There have been delays in routine activities as a result.",
        "Our team is struggling to maintain normal output levels.",
        "We are experiencing interruptions that are slowing us down.",
        "Some of our processes have had to be paused or rescheduled.",
        "This is creating friction in our operations and affecting productivity.",
    ],
    "high": [
        "As a result, our operations have come to a complete halt.",
        "We are currently unable to continue normal business activities.",
        "This has severely disrupted our operational continuity.",
        "We are losing business every hour this remains unresolved.",
        "Our entire team cannot work because of this situation.",
        "We are unable to serve our clients and are losing revenue.",
        "This is causing serious financial damage to our business.",
        "All work has stopped. We cannot function until this is fixed.",
    ],
}

# --- SAFETY LANGUAGE → drives safety_concern ---
SAFETY_PHRASES = {
    True: [
        "Additionally, there is a clear safety risk that must be addressed immediately.",
        "We are concerned this could result in injury to our staff or visitors.",
        "This situation presents a serious health and safety hazard.",
        "Exposed elements present a real danger to anyone in the vicinity.",
        "We have identified a potential safety risk that requires urgent attention.",
        "There are visible hazards that could cause harm if left unaddressed.",
        "This is a safety concern and we have flagged it to our own safety officer.",
        "Someone could get seriously hurt if this is not resolved quickly.",
        "We have taken precautions but the underlying safety risk remains.",
    ],
    False: [
        "At this time there does not appear to be any immediate safety risk.",
        "We have not identified any hazards but the issue still needs resolving.",
        "No safety concerns have been flagged by our team at this stage.",
        "Fortunately, no one has been put in danger by this issue so far.",
        "This is an operational issue only and does not pose a safety threat.",
    ],
}

# --- DURATION LANGUAGE → drives issue_urgency ---
# urgency is defined by how long the issue has been ongoing and whether
# the tenant has escalated. The longer and more escalated, the higher urgency.
DURATION_PHRASES = {
    "low": [
        "since this morning",
        "for the past few hours",
        "since earlier today",
        "just recently",
        "since yesterday",
    ],
    "medium": [
        "for the past two days",
        "for about three days now",
        "since the beginning of this week",
        "for a few days",
        "since last Monday",
    ],
    "high": [
        "for almost a week",
        "for over a week now",
        "for the past two weeks",
        "since last week",
        "for more than a week",
    ],
    "critical": [
        "for nearly a month now",
        "for over three weeks",
        "since the beginning of the month",
        "for several weeks",
        "since we moved in and it has never been fixed",
    ],
}

# Escalation language — added when urgency is high or critical
ESCALATION_PHRASES = {
    "high": [
        "I have reported this before but it has not been resolved.",
        "This was raised previously with your team.",
        "We have contacted you about this already.",
        "Despite a previous report, the problem persists.",
    ],
    "critical": [
        "This is the third time I am reporting this issue.",
        "We have contacted you multiple times with no resolution.",
        "Nothing has been done despite repeated complaints.",
        "I have escalated this twice already and nothing has changed.",
        "We are considering escalating this formally given the lack of response.",
    ],
}

# =============================================================================
# EMOTIONAL TONE PHRASES — 10 per category
# =============================================================================

emotional_tones = {
    "frustrated": [
        "This is extremely frustrating.",
        "I have been calling for days about this.",
        "This is unacceptable.",
        "We are very disappointed with the response time.",
        "I need to speak with a manager.",
        "This is the third time I am reporting this.",
        "Nobody seems to be taking this seriously.",
        "I expected much better from this facility.",
        "We are paying good money and this is what we get.",
        "I am losing patience with this situation.",
    ],
    "angry": [
        "This is completely unacceptable!",
        "I am very upset about this situation.",
        "We are considering legal action if this is not resolved.",
        "This is a breach of our lease agreement.",
        "I want this escalated immediately!",
        "We are paying premium rent for this kind of service?",
        "I want a formal complaint logged right now.",
        "This is outrageous, we have been ignored for weeks.",
        "I demand to speak with someone who can actually fix this.",
        "If this is not resolved today we are contacting our lawyers.",
    ],
    "concerned": [
        "I am quite worried about this.",
        "This could become a bigger problem if left alone.",
        "We need this addressed soon before it gets worse.",
        "I am concerned about the implications for our business.",
        "This is affecting our daily operations.",
        "We want to make sure this does not escalate.",
        "Could you prioritize this before something goes wrong?",
        "We are a bit anxious about the timeline for the fix.",
        "I hope this can be handled before our clients visit.",
        "It is starting to worry some of our staff.",
    ],
    "professional": [
        "I would like to report an issue.",
        "We need assistance with this matter.",
        "Could you please look into this at your convenience?",
        "I appreciate your help with this.",
        "Thank you for your attention to this.",
        "We wanted to bring this to your attention.",
        "Please log this and let us know the next steps.",
        "We understand these things take time.",
        "Just flagging this for the maintenance team.",
        "We are happy to work with your schedule on this.",
    ],
    "satisfied": [
        "Thank you for your quick response.",
        "I appreciate the help, really.",
        "That sounds good, thank you.",
        "Great, thank you for taking care of this.",
        "Perfect, that works for us.",
        "We are glad you are looking into it.",
        "Thanks for being so responsive.",
        "We appreciate the fast turnaround.",
        "That is reassuring, thank you.",
        "Wonderful, we will wait for the update.",
    ],
}

# =============================================================================
# AGENT RESPONSE PHRASES
# =============================================================================

AGENT_COMMIT = {
    "critical": [
        ("Agent: I am escalating this to our emergency response team immediately.",
         "Agent: You should receive a call within 15 minutes."),
        ("Agent: This is being treated as an emergency. I am dispatching a team now.",
         "Agent: Someone will be on site within 30 minutes."),
        ("Agent: I have flagged this as critical priority.",
         "Agent: Our emergency team is being notified right now."),
    ],
    "high": [
        ("Agent: I am marking this as high priority and escalating to the maintenance manager.",
         "Agent: We will have someone on-site within the hour."),
        ("Agent: I have escalated this to our senior maintenance team.",
         "Agent: Expect a callback within 2 hours with an update."),
        ("Agent: This is going to the top of the queue.",
         "Agent: We will get someone to your unit as soon as possible today."),
    ],
    "medium": [
        ("Agent: I have logged your ticket and our team will address this.",
         "Agent: We will update you within 24 hours."),
        ("Agent: I have created a maintenance request for this.",
         "Agent: You should hear back from us by tomorrow."),
        ("Agent: This has been noted and assigned to our facilities team.",
         "Agent: We aim to resolve medium-priority items within 48 hours."),
    ],
    "low": [
        ("Agent: I have logged this and our team will look into it.",
         "Agent: We will get to it as part of our regular maintenance schedule."),
        ("Agent: Thank you for letting us know. I have added this to our task list.",
         "Agent: It should be addressed within the next few business days."),
        ("Agent: Noted. I will pass this along to the appropriate team.",
         "Agent: They will take care of it when they are next in the area."),
    ],
}

# =============================================================================
# 4 CONVERSATION STRUCTURES
# =============================================================================

def _structure_standard(issue, asset, location, tone, is_recurring,
                        duration_phrase, consequence_phrase,
                        safety_phrase, escalation_phrase):
    """Standard: greeting → report → details → location."""
    lines = ["Agent: Industrial Park Support Desk, how may I assist?"]

    if is_recurring:
        lines.append("Tenant: Hi, I am calling again about an ongoing issue that has not been resolved.")
        lines.append(f"Tenant: {random.choice(emotional_tones['frustrated'])}")
    elif tone == "angry":
        lines.append("Tenant: I need to report a serious issue immediately.")
        lines.append(f"Tenant: {random.choice(emotional_tones['angry'])}")
    elif tone == "concerned":
        lines.append("Tenant: Hello, I need to report something that has been bothering us.")
    else:
        lines.append("Tenant: Hello, I need to report an issue.")

    lines.append(f"Tenant: We are experiencing {issue}.")
    lines.append(f"Tenant: This has been going on {duration_phrase}.")
    lines.append(f"Tenant: {consequence_phrase}")

    if escalation_phrase:
        lines.append(f"Tenant: {escalation_phrase}")

    lines.append("Agent: I am very sorry to hear that. Let me get your details to assist you.")
    lines.append("Agent: May I have your unit information?")
    lines.append(f"Tenant: We are located in {location}, {asset.lower()} unit.")

    return lines


def _structure_direct(issue, asset, location, tone, is_recurring,
                      duration_phrase, consequence_phrase,
                      safety_phrase, escalation_phrase):
    """Direct: tenant leads immediately with the problem, no pleasantries."""
    lines = ["Agent: Support Desk, good morning."]

    lines.append(f"Tenant: Yes, we have had {issue} {duration_phrase}.")
    lines.append(f"Tenant: {consequence_phrase}")

    if is_recurring:
        lines.append("Tenant: I reported this before and nothing was done about it.")
        lines.append(f"Tenant: {random.choice(emotional_tones['frustrated'])}")

    if escalation_phrase:
        lines.append(f"Tenant: {escalation_phrase}")

    lines.append("Agent: I understand. Can I confirm your location?")
    lines.append(f"Tenant: {location}, {asset.lower()}.")

    return lines


def _structure_narrative(issue, asset, location, tone, is_recurring,
                         duration_phrase, consequence_phrase,
                         safety_phrase, escalation_phrase):
    """Narrative: tenant provides background and context before stating the issue."""
    lines = ["Agent: Industrial Park Support, how can I help?"]
    lines.append(f"Tenant: Good morning. I am calling from our {asset.lower()} in {location}.")

    context_intros = [
        "So here is what happened.",
        "Let me explain the situation.",
        "I wanted to give you some background first.",
        "We have been dealing with something and I need your help.",
    ]
    lines.append(f"Tenant: {random.choice(context_intros)}")
    lines.append(f"Tenant: {duration_phrase.capitalize()}, we started noticing {issue}.")
    lines.append(f"Tenant: {consequence_phrase}")

    if tone in ["angry", "frustrated"]:
        lines.append(f"Tenant: {random.choice(emotional_tones[tone])}")

    if is_recurring:
        lines.append("Tenant: And this is not the first time. We have called about this before.")

    if escalation_phrase:
        lines.append(f"Tenant: {escalation_phrase}")

    lines.append("Agent: Thank you for explaining. I am logging this now.")

    return lines


def _structure_multi_exchange(issue, asset, location, tone, is_recurring,
                              duration_phrase, consequence_phrase,
                              safety_phrase, escalation_phrase):
    """Multi-exchange: agent asks clarifying questions, longer back-and-forth."""
    lines = ["Agent: Support Desk, how may I assist you today?"]
    lines.append("Tenant: Hi, I need to report a problem with our unit.")
    lines.append("Agent: Of course. Could you describe the issue?")
    lines.append(f"Tenant: We are dealing with {issue}.")
    lines.append("Agent: I see. How long has this been going on?")
    lines.append(f"Tenant: It has been happening {duration_phrase}.")
    lines.append("Agent: And can you tell me which unit you are in?")
    lines.append(f"Tenant: We are in {location}, the {asset.lower()}.")
    lines.append("Agent: Is this affecting your ability to operate?")
    lines.append(f"Tenant: {consequence_phrase}")

    if is_recurring:
        lines.append("Agent: Have you reported this before?")
        lines.append("Tenant: Yes, multiple times actually.")
        lines.append(f"Tenant: {random.choice(emotional_tones['frustrated'])}")
    elif tone in ["frustrated", "angry"]:
        lines.append(f"Tenant: {random.choice(emotional_tones[tone])}")

    if escalation_phrase:
        lines.append(f"Tenant: {escalation_phrase}")

    return lines


STRUCTURE_FUNCTIONS = [
    _structure_standard,
    _structure_direct,
    _structure_narrative,
    _structure_multi_exchange,
]

# =============================================================================
# SUPPORT TRANSCRIPT GENERATOR
#
# CORRELATION BREAKING LOGIC:
#   Step 1: Pick issue_type and issue_severity from template pool (physical context)
#   Step 2: Independently sample target business_impact, safety_concern, issue_urgency
#   Step 3: Select language pools that match those targets
#   Step 4: Assemble transcript — the TEXT carries the label signals
#   Result: The same issue_type can appear with any combination of labels
# =============================================================================

# Label distribution targets — intentionally balanced to avoid class imbalance
IMPACT_WEIGHTS   = {"low": 0.33, "medium": 0.34, "high": 0.33}
SAFETY_WEIGHTS   = {True: 0.35, False: 0.65}
URGENCY_WEIGHTS  = {"low": 0.25, "medium": 0.30, "high": 0.25, "critical": 0.20}


def _sample_weighted(weight_dict):
    """Sample a key from a dict of {key: probability} weights."""
    keys = list(weight_dict.keys())
    weights = list(weight_dict.values())
    return random.choices(keys, weights=weights, k=1)[0]


def generate_support_transcript(issue_severity, is_recurring=False):
    """
    Generate a support call transcript.

    issue_severity controls the PHYSICAL severity category used to pick
    the issue template. It does NOT determine business_impact, safety_concern,
    or issue_urgency — those are sampled independently and expressed through
    the transcript's language.
    """
    asset = random.choice(asset_types)
    location = random.choice(locations)
    tenant_tier = random.choice(tenant_tiers)

    # Step 1: Pick issue template (physical context only)
    issue_data = random.choice(service_issues[issue_severity])
    issue = issue_data["issue"]

    # Step 2: Sample labels INDEPENDENTLY
    target_impact   = _sample_weighted(IMPACT_WEIGHTS)
    target_safety   = _sample_weighted(SAFETY_WEIGHTS)
    target_urgency  = _sample_weighted(URGENCY_WEIGHTS)

    # Step 3: Select matching language
    consequence_phrase = random.choice(CONSEQUENCE_PHRASES[target_impact])
    safety_phrase      = random.choice(SAFETY_PHRASES[target_safety])
    duration_phrase    = random.choice(DURATION_PHRASES[target_urgency])

    # Escalation language only present for high/critical urgency
    escalation_phrase = None
    if target_urgency in ("high", "critical"):
        escalation_phrase = random.choice(ESCALATION_PHRASES[target_urgency])
    elif is_recurring:
        escalation_phrase = random.choice(ESCALATION_PHRASES["high"])

    # Step 4: Determine emotional tone
    # Tone is loosely influenced by impact and urgency but with randomness
    # so it is not a perfect predictor of labels
    if is_recurring or target_urgency == "critical":
        tone = random.choice(["frustrated", "angry"])
    elif target_impact == "high" or target_urgency == "high":
        tone = random.choice(["angry", "frustrated", "concerned"])
    elif target_impact == "medium" or target_urgency == "medium":
        tone = random.choice(["concerned", "professional"])
    else:
        tone = "professional"

    # Step 5: Pick conversation structure and build opening
    structure_fn = random.choice(STRUCTURE_FUNCTIONS)
    lines = structure_fn(
        issue, asset, location, tone, is_recurring,
        duration_phrase, consequence_phrase, safety_phrase, escalation_phrase
    )

    # Step 6: Inject safety language into the transcript TEXT
    # This is what makes the label learnable from text
    lines.append(f"Tenant: {safety_phrase}")

    # Step 7: Business impact statement for medium/high (reinforces label in text)
    if target_impact == "high":
        impact_statements = [
            "Tenant: This is seriously impacting our business operations.",
            "Tenant: We are losing money every day this goes unresolved.",
            "Tenant: Our staff cannot work properly because of this.",
            "Tenant: This is affecting our ability to serve our clients.",
        ]
        lines.append(random.choice(impact_statements))
    elif target_impact == "medium":
        medium_statements = [
            "Tenant: This is starting to affect how we work.",
            "Tenant: Our team has had to adjust how we operate because of this.",
            "Tenant: It is slowing us down more than we would like.",
        ]
        lines.append(random.choice(medium_statements))

    # Step 8: Agent commitment (keyed to issue_severity for realism)
    if issue_severity == "critical":
        pair = random.choice(AGENT_COMMIT["critical"])
    elif issue_severity == "high" or is_recurring:
        pair = random.choice(AGENT_COMMIT["high"])
    elif issue_severity == "medium":
        pair = random.choice(AGENT_COMMIT["medium"])
    else:
        pair = random.choice(AGENT_COMMIT["low"])

    lines.append(pair[0])
    lines.append(pair[1])

    # Step 9: Closing
    if tone in ["angry", "frustrated"]:
        close_pairs = [
            ("Tenant: I expect this to be resolved quickly.",
             "Agent: Absolutely. We will keep you updated every step of the way."),
            ("Tenant: Please make sure this actually gets done this time.",
             "Agent: You have my word. I will follow up personally."),
            ("Tenant: I really hope I do not have to call again about this.",
             "Agent: I understand your frustration. We will make it a priority."),
        ]
        pair = random.choice(close_pairs)
        lines.append(pair[0])
        lines.append(pair[1])
    else:
        lines.append(f"Tenant: {random.choice(emotional_tones['satisfied'])}")
        agent_closings = [
            "Agent: You are welcome. We will take care of this.",
            "Agent: Happy to help. We will be in touch.",
            "Agent: Thank you for reporting this. We will keep you updated.",
        ]
        lines.append(random.choice(agent_closings))

    return {
        "transcript":      "\n".join(lines),
        "asset":           asset,
        "location":        location,
        "tenant_tier":     tenant_tier,
        "issue_type":      issue,
        "issue_severity":  issue_severity,
        "issue_urgency":   target_urgency,
        "business_impact": target_impact,
        "safety_concern":  target_safety,
        "is_recurring":    is_recurring,
    }


# =============================================================================
# LEASING INQUIRY GENERATOR — 5 inquiry types
# Inquiries have no labels (N/A) — consistent with preprocess.py behavior
# =============================================================================

leasing_inquiries = [
    {
        "type": "professional_detailed",
        "questions": [
            "What is the rental rate per square foot?",
            "Are service charges included in the quote?",
            "What is the minimum lease term?",
            "Is the unit fitted or shell and core?",
            "How many parking spaces are allocated?",
            "Is 24/7 access permitted?",
            "What are the payment terms?",
            "Are there any move-in incentives currently available?",
            "What is the process for customizing the interior layout?",
        ],
        "tone": "formal"
    },
    {
        "type": "casual_quick",
        "questions": [
            "How much is the rent?",
            "When can we move in?",
            "Is parking included?",
            "Can you send me the details?",
            "Do you have anything smaller available?",
            "What is included in the rent?",
        ],
        "tone": "casual"
    },
    {
        "type": "urgent_expansion",
        "questions": [
            "We need space urgently for expansion.",
            "What is available immediately?",
            "Can we schedule a viewing today?",
            "What is the fastest we can sign?",
            "Can we move in within two weeks?",
        ],
        "tone": "urgent"
    },
    {
        "type": "comparison_shopping",
        "questions": [
            "How does your pricing compare to other business parks?",
            "What makes this location stand out?",
            "Do you offer flexible lease terms for startups?",
            "Are there shared facilities like meeting rooms?",
            "What is the tenant satisfaction rate here?",
        ],
        "tone": "formal"
    },
    {
        "type": "relocation_inquiry",
        "questions": [
            "We are relocating from another emirate, what do we need to know?",
            "Is there help with the setup process for new tenants?",
            "What are the logistics for moving large equipment in?",
            "Are there loading bays available during weekends?",
            "Do you assist with trade license requirements?",
        ],
        "tone": "formal"
    },
]


def generate_leasing_transcript():
    """Generate a leasing inquiry transcript with varying tones."""
    asset        = random.choice(asset_types)
    location     = random.choice(locations)
    size         = random.choice([1500, 2500, 4000, 6000, 8000, 10000, 15000, 25000])
    inquiry_type = random.choice(leasing_inquiries)

    lines = ["Agent: Industrial Park Leasing Desk, good morning."]

    if inquiry_type["tone"] == "urgent":
        lines.append("Caller: Hello, I need to find space urgently.")
        lines.append("Caller: Our current location is no longer suitable.")
    elif inquiry_type["tone"] == "casual":
        lines.append("Caller: Hi there, I am looking for some space to rent.")
    else:
        lines.append("Caller: Good morning, I am calling to enquire about available space.")

    lines.append("Agent: Certainly. Are you looking for office, warehouse, or retail space?")
    lines.append(f"Caller: We need a {asset.lower()}.")
    lines.append("Agent: Do you have a preferred location within the park?")
    lines.append(f"Caller: Ideally in {location}.")
    lines.append("Agent: May I know your size requirement?")
    lines.append(f"Caller: Approximately {size} square feet.")

    num_questions = random.randint(2, min(4, len(inquiry_type["questions"])))
    selected_questions = random.sample(inquiry_type["questions"], num_questions)

    for question in selected_questions:
        lines.append(f"Caller: {question}")
        q_lower = question.lower()
        if "rate" in q_lower or "how much" in q_lower or "pricing" in q_lower or "rent" in q_lower:
            lines.append("Agent: The rate varies by location and specifications. I can provide detailed pricing.")
        elif "when" in q_lower or "move in" in q_lower or "fastest" in q_lower:
            lines.append("Agent: We have immediate availability in several units.")
        elif "parking" in q_lower:
            lines.append("Agent: Parking allocation depends on the unit size, typically 1 space per 1000 sq ft.")
        elif "compare" in q_lower or "stand out" in q_lower:
            lines.append("Agent: We offer competitive rates with excellent facilities and a prime location.")
        elif "flexible" in q_lower or "startup" in q_lower:
            lines.append("Agent: Yes, we have flexible options including short-term leases for growing businesses.")
        elif "relocat" in q_lower or "emirate" in q_lower:
            lines.append("Agent: We have a dedicated relocation team that can help guide you through the process.")
        elif "trade license" in q_lower:
            lines.append("Agent: We work closely with the free zone authority and can assist with licensing.")
        elif "loading" in q_lower or "logistics" in q_lower or "equipment" in q_lower:
            lines.append("Agent: We have dedicated loading bays and can arrange after-hours access for moves.")
        else:
            lines.append("Agent: I can include all those details in the proposal.")

    if inquiry_type["tone"] == "urgent":
        lines.append("Caller: Can we schedule a viewing today?")
        lines.append("Agent: Absolutely. I can arrange a viewing this afternoon.")
        lines.append("Caller: Perfect, please send me the details.")
    else:
        lines.append("Caller: That sounds good. Please send the details.")
        lines.append("Agent: I will email you the floor plans, pricing, and lease terms within the hour.")
        lines.append("Caller: Thank you.")

    return {
        "transcript":      "\n".join(lines),
        "asset":           asset,
        "location":        location,
        "tenant_tier":     "Prospective",
        "issue_type":      inquiry_type["type"],
        "issue_severity":  "N/A",
        "issue_urgency":   "N/A",
        "business_impact": "N/A",
        "safety_concern":  False,
        "is_recurring":    False,
    }


# =============================================================================
# DATASET GENERATOR
#
# Distribution:
#   60% Tenant Support, 40% Leasing Inquiry
#   Support severity: 10% critical, 25% high, 40% medium, 25% low
#   Recurring rate:   40% critical, 35% high, 25% medium, 15% low
# =============================================================================

def generate_dataset(num_records=2000):
    """Generate the full dataset."""
    records = []

    num_support = int(num_records * 0.6)
    num_leasing = num_records - num_support

    num_critical = int(num_support * 0.10)
    num_high     = int(num_support * 0.25)
    num_medium   = int(num_support * 0.40)
    num_low      = num_support - num_critical - num_high - num_medium

    support_calls = (
        [(generate_support_transcript("critical", random.random() < 0.40), "Tenant Support")
         for _ in range(num_critical)] +
        [(generate_support_transcript("high",     random.random() < 0.35), "Tenant Support")
         for _ in range(num_high)] +
        [(generate_support_transcript("medium",   random.random() < 0.25), "Tenant Support")
         for _ in range(num_medium)] +
        [(generate_support_transcript("low",      random.random() < 0.15), "Tenant Support")
         for _ in range(num_low)]
    )

    leasing_calls = [
        (generate_leasing_transcript(), "Leasing Inquiry")
        for _ in range(num_leasing)
    ]

    all_calls = support_calls + leasing_calls
    random.shuffle(all_calls)

    start_date = datetime.now() - timedelta(days=90)

    for i, (call_data, category) in enumerate(all_calls, 1):
        timestamp = start_date + timedelta(
            days=random.randint(0, 90),
            hours=random.randint(8, 18),
            minutes=random.randint(0, 59)
        )

        records.append({
            "call_id":         f"IP-{timestamp.strftime('%Y%m')}-{i:05d}",
            "timestamp":       timestamp.strftime("%Y-%m-%d %H:%M:%S"),
            "call_category":   category,
            "tenant_tier":     call_data["tenant_tier"],
            "asset_type":      call_data["asset"],
            "location":        call_data["location"],
            "issue_type":      call_data["issue_type"],
            "issue_severity":  call_data["issue_severity"],
            "issue_urgency":   call_data["issue_urgency"],
            "business_impact": call_data["business_impact"],
            "safety_concern":  call_data["safety_concern"],
            "is_recurring":    call_data["is_recurring"],
            "transcript":      call_data["transcript"],
        })

    return pd.DataFrame(records)


# =============================================================================
# CORRELATION VALIDATION
# Runs after generation to verify no structural shortcuts exist.
# =============================================================================

def validate_no_correlations(df):
    """
    Check that labels are not structurally predictable from metadata.

    Threshold logic:
    - issue_severity / issue_urgency checks use 0.85 — these columns have
      only 4 values so sample sizes per cell are large. Any dominance >85%
      is a genuine structural shortcut.
    - issue_type checks use 0.92 — with 60 issue types across ~1800 support
      rows each type has ~30 records. At p=0.30 safety probability, getting
      <5 True samples by random chance (not by design) is possible and flags
      falsely at 0.85. Using 0.92 limits false positives to cases where an
      issue type has ≤2 True samples out of 30+, which would only occur if
      the probability were structurally suppressed below 10%.
    """
    print("\n=== CORRELATION VALIDATION ===")

    support = df[df["call_category"] == "Tenant Support"].copy()

    # (check_name, col_a, col_b, threshold)
    checks = [
        ("issue_severity → business_impact",  "issue_severity", "business_impact",  0.85),
        ("issue_severity → safety_concern",   "issue_severity", "safety_concern",   0.85),
        ("issue_severity → issue_urgency",    "issue_severity", "issue_urgency",    0.85),
        ("issue_type → business_impact",      "issue_type",     "business_impact",  0.92),
        ("issue_type → safety_concern",       "issue_type",     "safety_concern",   0.92),
    ]

    all_passed = True
    for check_name, col_a, col_b, threshold in checks:
        table = pd.crosstab(support[col_a], support[col_b], normalize="index")
        shortcuts = []
        for idx, row in table.iterrows():
            n = support[support[col_a] == idx].shape[0]
            if row.max() > threshold:
                shortcuts.append(
                    f"  ⚠  {idx} (n={n}): {col_b}={row.idxmax()} "
                    f"= {row.max():.0%}"
                )
        if shortcuts:
            all_passed = False
            print(f"\n[FAIL] {check_name} (threshold={threshold:.0%})")
            for s in shortcuts:
                print(s)
        else:
            print(f"[PASS] {check_name} — no shortcuts detected")

    if all_passed:
        print("\n✓ All correlation checks passed. No structural shortcuts found.")
    else:
        print("\n⚠  Some shortcuts detected — review above. If n is small "
              "(<20 per cell), this may be a sample-size artefact and will "
              "resolve after step2 augmentation.")

    print()


# =============================================================================
# MAIN
# =============================================================================

if __name__ == "__main__":
    import sys

    num_records = int(sys.argv[1]) if len(sys.argv) > 1 else 3000

    print("=" * 70)
    print("ENHANCED DATA SYNTHESIZER V6")
    print("=" * 70)
    print(f"  Target records:       {num_records}")
    print(f"  Issue templates:      {sum(len(v) for v in service_issues.values())} "
          f"({', '.join(f'{k}={len(v)}' for k, v in service_issues.items())})")
    print(f"  Conversation structs: {len(STRUCTURE_FUNCTIONS)}")
    print(f"  Impact pools:         {sum(len(v) for v in CONSEQUENCE_PHRASES.values())} phrases")
    print(f"  Safety pools:         {sum(len(v) for v in SAFETY_PHRASES.values())} phrases")
    print(f"  Duration pools:       {sum(len(v) for v in DURATION_PHRASES.values())} phrases")
    print(f"  Correlation mode:     TEXT-DRIVEN (labels independent of issue_type)")
    print()

    df = generate_dataset(num_records)

    output_path = "Enhanced_DataSet_SentimentAnalysis_v6.csv"
    df.to_csv(output_path, index=False)

    print(f"Dataset generated: {len(df)} records → {output_path}")

    print("\n=== DISTRIBUTION REPORT ===")

    print("\nCall Category:")
    print(df["call_category"].value_counts().to_string())

    support = df[df["call_category"] == "Tenant Support"]

    print("\nIssue Severity (Support only):")
    print(support["issue_severity"].value_counts().to_string())

    print("\nIssue Urgency (Support only):")
    print(support["issue_urgency"].value_counts().to_string())

    print("\nBusiness Impact (Support only):")
    print(support["business_impact"].value_counts().to_string())

    print("\nSafety Concern (Support only):")
    print(support["safety_concern"].value_counts().to_string())

    print("\nSeverity × Urgency cross-tab (verify independence):")
    print(pd.crosstab(support["issue_severity"], support["issue_urgency"],
                      normalize="index").round(2).to_string())

    print("\nSeverity × Business Impact cross-tab (verify independence):")
    print(pd.crosstab(support["issue_severity"], support["business_impact"],
                      normalize="index").round(2).to_string())

    print(f"\nUnique issue types: {support['issue_type'].nunique()}")
    print(f"Recurring issues:   {df['is_recurring'].sum()}")
    print(f"Safety concerns:    {df['safety_concern'].sum()}")

    validate_no_correlations(df)

    print(f"Saved to: {output_path}")
