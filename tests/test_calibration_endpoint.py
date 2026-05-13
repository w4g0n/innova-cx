"""
Unit tests for the department routing calibration endpoint logic.
Tests the probability normalisation math in isolation — no DB or server needed.
"""


def _compute_calibration_probs(rows, predicted):
    """Mirrors the logic in GET /api/internal/department-routing/calibration."""
    if not rows:
        return {"probabilities": {}}
    total = sum(int(r["cnt"]) for r in rows)
    probs = {r["approved_department"]: round(int(r["cnt"]) / total, 6) for r in rows}
    return {"probabilities": {predicted: probs}}


# ---------------------------------------------------------------------------
# Empty feedback table — should return empty probabilities
# ---------------------------------------------------------------------------

def test_empty_feedback_returns_empty_probabilities():
    result = _compute_calibration_probs([], predicted="IT")
    assert result == {"probabilities": {}}


# ---------------------------------------------------------------------------
# Single feedback row — 100% probability for that department
# ---------------------------------------------------------------------------

def test_single_row_gives_full_probability():
    rows = [{"approved_department": "IT", "cnt": 5}]
    result = _compute_calibration_probs(rows, predicted="IT")
    assert result == {"probabilities": {"IT": {"IT": 1.0}}}


# ---------------------------------------------------------------------------
# Multiple rows — probabilities normalise to 1.0
# ---------------------------------------------------------------------------

def test_multiple_rows_normalise_correctly():
    rows = [
        {"approved_department": "Maintenance", "cnt": 7},
        {"approved_department": "IT",          "cnt": 3},
    ]
    result = _compute_calibration_probs(rows, predicted="IT")
    probs = result["probabilities"]["IT"]
    assert abs(probs["Maintenance"] - 0.7) < 1e-5
    assert abs(probs["IT"]          - 0.3) < 1e-5
    assert abs(sum(probs.values()) - 1.0)  < 1e-5


# ---------------------------------------------------------------------------
# Predicted key is preserved correctly in response
# ---------------------------------------------------------------------------

def test_predicted_key_preserved():
    rows = [{"approved_department": "HR", "cnt": 1}]
    result = _compute_calibration_probs(rows, predicted="Facilities Management")
    assert "Facilities Management" in result["probabilities"]


# ---------------------------------------------------------------------------
# All departments can appear as corrections
# ---------------------------------------------------------------------------

def test_all_seven_departments_supported():
    departments = [
        "Facilities Management", "Legal & Compliance", "Safety & Security",
        "HR", "Leasing", "Maintenance", "IT",
    ]
    rows = [{"approved_department": d, "cnt": 1} for d in departments]
    result = _compute_calibration_probs(rows, predicted="IT")
    probs = result["probabilities"]["IT"]
    assert len(probs) == 7
    assert abs(sum(probs.values()) - 1.0) < 1e-5


# ---------------------------------------------------------------------------
# Probabilities are rounded to 6 decimal places (no float noise)
# ---------------------------------------------------------------------------

def test_probabilities_are_rounded():
    rows = [
        {"approved_department": "IT",          "cnt": 1},
        {"approved_department": "Maintenance", "cnt": 2},
    ]
    result = _compute_calibration_probs(rows, predicted="IT")
    probs = result["probabilities"]["IT"]
    for val in probs.values():
        # should have at most 6 decimal places
        assert round(val, 6) == val
