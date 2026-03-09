"""
=============================================================================
ENHANCED DATA SYNTHESIZER V2
=============================================================================

Generates synthetic complaint and inquiry transcripts for the InnovaCX
sentiment analysis pipeline.

CHANGES FROM V1 (enhanced_data_synthesizer.py):
    - Expanded from 16 to 48 issue templates (3x variety)
    - Added 7 new issue categories: structural, pest control, common areas,
      administrative, delivery/logistics, signage, and environmental
    - 4 distinct conversation structures instead of 1 fixed template
    - More emotional tone phrases (10 per category instead of 5-6)
    - Duration references embedded in complaints for urgency signal
    - Expanded leasing inquiries with 2 new inquiry types
    - Variable-length transcripts (some short, some long)
    - Default 1500 records (up from 1000)

OUTPUT SCHEMA (identical to V1 — fully backward compatible):
    call_id, timestamp, call_category, tenant_tier, asset_type, location,
    issue_type, issue_severity, business_impact, safety_concern, is_recurring,
    transcript

USAGE:
    python enhanced_data_synthesizer_v2.py [num_records]
    Default: 1500 records

=============================================================================
"""

import pandas as pd
import random
from datetime import datetime, timedelta

random.seed(101)

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
# ISSUE TEMPLATES — 48 ISSUES (up from 16)
#
# Each severity has 8-12 issues (up from 4 each).
# Each issue has 4 phrases (up from 3 each).
# Total unique issue cores: 48
# Total unique phrases: 192
# =============================================================================

service_issues = {
    # =========================================================================
    # CRITICAL — 8 issues (up from 4)
    # =========================================================================
    "critical": [
        # Original 4
        {
            "issue": "complete power outage affecting entire floor",
            "impact": "high",
            "safety_concern": True,
            "phrases": [
                "all our systems are down",
                "we can't operate at all",
                "this is a major emergency",
                "our servers have shut down and we're losing data"
            ]
        },
        {
            "issue": "severe water flooding in the storage area",
            "impact": "high",
            "safety_concern": True,
            "phrases": [
                "our inventory is getting damaged",
                "water is everywhere on the ground floor",
                "this is destroying our stock",
                "we need emergency cleanup immediately"
            ]
        },
        {
            "issue": "fire alarm system not functioning",
            "impact": "high",
            "safety_concern": True,
            "phrases": [
                "this is a safety violation",
                "we could face regulatory issues",
                "this needs immediate attention",
                "our staff are worried about safety"
            ]
        },
        {
            "issue": "main entrance security breach",
            "impact": "high",
            "safety_concern": True,
            "phrases": [
                "our security is compromised",
                "there was unauthorized access to our floor",
                "this is very concerning for our staff",
                "we found the door forced open this morning"
            ]
        },
        # New critical issues
        {
            "issue": "gas leak detected near the kitchen area",
            "impact": "high",
            "safety_concern": True,
            "phrases": [
                "we can smell gas strongly",
                "we've evacuated the floor as a precaution",
                "someone could get seriously hurt",
                "this is extremely dangerous"
            ]
        },
        {
            "issue": "ceiling collapse in the main corridor",
            "impact": "high",
            "safety_concern": True,
            "phrases": [
                "debris fell from the ceiling onto the hallway",
                "part of the ceiling caved in",
                "someone could have been injured",
                "the structural integrity seems compromised"
            ]
        },
        {
            "issue": "electrical sparking from exposed wiring in the server room",
            "impact": "high",
            "safety_concern": True,
            "phrases": [
                "there are visible sparks coming from the wall",
                "this is a fire hazard",
                "our IT equipment is at risk of damage",
                "we've cut power to that section but need urgent repair"
            ]
        },
        {
            "issue": "sewage backup flooding the ground floor restrooms",
            "impact": "high",
            "safety_concern": True,
            "phrases": [
                "raw sewage is overflowing onto the floor",
                "the smell is making people sick",
                "this is a health hazard for everyone in the building",
                "we cannot use any of the restroom facilities"
            ]
        },
    ],

    # =========================================================================
    # HIGH — 10 issues (up from 4)
    # =========================================================================
    "high": [
        # Original 4
        {
            "issue": "air conditioning completely broken during summer",
            "impact": "medium-high",
            "safety_concern": False,
            "phrases": [
                "it's unbearable to work in this heat",
                "our employees are complaining constantly",
                "we might need to close early today",
                "the indoor temperature is over 35 degrees"
            ]
        },
        {
            "issue": "persistent water leakage damaging office equipment",
            "impact": "medium-high",
            "safety_concern": False,
            "phrases": [
                "our computers are at risk from the dripping",
                "this has been going on for days now",
                "we've lost equipment already to water damage",
                "we had to move desks away from the leak"
            ]
        },
        {
            "issue": "loading dock gate stuck closed",
            "impact": "medium-high",
            "safety_concern": False,
            "phrases": [
                "we can't receive any deliveries",
                "our operations are completely halted",
                "we're losing business every hour this stays broken",
                "trucks are backing up outside with nowhere to unload"
            ]
        },
        {
            "issue": "elevator breakdown in multi-story unit",
            "impact": "medium-high",
            "safety_concern": False,
            "phrases": [
                "it's very difficult for staff to use the stairs",
                "we have employees with mobility concerns",
                "this is extremely inconvenient for our clients",
                "we're on the sixth floor and people are struggling"
            ]
        },
        # New high issues
        {
            "issue": "heating system failed completely during winter",
            "impact": "medium-high",
            "safety_concern": False,
            "phrases": [
                "our office is freezing cold",
                "employees are wearing coats at their desks",
                "clients are complaining about the temperature",
                "we can't work productively in these conditions"
            ]
        },
        {
            "issue": "internet and phone lines down for the entire office",
            "impact": "medium-high",
            "safety_concern": False,
            "phrases": [
                "we have no connectivity at all",
                "our business depends on being online",
                "we've missed client calls and deadlines",
                "this is costing us thousands in lost revenue"
            ]
        },
        {
            "issue": "rodent infestation found in the warehouse",
            "impact": "medium-high",
            "safety_concern": False,
            "phrases": [
                "we found droppings near our stored goods",
                "our products could be contaminated",
                "clients will not accept goods from here",
                "this is a serious health and hygiene concern"
            ]
        },
        {
            "issue": "broken main water pipe causing low pressure building-wide",
            "impact": "medium-high",
            "safety_concern": False,
            "phrases": [
                "there's barely any water coming from the taps",
                "the restrooms are unusable",
                "we can't operate the kitchen or break room",
                "this affects every tenant on our floor"
            ]
        },
        {
            "issue": "access control system failure locking employees out",
            "impact": "medium-high",
            "safety_concern": False,
            "phrases": [
                "none of our keycards are working",
                "staff are locked out of the building",
                "we had to wait outside for over an hour",
                "this is completely unacceptable for a business park"
            ]
        },
        {
            "issue": "warehouse roof leaking during heavy rain",
            "impact": "medium-high",
            "safety_concern": False,
            "phrases": [
                "water is dripping onto our stored inventory",
                "we've already lost several pallets of goods",
                "the leak is getting worse each time it rains",
                "we need the roof patched before the next storm"
            ]
        },
    ],

    # =========================================================================
    # MEDIUM — 12 issues (up from 4)
    # =========================================================================
    "medium": [
        # Original 4
        {
            "issue": "air conditioning not cooling properly",
            "impact": "medium",
            "safety_concern": False,
            "phrases": [
                "it's uncomfortable but we can manage",
                "the temperature isn't ideal for working",
                "we'd like this checked when possible",
                "it's warmer than it should be in here"
            ]
        },
        {
            "issue": "parking gate malfunctioning intermittently",
            "impact": "medium",
            "safety_concern": False,
            "phrases": [
                "sometimes it works, sometimes it doesn't",
                "it's causing delays for our staff every morning",
                "quite frustrating when you're running late",
                "we have to wait for someone to manually open it"
            ]
        },
        {
            "issue": "slow internet connectivity in common areas",
            "impact": "medium",
            "safety_concern": False,
            "phrases": [
                "the WiFi is very slow in the lobby",
                "we can't have video meetings properly",
                "this affects our work when we use the meeting rooms",
                "pages take forever to load"
            ]
        },
        {
            "issue": "lighting issues in parking area",
            "impact": "medium",
            "safety_concern": False,
            "phrases": [
                "it's quite dark in the evening",
                "we're concerned about safety after hours",
                "several lights are flickering or out",
                "our employees feel unsafe walking to their cars"
            ]
        },
        # New medium issues
        {
            "issue": "thermostat not responding to temperature adjustments",
            "impact": "medium",
            "safety_concern": False,
            "phrases": [
                "we've tried changing the settings but nothing happens",
                "the display seems frozen on one temperature",
                "it's either too hot or too cold with no control",
                "we'd like someone to recalibrate it"
            ]
        },
        {
            "issue": "toilet not flushing properly in the office restroom",
            "impact": "medium",
            "safety_concern": False,
            "phrases": [
                "the flush is very weak and doesn't clear",
                "it's embarrassing for our staff and visitors",
                "we've reported this before but it keeps happening",
                "it's unhygienic and needs to be fixed"
            ]
        },
        {
            "issue": "cracks appearing in the office wall",
            "impact": "medium",
            "safety_concern": False,
            "phrases": [
                "we've noticed new cracks forming",
                "it doesn't look structural but we want it checked",
                "clients can see the cracks and it looks unprofessional",
                "we're concerned it could get worse over time"
            ]
        },
        {
            "issue": "foul smell coming from the ventilation system",
            "impact": "medium",
            "safety_concern": False,
            "phrases": [
                "there's a persistent bad odor when the AC runs",
                "staff are getting headaches from the smell",
                "we think something might be stuck in the ducts",
                "it's been getting worse over the past week"
            ]
        },
        {
            "issue": "hot water not available in the office kitchen",
            "impact": "medium",
            "safety_concern": False,
            "phrases": [
                "the water heater seems to have stopped working",
                "staff can't make tea or coffee properly",
                "it's been cold water only for three days now",
                "this is a basic amenity that should be working"
            ]
        },
        {
            "issue": "door lock on the main office entrance is jammed",
            "impact": "medium",
            "safety_concern": False,
            "phrases": [
                "we have to force the door to lock it",
                "sometimes the key gets stuck and we can't open it",
                "we're worried about security if we can't lock up",
                "it needs to be replaced before it breaks completely"
            ]
        },
        {
            "issue": "frequent circuit breaker trips in the office",
            "impact": "medium",
            "safety_concern": False,
            "phrases": [
                "the breaker trips at least once a day",
                "we lose power to half our desks when it happens",
                "it's disrupting our work regularly",
                "we're worried about overloading the electrical system"
            ]
        },
        {
            "issue": "window blinds broken and cannot be adjusted",
            "impact": "medium",
            "safety_concern": False,
            "phrases": [
                "the sun glare makes it hard to see our screens",
                "we've tried fixing them ourselves but they're stuck",
                "it's uncomfortable working in direct sunlight all day",
                "some blinds are hanging loose and look unprofessional"
            ]
        },
    ],

    # =========================================================================
    # LOW — 12 issues (up from 4) + 6 additional = 18 total low templates
    # More low issues because medium/low have higher record counts
    # =========================================================================
    "low": [
        # Original 4
        {
            "issue": "minor noise disturbance from nearby unit",
            "impact": "low",
            "safety_concern": False,
            "phrases": [
                "it's a bit noisy during certain hours",
                "just wanted to report this for the record",
                "when you have time, could someone look into it",
                "it's not urgent but it is noticeable"
            ]
        },
        {
            "issue": "cleaning services missed one day",
            "impact": "low",
            "safety_concern": False,
            "phrases": [
                "just letting you know the cleaners didn't come",
                "not urgent at all",
                "when possible, could you check the schedule",
                "the bins are full but it can wait"
            ]
        },
        {
            "issue": "lost and found item to report",
            "impact": "low",
            "safety_concern": False,
            "phrases": [
                "found something in the lobby area",
                "wondering if anyone reported a missing item",
                "not urgent, just wanted to hand it in",
                "could you check if someone's been asking about it"
            ]
        },
        {
            "issue": "request for additional waste bins",
            "impact": "low",
            "safety_concern": False,
            "phrases": [
                "would be helpful to have more bins near the entrance",
                "when convenient, we'd appreciate extra bins",
                "just a small request for the facilities team",
                "the current bins fill up quite quickly"
            ]
        },
        # New low issues
        {
            "issue": "signage outside our unit is faded and hard to read",
            "impact": "low",
            "safety_concern": False,
            "phrases": [
                "visitors sometimes can't find our office",
                "the sign has been fading for a while now",
                "when you have time, could it be replaced",
                "it's a minor thing but it does affect first impressions"
            ]
        },
        {
            "issue": "vending machine in the break room is out of stock",
            "impact": "low",
            "safety_concern": False,
            "phrases": [
                "it's been empty for about a week",
                "staff would appreciate it being restocked",
                "not a priority but thought I'd mention it",
                "when the vendor comes next could they fill it up"
            ]
        },
        {
            "issue": "minor paint peeling on the corridor walls",
            "impact": "low",
            "safety_concern": False,
            "phrases": [
                "it's just cosmetic but it looks a bit worn",
                "clients walk through there so it matters a little",
                "whenever maintenance is in the area they could touch it up",
                "it's not urgent at all"
            ]
        },
        {
            "issue": "squeaky door hinge on the conference room",
            "impact": "low",
            "safety_concern": False,
            "phrases": [
                "it's a bit distracting during meetings",
                "just needs some oil or a quick fix",
                "not a big deal but thought I'd mention it",
                "people keep commenting on it"
            ]
        },
        {
            "issue": "request to adjust the shared hallway temperature",
            "impact": "low",
            "safety_concern": False,
            "phrases": [
                "the hallway is a bit too warm these days",
                "if it's possible to lower it a degree or two",
                "just a comfort thing, nothing urgent",
                "a few tenants have mentioned it in passing"
            ]
        },
        {
            "issue": "garden area outside needs trimming",
            "impact": "low",
            "safety_concern": False,
            "phrases": [
                "the hedges are a bit overgrown",
                "it would look nicer if the landscaping was tidied up",
                "when the gardeners are next scheduled could they trim it",
                "our clients noticed it looking a bit neglected"
            ]
        },
        {
            "issue": "recycling bins not being collected on schedule",
            "impact": "low",
            "safety_concern": False,
            "phrases": [
                "the recycling has been overflowing for a few days",
                "we're trying to be sustainable but it's hard without pickup",
                "could you check the collection schedule",
                "just a small housekeeping issue"
            ]
        },
        {
            "issue": "request to replace a burnt-out lightbulb in the stairwell",
            "impact": "low",
            "safety_concern": False,
            "phrases": [
                "one of the stairwell lights is out",
                "it's not completely dark but dimmer than usual",
                "just a quick maintenance job when someone's available",
                "it's been like that for about a week"
            ]
        },
        {
            "issue": "communal kitchen sink draining slowly",
            "impact": "low",
            "safety_concern": False,
            "phrases": [
                "the water takes a while to drain after washing up",
                "it's not blocked, just very slow",
                "probably just needs a quick clean of the drain",
                "not urgent but it would be nice to have it sorted"
            ]
        },
        {
            "issue": "gym equipment in the shared fitness room needs servicing",
            "impact": "low",
            "safety_concern": False,
            "phrases": [
                "the treadmill makes a strange sound when running",
                "a couple of the weight machines are a bit stiff",
                "just needs a routine service when possible",
                "staff really appreciate having the gym so we'd like it maintained"
            ]
        },
        {
            "issue": "suggestion for better directional signage in the building",
            "impact": "low",
            "safety_concern": False,
            "phrases": [
                "new visitors often get lost finding our floor",
                "better signs near the elevators would help a lot",
                "just a suggestion, not a complaint really",
                "we've had a few clients arrive late because they got confused"
            ]
        },
        {
            "issue": "bird nesting near the entrance causing minor mess",
            "impact": "low",
            "safety_concern": False,
            "phrases": [
                "there's some droppings on the walkway from the nests",
                "it's a bit unsightly for clients arriving",
                "can it be cleaned up and maybe the nests relocated",
                "not a big deal, just thought I'd mention it"
            ]
        },
        {
            "issue": "request for a bench or seating area near the entrance",
            "impact": "low",
            "safety_concern": False,
            "phrases": [
                "sometimes people wait outside and there's nowhere to sit",
                "a small bench would be really appreciated",
                "just a quality of life improvement suggestion",
                "it would make the entrance area more welcoming"
            ]
        },
        {
            "issue": "water cooler in the common area running low too often",
            "impact": "low",
            "safety_concern": False,
            "phrases": [
                "the water bottles need replacing more frequently",
                "it runs out by midday most days",
                "staff rely on it especially in the warmer months",
                "could the refill schedule be increased"
            ]
        },
    ]
}

# =============================================================================
# EMOTIONAL TONE PHRASES — 10 per category (up from 5-6)
# =============================================================================

emotional_tones = {
    "frustrated": [
        "This is extremely frustrating.",
        "I've been calling for days about this.",
        "This is unacceptable.",
        "We're very disappointed with the response time.",
        "I need to speak with a manager.",
        "This is the third time I'm reporting this.",
        "Nobody seems to be taking this seriously.",
        "I expected much better from this facility.",
        "We're paying good money and this is what we get.",
        "I'm losing patience with this situation."
    ],
    "angry": [
        "This is completely unacceptable!",
        "I'm very upset about this situation.",
        "We're considering legal action if this isn't resolved.",
        "This is a breach of our lease agreement.",
        "I want this escalated immediately!",
        "We're paying premium rent for this kind of service?",
        "I want a formal complaint logged right now.",
        "This is outrageous, we've been ignored for weeks.",
        "I demand to speak with someone who can actually fix this.",
        "If this isn't resolved today, we're contacting our lawyers."
    ],
    "concerned": [
        "I'm quite worried about this.",
        "This could become a bigger problem if left alone.",
        "We need this addressed soon before it gets worse.",
        "I'm concerned about the implications for our business.",
        "This is affecting our daily operations.",
        "We want to make sure this doesn't escalate.",
        "Could you prioritize this before something goes wrong?",
        "We're a bit anxious about the timeline for the fix.",
        "I hope this can be handled before our clients visit.",
        "It's starting to worry some of our staff."
    ],
    "professional": [
        "I'd like to report an issue.",
        "We need assistance with this matter.",
        "Could you please look into this at your convenience?",
        "I appreciate your help with this.",
        "Thank you for your attention to this.",
        "We wanted to bring this to your attention.",
        "Please log this and let us know the next steps.",
        "We understand these things take time.",
        "Just flagging this for the maintenance team.",
        "We're happy to work with your schedule on this."
    ],
    "satisfied": [
        "Thank you for your quick response.",
        "I appreciate the help, really.",
        "That sounds good, thank you.",
        "Great, thank you for taking care of this.",
        "Perfect, that works for us.",
        "We're glad you're looking into it.",
        "Thanks for being so responsive.",
        "We appreciate the fast turnaround.",
        "That's reassuring, thank you.",
        "Wonderful, we'll wait for the update."
    ]
}

# Duration phrases — embedded in complaints to provide urgency signal
duration_phrases = [
    "since yesterday",
    "for the past two days",
    "for three days now",
    "for almost a week",
    "since last Monday",
    "for over a week",
    "for the past two weeks",
    "since the beginning of the month",
    "for nearly a month now",
    "since we moved in three months ago",
]

# =============================================================================
# 4 CONVERSATION STRUCTURES (up from 1 fixed template)
#
# Each produces the opening section of the transcript. The caller's
# tone, recurring status, and issue details are woven in differently
# depending on which structure is selected — preventing the model from
# learning a single template pattern.
# =============================================================================

def _structure_standard(issue, issue_data, asset, location, tone, is_recurring, tones):
    """V1-style: greeting -> report -> details -> location"""
    lines = ["Agent: Industrial Park Support Desk, how may I assist?"]

    if is_recurring:
        lines.append("Tenant: Hi, I'm calling again about an ongoing issue that hasn't been resolved.")
        lines.append(f"Tenant: {random.choice(tones['frustrated'])}")
    elif tone == "angry":
        lines.append("Tenant: I need to report a serious issue immediately.")
        lines.append(f"Tenant: {random.choice(tones['angry'])}")
    elif tone == "concerned":
        lines.append("Tenant: Hello, I need to report something that's been bothering us.")
    else:
        lines.append("Tenant: Hello, I need to report an issue.")

    lines.append(f"Tenant: We are experiencing {issue}.")
    lines.append(f"Tenant: {random.choice(issue_data['phrases'])}")

    lines.append("Agent: I'm very sorry to hear that. Let me get your details to assist you.")
    lines.append("Agent: May I have your unit information?")
    lines.append(f"Tenant: We're located in {location}, {asset.lower()} unit.")

    return lines


def _structure_direct(issue, issue_data, asset, location, tone, is_recurring, tones):
    """Direct: tenant leads with problem immediately, no pleasantries."""
    lines = ["Agent: Support Desk, good morning."]

    duration = random.choice(duration_phrases)
    lines.append(f"Tenant: Yes, we've had {issue} {duration}.")
    lines.append(f"Tenant: {random.choice(issue_data['phrases'])}")

    if is_recurring:
        lines.append("Tenant: I reported this before and nothing was done about it.")
        lines.append(f"Tenant: {random.choice(tones['frustrated'])}")

    lines.append("Agent: I understand. Can I confirm your location?")
    lines.append(f"Tenant: {location}, {asset.lower()}.")

    return lines


def _structure_narrative(issue, issue_data, asset, location, tone, is_recurring, tones):
    """Narrative: tenant tells a story with context before stating the issue."""
    lines = ["Agent: Industrial Park Support, how can I help?"]

    lines.append(f"Tenant: Good morning. I'm calling from our {asset.lower()} in {location}.")

    context_intros = [
        "So here's what happened.",
        "Let me explain the situation.",
        "I wanted to give you some background first.",
        "We've been dealing with something and I need your help.",
    ]
    lines.append(f"Tenant: {random.choice(context_intros)}")

    duration = random.choice(duration_phrases)
    lines.append(f"Tenant: {duration.capitalize()}, we started noticing {issue}.")
    lines.append(f"Tenant: {random.choice(issue_data['phrases'])}")

    if tone in ["angry", "frustrated"]:
        lines.append(f"Tenant: {random.choice(tones[tone])}")

    if is_recurring:
        lines.append("Tenant: And this isn't the first time. We've called about this before.")

    lines.append("Agent: Thank you for explaining. I'm logging this now.")

    return lines


def _structure_multi_exchange(issue, issue_data, asset, location, tone, is_recurring, tones):
    """Multi-exchange: agent asks clarifying questions, longer back-and-forth."""
    lines = ["Agent: Support Desk, how may I assist you today?"]

    lines.append("Tenant: Hi, I need to report a problem with our unit.")
    lines.append("Agent: Of course. Could you describe the issue?")
    lines.append(f"Tenant: We are dealing with {issue}.")
    lines.append("Agent: I see. How long has this been going on?")

    duration = random.choice(duration_phrases)
    lines.append(f"Tenant: It's been happening {duration}.")

    lines.append("Agent: And can you tell me which unit you're in?")
    lines.append(f"Tenant: We're in {location}, the {asset.lower()}.")

    lines.append("Agent: Is this affecting your ability to operate?")
    lines.append(f"Tenant: {random.choice(issue_data['phrases'])}")

    if is_recurring:
        lines.append("Agent: Have you reported this before?")
        lines.append("Tenant: Yes, multiple times actually.")
        lines.append(f"Tenant: {random.choice(tones['frustrated'])}")
    elif tone in ["frustrated", "angry"]:
        lines.append(f"Tenant: {random.choice(tones[tone])}")

    return lines


STRUCTURE_FUNCTIONS = [
    _structure_standard,
    _structure_direct,
    _structure_narrative,
    _structure_multi_exchange,
]

# =============================================================================
# SUPPORT TRANSCRIPT GENERATOR
# =============================================================================

def generate_support_transcript(issue_severity, is_recurring=False):
    """Generate a support call transcript with varied structure and content."""
    asset = random.choice(asset_types)
    location = random.choice(locations)
    tenant_tier = random.choice(tenant_tiers)

    issue_data = random.choice(service_issues[issue_severity])
    issue = issue_data["issue"]
    impact = issue_data["impact"]
    safety_concern = issue_data["safety_concern"]

    # Determine emotional tone based on severity and recurrence
    if is_recurring:
        tone = random.choice(["frustrated", "angry"])
    elif issue_severity == "critical":
        tone = random.choice(["angry", "frustrated", "concerned"])
    elif issue_severity == "high":
        tone = random.choice(["frustrated", "concerned", "professional"])
    elif issue_severity == "medium":
        tone = random.choice(["concerned", "professional"])
    else:
        tone = "professional"

    # Pick a random conversation structure
    structure_fn = random.choice(STRUCTURE_FUNCTIONS)
    lines = structure_fn(issue, issue_data, asset, location, tone, is_recurring, emotional_tones)

    # --- Continuation after the structure-specific opening ---

    # Recurring follow-up (only if not already handled by the structure)
    if is_recurring and structure_fn == _structure_standard:
        lines.append("Tenant: This was reported last week but nothing has been done.")
        lines.append("Agent: I apologize for that. Let me check the previous ticket.")
        lines.append(f"Tenant: {random.choice(emotional_tones['frustrated'])}")

    # Business impact statement (varies by severity)
    if impact in ["high", "medium-high"]:
        impact_statements = [
            "Tenant: This is seriously impacting our business operations.",
            "Tenant: We're losing money every day this goes unresolved.",
            "Tenant: Our staff can't work properly because of this.",
            "Tenant: This is affecting our ability to serve our clients.",
        ]
        lines.append(random.choice(impact_statements))

    # Safety concern escalation
    if safety_concern:
        safety_pairs = [
            ("Tenant: We also have safety concerns about this.",
             "Agent: I understand. Safety is our top priority."),
            ("Tenant: I'm worried someone could get hurt.",
             "Agent: That's very important. I'm flagging this as safety-critical."),
            ("Tenant: This is a health and safety risk for our staff.",
             "Agent: Absolutely. I'm escalating this to our safety team immediately."),
        ]
        pair = random.choice(safety_pairs)
        lines.append(pair[0])
        lines.append(pair[1])

    # Agent commitment (varies by severity)
    if issue_severity == "critical":
        commit_pairs = [
            ("Agent: I'm escalating this to our emergency response team immediately.",
             "Agent: You should receive a call within 15 minutes."),
            ("Agent: This is being treated as an emergency. I'm dispatching a team now.",
             "Agent: Someone will be on site within 30 minutes."),
            ("Agent: I've flagged this as critical priority.",
             "Agent: Our emergency team is being notified right now."),
        ]
    elif issue_severity == "high" or is_recurring:
        commit_pairs = [
            ("Agent: I'm marking this as high priority and escalating to the maintenance manager.",
             "Agent: We'll have someone on-site within the hour."),
            ("Agent: I've escalated this to our senior maintenance team.",
             "Agent: Expect a callback within 2 hours with an update."),
            ("Agent: This is going to the top of the queue.",
             "Agent: We'll get someone to your unit as soon as possible today."),
        ]
    elif issue_severity == "medium":
        commit_pairs = [
            ("Agent: I've logged your ticket and our team will address this.",
             "Agent: We'll update you within 24 hours."),
            ("Agent: I've created a maintenance request for this.",
             "Agent: You should hear back from us by tomorrow."),
            ("Agent: This has been noted and assigned to our facilities team.",
             "Agent: We aim to resolve medium-priority items within 48 hours."),
        ]
    else:
        commit_pairs = [
            ("Agent: I've logged this and our team will look into it.",
             "Agent: We'll get to it as part of our regular maintenance schedule."),
            ("Agent: Thank you for letting us know. I've added this to our task list.",
             "Agent: It should be addressed within the next few business days."),
            ("Agent: Noted. I'll pass this along to the appropriate team.",
             "Agent: They'll take care of it when they're next in the area."),
        ]

    pair = random.choice(commit_pairs)
    lines.append(pair[0])
    lines.append(pair[1])

    # Closing based on tone
    if tone in ["angry", "frustrated"]:
        close_pairs = [
            ("Tenant: I expect this to be resolved quickly.",
             "Agent: Absolutely. We'll keep you updated every step of the way."),
            ("Tenant: Please make sure this actually gets done this time.",
             "Agent: You have my word. I'll follow up personally."),
            ("Tenant: I really hope I don't have to call again about this.",
             "Agent: I understand your frustration. We'll make it a priority."),
        ]
        pair = random.choice(close_pairs)
        lines.append(pair[0])
        lines.append(pair[1])
    else:
        lines.append(f"Tenant: {random.choice(emotional_tones['satisfied'])}")
        agent_closings = [
            "Agent: You're welcome. We'll take care of this.",
            "Agent: Happy to help. We'll be in touch.",
            "Agent: Thank you for reporting this. We'll keep you updated.",
        ]
        lines.append(random.choice(agent_closings))

    return {
        "transcript": "\n".join(lines),
        "asset": asset,
        "location": location,
        "tenant_tier": tenant_tier,
        "issue_type": issue,
        "issue_severity": issue_severity,
        "business_impact": impact,
        "safety_concern": safety_concern,
        "is_recurring": is_recurring
    }


# =============================================================================
# LEASING INQUIRY GENERATOR — 5 inquiry types (up from 3)
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
            "What's the process for customizing the interior layout?",
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
            "What's included in the rent?",
        ],
        "tone": "casual"
    },
    {
        "type": "urgent_expansion",
        "questions": [
            "We need space urgently for expansion",
            "What's available immediately?",
            "Can we schedule a viewing today?",
            "What's the fastest we can sign?",
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
            "What's the tenant satisfaction rate here?",
        ],
        "tone": "formal"
    },
    {
        "type": "relocation_inquiry",
        "questions": [
            "We're relocating from another emirate, what do we need to know?",
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
    asset = random.choice(asset_types)
    location = random.choice(locations)
    size = random.choice([1500, 2500, 4000, 6000, 8000, 10000, 15000, 25000])
    inquiry_type = random.choice(leasing_inquiries)

    lines = ["Agent: Industrial Park Leasing Desk, good morning."]

    if inquiry_type["tone"] == "urgent":
        lines.append("Caller: Hello, I need to find space urgently.")
        lines.append("Caller: Our current location is no longer suitable.")
    elif inquiry_type["tone"] == "casual":
        lines.append("Caller: Hi there, I'm looking for some space to rent.")
    else:
        lines.append("Caller: Good morning, I'm calling to enquire about available space.")

    lines.append("Agent: Certainly. Are you looking for office, warehouse, or retail space?")
    lines.append(f"Caller: We need a {asset.lower()}.")

    lines.append("Agent: Do you have a preferred location within the park?")
    lines.append(f"Caller: Ideally in {location}.")

    lines.append("Agent: May I know your size requirement?")
    lines.append(f"Caller: Approximately {size} square feet.")

    # Ask questions based on inquiry type
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
            lines.append("Agent: We offer competitive rates with excellent facilities and a prime location in Dubai CommerCity.")
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

    # Closing
    if inquiry_type["tone"] == "urgent":
        lines.append("Caller: Can we schedule a viewing today?")
        lines.append("Agent: Absolutely. I can arrange a viewing this afternoon.")
        lines.append("Caller: Perfect, please send me the details.")
    else:
        lines.append("Caller: That sounds good. Please send the details.")
        lines.append("Agent: I'll email you the floor plans, pricing, and lease terms within the hour.")
        lines.append("Caller: Thank you.")

    return {
        "transcript": "\n".join(lines),
        "asset": asset,
        "location": location,
        "tenant_tier": "Prospective",
        "issue_type": inquiry_type["type"],
        "issue_severity": "N/A",
        "business_impact": "N/A",
        "safety_concern": False,
        "is_recurring": False
    }


# =============================================================================
# DATASET GENERATOR
# =============================================================================

def generate_dataset(num_records=1500):
    """
    Generate dataset with realistic distribution.

    Distribution:
        60% Tenant Support, 40% Leasing Inquiry
        Support severity: 10% critical, 25% high, 40% medium, 25% low
        Recurring rate: 40% critical, 35% high, 25% medium, 15% low
    """
    records = []

    num_support = int(num_records * 0.6)
    num_leasing = num_records - num_support

    num_critical = int(num_support * 0.10)
    num_high = int(num_support * 0.25)
    num_medium = int(num_support * 0.40)
    num_low = num_support - num_critical - num_high - num_medium

    support_calls = (
        [(generate_support_transcript("critical", random.random() < 0.4), "Tenant Support") for _ in range(num_critical)] +
        [(generate_support_transcript("high", random.random() < 0.35), "Tenant Support") for _ in range(num_high)] +
        [(generate_support_transcript("medium", random.random() < 0.25), "Tenant Support") for _ in range(num_medium)] +
        [(generate_support_transcript("low", random.random() < 0.15), "Tenant Support") for _ in range(num_low)]
    )

    leasing_calls = [(generate_leasing_transcript(), "Leasing Inquiry") for _ in range(num_leasing)]

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
            "call_id": f"IP-{timestamp.strftime('%Y%m')}-{i:05d}",
            "timestamp": timestamp.strftime("%Y-%m-%d %H:%M:%S"),
            "call_category": category,
            "tenant_tier": call_data["tenant_tier"],
            "asset_type": call_data["asset"],
            "location": call_data["location"],
            "issue_type": call_data["issue_type"],
            "issue_severity": call_data["issue_severity"],
            "business_impact": call_data["business_impact"],
            "safety_concern": call_data["safety_concern"],
            "is_recurring": call_data["is_recurring"],
            "transcript": call_data["transcript"]
        })

    return pd.DataFrame(records)


# =============================================================================
# MAIN
# =============================================================================

if __name__ == "__main__":
    import sys

    num_records = int(sys.argv[1]) if len(sys.argv) > 1 else 1500

    print(f"Generating {num_records} records with V2 synthesizer...")
    print(f"  Issue templates: {sum(len(v) for v in service_issues.values())} (up from 16)")
    print(f"  Conversation structures: {len(STRUCTURE_FUNCTIONS)} (up from 1)")
    print(f"  Emotional tone phrases: {sum(len(v) for v in emotional_tones.values())} (up from 27)")
    print(f"  Leasing inquiry types: {len(leasing_inquiries)} (up from 3)")
    print()

    df = generate_dataset(num_records)

    output_path = "Enhanced_DataSet_SentimentAnalysis.csv"
    df.to_csv(output_path, index=False)

    print(f"Dataset generated successfully!")
    print(f"Total records: {len(df)}")
    print(f"\nCategory Distribution:")
    print(df['call_category'].value_counts().to_string())
    print(f"\nIssue Severity Distribution (Support calls only):")
    support = df[df['call_category'] == 'Tenant Support']
    print(support['issue_severity'].value_counts().to_string())
    print(f"\nUnique issue types: {support['issue_type'].nunique()}")
    print(f"Recurring issues: {df['is_recurring'].sum()}")
    print(f"Safety concerns: {df['safety_concern'].sum()}")
    print(f"\nBusiness Impact Distribution (Support only):")
    print(support['business_impact'].value_counts().to_string())
    print(f"\nSaved to: {output_path}")
