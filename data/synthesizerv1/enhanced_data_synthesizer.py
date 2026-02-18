import pandas as pd
import random
from datetime import datetime, timedelta

random.seed(101)

# Base Configuration
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

# Enhanced Issue Categories with severity and business impact
service_issues = {
    # Critical Issues - High business impact
    "critical": [
        {
            "issue": "complete power outage affecting entire floor",
            "impact": "high",
            "safety_concern": True,
            "phrases": ["all our systems are down", "we can't operate", "this is a major emergency"]
        },
        {
            "issue": "severe water flooding in the storage area",
            "impact": "high",
            "safety_concern": True,
            "phrases": ["our inventory is getting damaged", "water is everywhere", "this is destroying our stock"]
        },
        {
            "issue": "fire alarm system not functioning",
            "impact": "high",
            "safety_concern": True,
            "phrases": ["this is a safety violation", "we could face regulatory issues", "this needs immediate attention"]
        },
        {
            "issue": "main entrance security breach",
            "impact": "high",
            "safety_concern": True,
            "phrases": ["our security is compromised", "unauthorized access", "this is very concerning"]
        }
    ],
    # High Priority - Significant operational impact
    "high": [
        {
            "issue": "air conditioning completely broken during summer",
            "impact": "medium-high",
            "safety_concern": False,
            "phrases": ["it's unbearable to work", "our employees are complaining", "we might need to close early"]
        },
        {
            "issue": "persistent water leakage damaging office equipment",
            "impact": "medium-high",
            "safety_concern": False,
            "phrases": ["our computers are at risk", "this has been going on for days", "we've lost equipment already"]
        },
        {
            "issue": "loading dock gate stuck closed",
            "impact": "medium-high",
            "safety_concern": False,
            "phrases": ["we can't receive deliveries", "our operations are halted", "we're losing business"]
        },
        {
            "issue": "elevator breakdown in multi-story unit",
            "impact": "medium-high",
            "safety_concern": False,
            "phrases": ["it's difficult for staff", "we have mobility concerns", "this is very inconvenient"]
        }
    ],
    # Medium Priority - Moderate impact
    "medium": [
        {
            "issue": "air conditioning not cooling properly",
            "impact": "medium",
            "safety_concern": False,
            "phrases": ["it's uncomfortable", "the temperature isn't ideal", "we'd like this checked"]
        },
        {
            "issue": "parking gate malfunctioning intermittently",
            "impact": "medium",
            "safety_concern": False,
            "phrases": ["sometimes it works, sometimes it doesn't", "it's causing delays", "quite frustrating"]
        },
        {
            "issue": "slow internet connectivity in common areas",
            "impact": "medium",
            "safety_concern": False,
            "phrases": ["the WiFi is very slow", "we can't have meetings properly", "this affects our work"]
        },
        {
            "issue": "lighting issues in parking area",
            "impact": "medium",
            "safety_concern": False,
            "phrases": ["it's quite dark", "we're concerned about safety", "needs to be addressed"]
        }
    ],
    # Low Priority - Minor inconveniences
    "low": [
        {
            "issue": "minor noise disturbance from nearby unit",
            "impact": "low",
            "safety_concern": False,
            "phrases": ["it's a bit noisy", "just wanted to report this", "when you have time"]
        },
        {
            "issue": "cleaning services missed one day",
            "impact": "low",
            "safety_concern": False,
            "phrases": ["just letting you know", "not urgent", "when possible"]
        },
        {
            "issue": "lost and found item to report",
            "impact": "low",
            "safety_concern": False,
            "phrases": ["found something", "wondering if anyone reported", "not urgent"]
        },
        {
            "issue": "request for additional waste bins",
            "impact": "low",
            "safety_concern": False,
            "phrases": ["would be helpful", "when convenient", "just a request"]
        }
    ]
}

# Leasing inquiry types with different tones
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
            "What are the payment terms?"
        ],
        "tone": "formal"
    },
    {
        "type": "casual_quick",
        "questions": [
            "How much is the rent?",
            "When can we move in?",
            "Is parking included?",
            "Can you send me the details?"
        ],
        "tone": "casual"
    },
    {
        "type": "urgent_expansion",
        "questions": [
            "We need space urgently for expansion",
            "What's available immediately?",
            "Can we schedule a viewing today?",
            "What's the fastest we can sign?"
        ],
        "tone": "urgent"
    }
]

# Emotional tone phrases for different sentiment levels
emotional_tones = {
    "frustrated": [
        "This is extremely frustrating.",
        "I've been calling for days.",
        "This is unacceptable.",
        "We're very disappointed.",
        "I need to speak with a manager.",
        "This is the third time I'm reporting this."
    ],
    "angry": [
        "This is completely unacceptable!",
        "I'm very upset about this situation.",
        "We're considering legal action.",
        "This is a breach of our agreement.",
        "I want this escalated immediately!",
        "We're paying premium rent for this?"
    ],
    "concerned": [
        "I'm quite worried about this.",
        "This could become a bigger problem.",
        "We need this addressed soon.",
        "I'm concerned about the implications.",
        "This is affecting our operations."
    ],
    "professional": [
        "I'd like to report an issue.",
        "We need assistance with this matter.",
        "Could you please look into this?",
        "I appreciate your help with this.",
        "Thank you for your attention to this."
    ],
    "satisfied": [
        "Thank you for your quick response.",
        "I appreciate the help.",
        "That sounds good.",
        "Great, thank you.",
        "Perfect, that works for us."
    ]
}

def generate_support_transcript(issue_severity, is_recurring=False):
    """Generate a support call transcript with varying emotional tones and complexity"""
    asset = random.choice(asset_types)
    location = random.choice(locations)
    tenant_tier = random.choice(tenant_tiers)
    
    # Select issue based on severity
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
    
    lines = [
        "Agent: Industrial Park Support Desk, how may I assist?",
    ]
    
    # Opening based on tone and recurrence
    if is_recurring:
        lines.append(f"Tenant: Hi, I'm calling again about an ongoing issue that hasn't been resolved.")
        lines.append(f"Tenant: {random.choice(emotional_tones['frustrated'])}")
    elif tone == "angry":
        lines.append(f"Tenant: I need to report a serious issue immediately.")
        lines.append(f"Tenant: {random.choice(emotional_tones['angry'])}")
    else:
        lines.append(f"Tenant: Hello, I need to report an issue.")
    
    # Describe the issue
    lines.append(f"Tenant: We are experiencing {issue}.")
    
    # Add issue-specific phrase
    lines.append(f"Tenant: {random.choice(issue_data['phrases'])}.")
    
    # Agent response
    lines.append("Agent: I'm very sorry to hear that. Let me get your details to assist you.")
    lines.append("Agent: May I have your unit information?")
    
    lines.append(f"Tenant: We're located in {location}, {asset.lower()} unit.")
    
    # If recurring, add history
    if is_recurring:
        lines.append("Tenant: This was reported last week but nothing has been done.")
        lines.append("Agent: I apologize for that. Let me check the previous ticket.")
        lines.append(f"Tenant: {random.choice(emotional_tones['frustrated'])}")
    
    # Business impact statement
    if impact in ["high", "medium-high"]:
        lines.append("Tenant: This is seriously impacting our business operations.")
    
    # Safety concern escalation
    if safety_concern:
        lines.append("Tenant: We also have safety concerns about this.")
        lines.append("Agent: I understand. Safety is our top priority.")
    
    # Agent commitment
    if issue_severity == "critical":
        lines.append("Agent: I'm escalating this to our emergency response team immediately.")
        lines.append("Agent: You should receive a call within 15 minutes.")
    elif issue_severity == "high" or is_recurring:
        lines.append("Agent: I'm marking this as high priority and escalating to the maintenance manager.")
        lines.append("Agent: We'll have someone on-site within the hour.")
    else:
        lines.append("Agent: I've logged your ticket and our team will address this.")
        lines.append("Agent: We'll update you within 24 hours.")
    
    # Closing based on tone
    if tone in ["angry", "frustrated"]:
        lines.append("Tenant: I expect this to be resolved quickly.")
        lines.append("Agent: Absolutely. We'll keep you updated every step of the way.")
    else:
        lines.append(f"Tenant: {random.choice(emotional_tones['satisfied'])}")
        lines.append("Agent: You're welcome. We'll take care of this.")
    
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

def generate_leasing_transcript():
    """Generate a leasing inquiry transcript with varying tones"""
    asset = random.choice(asset_types)
    location = random.choice(locations)
    size = random.choice([2500, 4000, 6000, 10000, 15000, 25000])
    inquiry_type = random.choice(leasing_inquiries)
    
    lines = [
        "Agent: Industrial Park Leasing Desk, good morning.",
    ]
    
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
        # Agent provides generic positive response
        if "rate" in question.lower() or "how much" in question.lower():
            lines.append(f"Agent: The rate varies by location and specifications. I can provide detailed pricing.")
        elif "when" in question.lower():
            lines.append("Agent: We have immediate availability in several units.")
        elif "parking" in question.lower():
            lines.append("Agent: Parking allocation depends on the unit size, typically 1 space per 1000 sq ft.")
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
        "tenant_tier": "Prospective",  # Not yet a tenant
        "issue_type": inquiry_type["type"],
        "issue_severity": "N/A",
        "business_impact": "N/A",
        "safety_concern": False,
        "is_recurring": False
    }

def generate_dataset(num_records=1000):
    """Generate enhanced dataset with realistic distribution"""
    records = []
    
    # Define distribution
    # 60% Support, 40% Leasing
    num_support = int(num_records * 0.6)
    num_leasing = num_records - num_support
    
    # Support severity distribution
    # Critical: 10%, High: 25%, Medium: 40%, Low: 25%
    num_critical = int(num_support * 0.10)
    num_high = int(num_support * 0.25)
    num_medium = int(num_support * 0.40)
    num_low = num_support - num_critical - num_high - num_medium
    
    # Generate support calls
    support_calls = (
        [(generate_support_transcript("critical", random.random() < 0.4), "Tenant Support") for _ in range(num_critical)] +
        [(generate_support_transcript("high", random.random() < 0.35), "Tenant Support") for _ in range(num_high)] +
        [(generate_support_transcript("medium", random.random() < 0.25), "Tenant Support") for _ in range(num_medium)] +
        [(generate_support_transcript("low", random.random() < 0.15), "Tenant Support") for _ in range(num_low)]
    )
    
    # Generate leasing calls
    leasing_calls = [(generate_leasing_transcript(), "Leasing Inquiry") for _ in range(num_leasing)]
    
    # Combine and shuffle
    all_calls = support_calls + leasing_calls
    random.shuffle(all_calls)
    
    # Create timestamps (last 90 days)
    start_date = datetime.now() - timedelta(days=90)
    
    for i, (call_data, category) in enumerate(all_calls, 1):
        # Generate realistic timestamp
        timestamp = start_date + timedelta(
            days=random.randint(0, 90),
            hours=random.randint(8, 18),  # Business hours
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

# Generate the dataset
if __name__ == "__main__":
    print("Generating enhanced dataset...")
    df = generate_dataset(1000)
    
    # Save to CSV
    output_path = "/mnt/user-data/outputs/Enhanced_DataSet_SentimentAnalysis.csv"
    df.to_csv(output_path, index=False)
    
    print(f"\nDataset generated successfully!")
    print(f"Total records: {len(df)}")
    print(f"\nCategory Distribution:")
    print(df['call_category'].value_counts())
    print(f"\nIssue Severity Distribution (Support calls only):")
    print(df[df['call_category'] == 'Tenant Support']['issue_severity'].value_counts())
    print(f"\nRecurring Issues: {df['is_recurring'].sum()}")
    print(f"Safety Concerns: {df['safety_concern'].sum()}")
    print(f"\nSample saved to: {output_path}")
