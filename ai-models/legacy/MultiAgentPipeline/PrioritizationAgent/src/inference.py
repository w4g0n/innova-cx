"""
Prioritization Agent - Fuzzy Logic Engine
==========================================
Part of the Adaptable MultiAgentic System (V7)

Inputs (from upstream agents):
    - sentiment_score  : float, range [-1, 1]
    - issue_severity   : str, one of ['low', 'medium', 'high', 'critical']
    - issue_urgency    : str, one of ['low', 'medium', 'high', 'critical']
    - business_impact  : str, one of ['low', 'medium', 'high']
    - safety_concern   : bool
    - is_recurring     : bool
    - ticket_type      : str, one of ['complaint', 'inquiry']

Output:
    - priority         : str, one of ['low', 'medium', 'high', 'critical']

Install dependencies:
    pip install scikit-fuzzy numpy
"""

import numpy as np
import skfuzzy as fuzz
from skfuzzy import control as ctrl


# =============================================================================
# STEP 1: Define Universes of Discourse
# =============================================================================

# Sentiment: -1 (very negative) to 1 (very positive)
sentiment_universe = np.arange(-1, 1.05, 0.05)

# Severity, Urgency, Business Impact: 0=low, 1=medium, 2=high, 3=critical
severity_universe = np.arange(0, 4, 1)
urgency_universe = np.arange(0, 4, 1)
impact_universe = np.arange(0, 3, 1)  # no 'critical' for business impact

# Priority output: 0=low, 1=medium, 2=high, 3=critical
priority_universe = np.arange(0, 4, 1)


# =============================================================================
# STEP 2: Define Antecedents (Inputs) and Consequent (Output)
# =============================================================================

sentiment = ctrl.Antecedent(sentiment_universe, "sentiment")
issue_severity = ctrl.Antecedent(severity_universe, "issue_severity")
issue_urgency = ctrl.Antecedent(urgency_universe, "issue_urgency")
business_impact = ctrl.Antecedent(impact_universe, "business_impact")
priority = ctrl.Consequent(priority_universe, "priority", defuzzify_method="centroid")


# =============================================================================
# STEP 3: Define Membership Functions
# =============================================================================

# --- Sentiment ---
sentiment["negative"] = fuzz.trapmf(sentiment_universe, [-1, -1, -0.25, 0.0])
sentiment["neutral"] = fuzz.trimf(sentiment_universe, [-0.25, 0.0, 0.25])
sentiment["positive"] = fuzz.trapmf(sentiment_universe, [0.0, 0.25, 1.0, 1.0])

# --- Issue Severity (0=low, 1=medium, 2=high, 3=critical) ---
issue_severity["low"] = fuzz.trimf(severity_universe, [0, 0, 1])
issue_severity["medium"] = fuzz.trimf(severity_universe, [0, 1, 2])
issue_severity["high"] = fuzz.trimf(severity_universe, [1, 2, 3])
issue_severity["critical"] = fuzz.trimf(severity_universe, [2, 3, 3])

# --- Issue Urgency (same scale) ---
issue_urgency["low"] = fuzz.trimf(urgency_universe, [0, 0, 1])
issue_urgency["medium"] = fuzz.trimf(urgency_universe, [0, 1, 2])
issue_urgency["high"] = fuzz.trimf(urgency_universe, [1, 2, 3])
issue_urgency["critical"] = fuzz.trimf(urgency_universe, [2, 3, 3])

# --- Business Impact (0=low, 1=medium, 2=high) ---
business_impact["low"] = fuzz.trimf(impact_universe, [0, 0, 1])
business_impact["medium"] = fuzz.trimf(impact_universe, [0, 1, 2])
business_impact["high"] = fuzz.trimf(impact_universe, [1, 2, 2])

# --- Priority Output (0=low, 1=medium, 2=high, 3=critical) ---
priority["low"] = fuzz.trimf(priority_universe, [0, 0, 1])
priority["medium"] = fuzz.trimf(priority_universe, [0, 1, 2])
priority["high"] = fuzz.trimf(priority_universe, [1, 2, 3])
priority["critical"] = fuzz.trimf(priority_universe, [2, 3, 3])


# =============================================================================
# STEP 4: Define Fuzzy Rules
# =============================================================================

rules = [
    # -------------------------------------------------------------------------
    # GROUP 1: Base rules — severity + urgency fully aligned
    # -------------------------------------------------------------------------
    ctrl.Rule(issue_severity["critical"] & issue_urgency["critical"], priority["critical"]),
    ctrl.Rule(issue_severity["high"] & issue_urgency["high"], priority["high"]),
    ctrl.Rule(issue_severity["medium"] & issue_urgency["medium"], priority["medium"]),
    ctrl.Rule(issue_severity["low"] & issue_urgency["low"], priority["low"]),
    # -------------------------------------------------------------------------
    # GROUP 2: Mismatch rules — severity + urgency disagree (1/2)
    # critical + high → critical
    # -------------------------------------------------------------------------
    ctrl.Rule(issue_severity["critical"] & issue_urgency["high"], priority["critical"]),
    ctrl.Rule(issue_severity["high"] & issue_urgency["critical"], priority["critical"]),
    # critical + anything else (medium/low) → high
    ctrl.Rule(issue_severity["critical"] & issue_urgency["medium"], priority["high"]),
    ctrl.Rule(issue_severity["medium"] & issue_urgency["critical"], priority["high"]),
    ctrl.Rule(issue_severity["critical"] & issue_urgency["low"], priority["high"]),
    ctrl.Rule(issue_severity["low"] & issue_urgency["critical"], priority["high"]),
    # high + medium → high
    ctrl.Rule(issue_severity["high"] & issue_urgency["medium"], priority["high"]),
    ctrl.Rule(issue_severity["medium"] & issue_urgency["high"], priority["high"]),
    # high + anything else (low) → medium
    ctrl.Rule(issue_severity["high"] & issue_urgency["low"], priority["medium"]),
    ctrl.Rule(issue_severity["low"] & issue_urgency["high"], priority["medium"]),
    # medium + low → medium
    ctrl.Rule(issue_severity["medium"] & issue_urgency["low"], priority["medium"]),
    ctrl.Rule(issue_severity["low"] & issue_urgency["medium"], priority["medium"]),
    # -------------------------------------------------------------------------
    # GROUP 3: Business impact rules (3-way combination)
    # -------------------------------------------------------------------------
    # 3/3 high → critical
    ctrl.Rule(
        business_impact["high"] & issue_severity["high"] & issue_urgency["high"],
        priority["critical"],
    ),
    # 2/3 high + 1/3 medium → high
    ctrl.Rule(
        business_impact["high"] & issue_severity["high"] & issue_urgency["medium"],
        priority["high"],
    ),
    ctrl.Rule(
        business_impact["high"] & issue_severity["medium"] & issue_urgency["high"],
        priority["high"],
    ),
    ctrl.Rule(
        business_impact["medium"] & issue_severity["high"] & issue_urgency["high"],
        priority["high"],
    ),
    # 2/3 high + 1/3 low → high
    ctrl.Rule(
        business_impact["high"] & issue_severity["high"] & issue_urgency["low"],
        priority["high"],
    ),
    ctrl.Rule(
        business_impact["high"] & issue_severity["low"] & issue_urgency["high"],
        priority["high"],
    ),
    ctrl.Rule(
        business_impact["low"] & issue_severity["high"] & issue_urgency["high"],
        priority["high"],
    ),
    # 1/3 high + 2/3 medium → medium
    ctrl.Rule(
        business_impact["high"] & issue_severity["medium"] & issue_urgency["medium"],
        priority["medium"],
    ),
    ctrl.Rule(
        business_impact["medium"] & issue_severity["high"] & issue_urgency["medium"],
        priority["medium"],
    ),
    ctrl.Rule(
        business_impact["medium"] & issue_severity["medium"] & issue_urgency["high"],
        priority["medium"],
    ),
    # 1/3 high + 2/3 low → medium
    ctrl.Rule(
        business_impact["high"] & issue_severity["low"] & issue_urgency["low"],
        priority["medium"],
    ),
    ctrl.Rule(
        business_impact["low"] & issue_severity["high"] & issue_urgency["low"],
        priority["medium"],
    ),
    ctrl.Rule(
        business_impact["low"] & issue_severity["low"] & issue_urgency["high"],
        priority["medium"],
    ),
    # 3/3 medium → high
    ctrl.Rule(
        business_impact["medium"] & issue_severity["medium"] & issue_urgency["medium"],
        priority["high"],
    ),
    # 2/3 medium + 1/3 low → medium
    ctrl.Rule(
        business_impact["medium"] & issue_severity["medium"] & issue_urgency["low"],
        priority["medium"],
    ),
    ctrl.Rule(
        business_impact["medium"] & issue_severity["low"] & issue_urgency["medium"],
        priority["medium"],
    ),
    ctrl.Rule(
        business_impact["low"] & issue_severity["medium"] & issue_urgency["medium"],
        priority["medium"],
    ),
    # 1/3 medium + 2/3 low → low
    ctrl.Rule(
        business_impact["medium"] & issue_severity["low"] & issue_urgency["low"],
        priority["low"],
    ),
    ctrl.Rule(
        business_impact["low"] & issue_severity["medium"] & issue_urgency["low"],
        priority["low"],
    ),
    ctrl.Rule(
        business_impact["low"] & issue_severity["low"] & issue_urgency["medium"],
        priority["low"],
    ),
    # 3/3 low → low
    ctrl.Rule(
        business_impact["low"] & issue_severity["low"] & issue_urgency["low"],
        priority["low"],
    ),
    # -------------------------------------------------------------------------
    # GROUP 4: Sentiment — influences output direction
    # -------------------------------------------------------------------------
    ctrl.Rule(sentiment["negative"], priority["high"]),  # negative → boosts toward high
    ctrl.Rule(sentiment["positive"], priority["low"]),  # positive → pulls toward low
    # neutral → no rule fired, no effect
]


# =============================================================================
# STEP 5: Build Control System
# =============================================================================

priority_ctrl = ctrl.ControlSystem(rules)


# =============================================================================
# STEP 6: Helper - Convert categorical inputs to numeric
# =============================================================================

SEVERITY_MAP = {"low": 0, "medium": 1, "high": 2, "critical": 3}
IMPACT_MAP = {"low": 0, "medium": 1, "high": 2}
PRIORITY_LEVELS = ["low", "medium", "high", "critical"]


def _level_to_int(priority_label: str) -> int:
    return PRIORITY_LEVELS.index(priority_label)


def _int_to_level(n: int) -> str:
    n = max(0, min(3, n))  # hard cap between low and critical
    return PRIORITY_LEVELS[n]


# =============================================================================
# STEP 7: Main Prioritization Function
# =============================================================================

def prioritize(
    sentiment_score: float,
    issue_severity_val: str,
    issue_urgency_val: str,
    business_impact_val: str,
    safety_concern: bool,
    is_recurring: bool,
    ticket_type: str,
) -> dict:
    """
    Run the fuzzy prioritization engine.

    Returns a dict with:
        - raw_score    : float (0-3), the raw fuzzy output before modifiers
        - base_priority: str, priority before boolean/type modifiers
        - final_priority: str, priority after all modifiers applied
        - modifiers_applied: list of strings explaining what changed
    """
    sim = ctrl.ControlSystemSimulation(priority_ctrl)

    # --- Feed fuzzy inputs ---
    sim.input["sentiment"] = float(sentiment_score)
    sim.input["issue_severity"] = SEVERITY_MAP[issue_severity_val.lower()]
    sim.input["issue_urgency"] = SEVERITY_MAP[issue_urgency_val.lower()]
    sim.input["business_impact"] = IMPACT_MAP[business_impact_val.lower()]

    sim.compute()
    raw_score = sim.output["priority"]

    # --- Convert raw score to base priority label ---
    base_level = int(round(raw_score))
    base_priority = _int_to_level(base_level)

    # --- Apply modifiers ---
    modifier = 0
    modifiers_applied = []

    if is_recurring:
        modifier += 1
        modifiers_applied.append("is_recurring=True -> +1")

    if ticket_type.lower() == "inquiry":
        modifier -= 1
        modifiers_applied.append("ticket_type=Inquiry -> -1")

    # Sentiment discrete modifier (as requested)
    if sentiment_score < -0.25:
        modifier += 1
        modifiers_applied.append("sentiment=Negative -> +1")
    elif sentiment_score > 0.25:
        modifier -= 1
        modifiers_applied.append("sentiment=Positive -> -1")
    else:
        modifiers_applied.append("sentiment=Neutral -> 0")

    final_level = base_level + modifier
    final_priority = _int_to_level(final_level)

    # safety_concern: enforce minimum of 'high'
    if safety_concern:
        modifiers_applied.append("safety_concern=True -> minimum High")
        if _level_to_int(final_priority) < _level_to_int("high"):
            final_priority = "high"

    # Hard caps
    final_priority = _int_to_level(max(0, min(3, _level_to_int(final_priority))))

    return {
        "raw_score": round(raw_score, 3),
        "base_priority": base_priority,
        "final_priority": final_priority,
        "modifiers_applied": modifiers_applied if modifiers_applied else ["none"],
    }


# =============================================================================
# STEP 8: Example Usage
# =============================================================================

if __name__ == "__main__":
    test_cases = [
        # --- Base alignment rules ---
        {
            "label": "[Base] Critical severity + urgency -> Critical",
            "inputs": dict(
                sentiment_score=0.0,
                issue_severity_val="critical",
                issue_urgency_val="critical",
                business_impact_val="medium",
                safety_concern=False,
                is_recurring=False,
                ticket_type="complaint",
            ),
        },
        {
            "label": "[Base] High severity + urgency -> High",
            "inputs": dict(
                sentiment_score=0.0,
                issue_severity_val="high",
                issue_urgency_val="high",
                business_impact_val="low",
                safety_concern=False,
                is_recurring=False,
                ticket_type="complaint",
            ),
        },
        {
            "label": "[Base] Low severity + urgency -> Low",
            "inputs": dict(
                sentiment_score=0.0,
                issue_severity_val="low",
                issue_urgency_val="low",
                business_impact_val="low",
                safety_concern=False,
                is_recurring=False,
                ticket_type="complaint",
            ),
        },
        # --- Mismatch rules ---
        {
            "label": "[Mismatch] Critical severity + High urgency -> Critical",
            "inputs": dict(
                sentiment_score=0.0,
                issue_severity_val="critical",
                issue_urgency_val="high",
                business_impact_val="low",
                safety_concern=False,
                is_recurring=False,
                ticket_type="complaint",
            ),
        },
        {
            "label": "[Mismatch] Critical severity + Low urgency -> High",
            "inputs": dict(
                sentiment_score=0.0,
                issue_severity_val="critical",
                issue_urgency_val="low",
                business_impact_val="low",
                safety_concern=False,
                is_recurring=False,
                ticket_type="complaint",
            ),
        },
        {
            "label": "[Mismatch] High severity + Medium urgency -> High",
            "inputs": dict(
                sentiment_score=0.0,
                issue_severity_val="high",
                issue_urgency_val="medium",
                business_impact_val="low",
                safety_concern=False,
                is_recurring=False,
                ticket_type="complaint",
            ),
        },
        {
            "label": "[Mismatch] Medium severity + Low urgency -> Medium",
            "inputs": dict(
                sentiment_score=0.0,
                issue_severity_val="medium",
                issue_urgency_val="low",
                business_impact_val="low",
                safety_concern=False,
                is_recurring=False,
                ticket_type="complaint",
            ),
        },
        # --- Business impact rules ---
        {
            "label": "[BIZ] 3/3 High -> Critical",
            "inputs": dict(
                sentiment_score=0.0,
                issue_severity_val="high",
                issue_urgency_val="high",
                business_impact_val="high",
                safety_concern=False,
                is_recurring=False,
                ticket_type="complaint",
            ),
        },
        {
            "label": "[BIZ] 3/3 Medium -> High",
            "inputs": dict(
                sentiment_score=0.0,
                issue_severity_val="medium",
                issue_urgency_val="medium",
                business_impact_val="medium",
                safety_concern=False,
                is_recurring=False,
                ticket_type="complaint",
            ),
        },
        {
            "label": "[BIZ] 1/3 High + 2/3 Low -> Medium",
            "inputs": dict(
                sentiment_score=0.0,
                issue_severity_val="high",
                issue_urgency_val="low",
                business_impact_val="low",
                safety_concern=False,
                is_recurring=False,
                ticket_type="complaint",
            ),
        },
        # --- Modifiers ---
        {
            "label": "[MOD] Safety concern floors at High (was Low)",
            "inputs": dict(
                sentiment_score=0.0,
                issue_severity_val="low",
                issue_urgency_val="low",
                business_impact_val="low",
                safety_concern=True,
                is_recurring=False,
                ticket_type="complaint",
            ),
        },
        {
            "label": "[MOD] Recurring +1: Medium -> High",
            "inputs": dict(
                sentiment_score=0.0,
                issue_severity_val="medium",
                issue_urgency_val="medium",
                business_impact_val="low",
                safety_concern=False,
                is_recurring=True,
                ticket_type="complaint",
            ),
        },
        {
            "label": "[MOD] Inquiry -1: High -> Medium",
            "inputs": dict(
                sentiment_score=0.0,
                issue_severity_val="high",
                issue_urgency_val="high",
                business_impact_val="low",
                safety_concern=False,
                is_recurring=False,
                ticket_type="inquiry",
            ),
        },
        {
            "label": "[MOD] Negative sentiment +1, recurring +1, inquiry -1 -> net +1",
            "inputs": dict(
                sentiment_score=-0.7,
                issue_severity_val="medium",
                issue_urgency_val="medium",
                business_impact_val="low",
                safety_concern=False,
                is_recurring=True,
                ticket_type="inquiry",
            ),
        },
        {
            "label": "[MOD] Critical already — recurring cannot exceed Critical",
            "inputs": dict(
                sentiment_score=-0.9,
                issue_severity_val="critical",
                issue_urgency_val="critical",
                business_impact_val="high",
                safety_concern=False,
                is_recurring=True,
                ticket_type="complaint",
            ),
        },
    ]

    for case in test_cases:
        print(f"\n{'=' * 60}")
        print(f"  {case['label']}")
        print(f"{'=' * 60}")
        result = prioritize(**case["inputs"])
        print(f"  Raw fuzzy score  : {result['raw_score']}")
        print(f"  Base priority    : {result['base_priority']}")
        print(f"  Modifiers        : {', '.join(result['modifiers_applied'])}")
        print(f"  FINAL PRIORITY   : {result['final_priority'].upper()}")
