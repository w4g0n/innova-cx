import random
import pandas as pd

TOTAL_ROWS = 5000
COMPLAINT_RATIO = 0.6
LOW_RATIO = 0.35
MEDIUM_RATIO = 0.40
HIGH_RATIO = 0.25
BASE_SAFETY_PROB = 0.28

# -----------------------------
# ISSUE CATEGORIES
# -----------------------------

COMPLAINT_CATEGORIES = [
    "HVAC system malfunction",
    "power instability",
    "water leakage",
    "internet disruption",
    "security concern",
    "billing discrepancy",
    "maintenance backlog",
    "cleaning deficiency",
    "parking allocation issue",
    "access control malfunction",
    "noise disturbance",
    "elevator outage",
    "plumbing blockage",
    "delivery delay",
    "staff conduct issue",
    "loading dock obstruction",
    "lighting failure",
    "server room overheating",
    "unauthorized entry",
    "fire alarm fault"
]

INQUIRY_CATEGORIES = [
    "lease renewal terms",
    "invoice clarification",
    "facility reservation",
    "operating schedule",
    "insurance documentation",
    "unit expansion options",
    "parking regulations",
    "accepted payment methods",
    "compliance procedures",
    "visitor access protocol",
    "service agreement details",
    "renovation approval process",
    "inspection timeline",
    "utility activation process",
    "signage approval guidelines",
    "internet provider policies",
    "visitor pass issuance",
    "storage usage rules",
    "coverage limitations",
    "renewal deadlines"
]

# -----------------------------
# NARRATIVE BUILDING BLOCKS
# -----------------------------

GREETINGS = [
    "Good afternoon,",
    "Hello,",
    "We hope you are doing well.",
    "We are writing to bring this to your attention."
]

BACKGROUND = [
    "Over the past few days, we have observed that",
    "Recently, our team noticed that",
    "For some time now, it has become apparent that",
    "During our regular operations, we identified that"
]

CLARIFICATIONS = [
    "This appears to be affecting multiple areas within the unit.",
    "The issue seems more noticeable during peak hours.",
    "It is not isolated to a single occurrence.",
    "The condition has not resolved despite initial adjustments."
]

EXPECTATION = [
    "We would appreciate your assistance in resolving this matter.",
    "We trust this can be addressed promptly.",
    "Kindly review and advise on the next steps.",
    "We look forward to your support in resolving this."
]

CONSEQUENCE_LOW = [
    "While this has caused minor inconvenience, operations are still ongoing.",
    "The disruption remains limited at this stage.",
    "The impact has been manageable so far."
]

CONSEQUENCE_MEDIUM = [
    "This has started to affect our daily workflow and coordination.",
    "Operational efficiency has been noticeably impacted.",
    "There have been delays in routine activities."
]

CONSEQUENCE_HIGH = [
    "As a result, our operations have come to a halt.",
    "We are currently unable to continue normal business activities.",
    "This has severely disrupted our operational continuity."
]

SAFETY_RISK = [
    "Additionally, there is a potential safety risk involved.",
    "There are visible hazards that could pose injury.",
    "This situation raises significant safety concerns.",
    "Exposed elements present a possible danger."
]

SAFETY_NONE = [
    "At this time, there does not appear to be any immediate safety risk.",
    "Fortunately, no hazards have been identified so far."
]

# -----------------------------
# GENERATORS
# -----------------------------

def generate_complaint(ticket_id):
    issue = random.choice(COMPLAINT_CATEGORIES)

    sentences = []

    if random.random() < 0.8:
        sentences.append(random.choice(GREETINGS))

    sentences.append(
        f"{random.choice(BACKGROUND)} the {issue.lower()} persists within our premises."
    )

    if random.random() < 0.7:
        sentences.append(random.choice(CLARIFICATIONS))

    # Impact determined by consequence language
    roll = random.random()
    if roll < LOW_RATIO:
        impact = "low"
        sentences.append(random.choice(CONSEQUENCE_LOW))
    elif roll < LOW_RATIO + MEDIUM_RATIO:
        impact = "medium"
        sentences.append(random.choice(CONSEQUENCE_MEDIUM))
    else:
        impact = "high"
        sentences.append(random.choice(CONSEQUENCE_HIGH))

    # Curved but non-deterministic safety distribution
    if impact == "low":
        safety_prob = random.uniform(0.05, 0.18)
    elif impact == "medium":
        safety_prob = random.uniform(0.15, 0.35)
    else:  # high
        safety_prob = random.uniform(0.35, 0.65)
    safety = random.random() < safety_prob

    sentences.append(random.choice(EXPECTATION))

    text = " ".join(sentences)

    return {
        "ticket_id": f"cx{ticket_id:05d}",
        "ticket_type": "Complaint",
        "ticket_details": text,
        "issue_category": issue,
        "business_impact": impact,
        "safety_concern": safety
    }


def generate_inquiry(ticket_id):
    issue = random.choice(INQUIRY_CATEGORIES)

    sentences = []

    if random.random() < 0.8:
        sentences.append(random.choice(GREETINGS))

    sentences.append(
        f"We would like clarification regarding {issue}."
    )

    if random.random() < 0.7:
        sentences.append(
            "This information is important for our internal planning."
        )

    sentences.append(
        "Kindly advise us on the appropriate steps moving forward."
    )

    text = " ".join(sentences)

    return {
        "ticket_id": f"cx{ticket_id:05d}",
        "ticket_type": "Inquiry",
        "ticket_details": text,
        "issue_category": issue,
        "business_impact": None,
        "safety_concern": None
    }

# -----------------------------
# MAIN
# -----------------------------

rows = []
num_complaints = int(TOTAL_ROWS * COMPLAINT_RATIO)

for i in range(TOTAL_ROWS):
    if i < num_complaints:
        rows.append(generate_complaint(i))
    else:
        rows.append(generate_inquiry(i))

random.shuffle(rows)

df = pd.DataFrame(rows)
df = df.drop_duplicates(subset=["ticket_details"]).reset_index(drop=True)

df.to_csv("synthetic_dataset.csv", index=False)

print("Total rows:", len(df))
print(df["ticket_type"].value_counts())
print(df["business_impact"].value_counts(dropna=False))
print(df["safety_concern"].value_counts(dropna=False))