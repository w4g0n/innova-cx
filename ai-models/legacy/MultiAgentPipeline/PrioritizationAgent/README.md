# Prioritization Agent (Fuzzy Logic)

Part of Model Architecture V7 (Adaptable MultiAgentic System).

## Fuzzy Logic Set Rules Prioritization Engine

### Safety concern rule
- `safety_concern = true` -> minimum priority floor is `high`.
- It can still end at `critical` if other rules/modifiers raise it.

### Severity + urgency aligned rules
- `critical + critical` -> `critical`
- `high + high` -> `high`
- `medium + medium` -> `medium`
- `low + low` -> `low`

### Severity + urgency mismatch rules (1/2 style)
- `critical + high` -> `critical`
- `critical + (medium or low)` -> `high`
- `high + medium` -> `high`
- `high + low` -> `medium`
- `medium + low` -> `medium`

Symmetric pairs are included (severity/urgency order does not matter).

### Business impact + severity + urgency rules

High-dominant:
- `3/3 high` -> `critical`
- `2/3 high + 1/3 medium` -> `high`
- `2/3 high + 1/3 low` -> `high`
- `1/3 high + 2/3 medium` -> `medium`
- `1/3 high + 2/3 low` -> `medium`

Assuming less than high:
- `3/3 medium` -> `high`
- `2/3 medium + 1/3 low` -> `medium`
- `1/3 medium + 2/3 low` -> `low`

Assuming less than medium:
- `3/3 low` -> `low`
- `2/3 low` cases are covered by the explicit low rules above.

### Sentiment ranges
- Negative: `[-1, -0.25)` (implemented via fuzzy set and discrete modifier threshold)
- Neutral: `[-0.25, 0.25]`
- Positive: `(0.25, 1]`

### Sentiment effects
- Negative -> `+1` level modifier
- Neutral -> no level modifier
- Positive -> `-1` level modifier

### Other discrete modifiers
- `is_recurring = true` -> `+1` level
- `ticket_type = complaint` -> `0`
- `ticket_type = inquiry` -> `-1` level

## Decision Flow (Execution Order)
1. Fuzzy engine computes `raw_score` from sentiment, severity, urgency, business impact.
2. `raw_score` is rounded to `base_priority`.
3. Discrete modifiers are applied:
- recurring (`+1`)
- inquiry (`-1`)
- sentiment (`negative +1`, `neutral 0`, `positive -1`)
4. Safety floor applied:
- if `safety_concern=true`, enforce minimum `high`.
5. Clamp into valid labels:
- `low`, `medium`, `high`, `critical`.
