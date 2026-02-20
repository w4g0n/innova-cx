"""
Compatibility shim for data_preparation.py.

data_preparation.py imports get_keyword_vocabulary from this module.
The keyword vocabulary is still needed to generate proxy_keywords_str
in the CSV (even though train_production.py no longer reads that column).
"""

from typing import List

KEYWORD_VOCABULARY = [
    # HVAC (8)
    "air conditioning", "AC", "heating", "temperature",
    "cooling", "HVAC", "thermostat", "ventilation",

    # Plumbing (9)
    "water", "leak", "flooding", "drain", "pipe",
    "plumbing", "toilet", "sink", "faucet",

    # Electrical (8)
    "power", "electricity", "lights", "lighting",
    "electrical", "outlet", "circuit", "power outage",

    # Elevators (2)
    "elevator", "lift",

    # Parking (3)
    "parking", "gate", "barrier",

    # Security (4)
    "security", "alarm", "fire alarm", "safety",

    # Maintenance (4)
    "cleaning", "maintenance", "trash", "garbage",

    # Noise (3)
    "noise", "loud", "disturbance",

    # Internet (4)
    "internet", "WiFi", "connectivity", "network",

    # Status words (5)
    "broken", "not working", "repair", "emergency", "urgent"
]


def get_keyword_vocabulary() -> List[str]:
    return KEYWORD_VOCABULARY
