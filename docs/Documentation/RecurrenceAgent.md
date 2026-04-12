# Recurrence Agent

The Recurrence Agent is step 1 of the orchestrator pipeline. It detects whether a new customer submission is a repeat of an existing ticket from the same customer, then either absorbs the new ticket into the existing one or lets it continue through the pipeline with prior context injected.

## Files

| File | Purpose |
|------|---------|
| `ai-models/MultiAgentPipeline/Orchestrator/agents/step01_recurrence/step.py` | Branch logic and DB actions |
| `ai-models/MultiAgentPipeline/Orchestrator/recurrence_encoder.py` | Transformer similarity model |
| `/opt/innova-models/recurrence/all-MiniLM-L6-v2` (mounted in-container at `/app/models/recurrence/all-MiniLM-L6-v2`) | Preferred persistent sentence-transformer weights store for live deployments |
| `ai-models/MultiAgentPipeline/Orchestrator/agents/step01_recurrence/model/` | Repo-local fallback model path |

---

## Candidate filter

The agent only compares the new ticket against prior tickets that meet **all** of these conditions:

- Same `created_by_user_id` as the new ticket
- Different `ticket_code` from the new ticket
- Status is **not** `Open` or `Linked`
- `priority_assigned_at IS NOT NULL` (SLA has started)
- Has a completed `ReviewAgent` output event (pipeline ran to completion)
- Most recent first, up to 200 tickets (transformer) or 120 tickets (heuristic fallback)

`Linked` tickets are excluded because they are absorbed duplicates — the recurrence check should match against the original ticket, not the chain of pointers.

---

## Similarity scoring

The primary path uses a sentence-transformer encoder (mean-pooled cosine similarity). The heuristic fallback uses `SequenceMatcher` ratio and token Jaccard similarity when the model cannot load.

Default threshold: **0.70** (configurable via `RECURRENCE_SIMILARITY_THRESHOLD` env var).

Only the single best match is used. If multiple tickets are similar, the highest-scoring one controls the branch/action.

---

## Branch logic

```
New ticket submitted
        │
        ▼
Similar ticket found?
   No → not recurring, pipeline continues normally
   Yes → determine branch
              │
              ├─ matched.status in {Open, Assigned, In Progress,
              │   Escalated, Overdue, Reopened}
              │       │
              │       ├─ SLA elapsed < 50%  → Branch A
              │       └─ SLA elapsed ≥ 50%  → Branch B (once per ticket)
              │
              └─ matched.status == Resolved
                      │
                      ├─ resolved_at < 30 days ago  → Branch C
                      └─ resolved_at ≥ 30 days ago  → Branch D
```

### Branch A — open, SLA < 50%

- Sends a `recurrence_reminder` notification (🔁) to the assigned employee
- Adds a `recurrence_reminder` update to the matched ticket
- Absorbs the new ticket: sets status → `Linked`, `linked_ticket_code` → matched code
- Stops the pipeline (`_recurrence_handled = True`)
- Does not change priority

### Branch B — open, SLA ≥ 50%

- Escalates the matched ticket's priority by one level (Low → Medium → High → Critical)
- Skipped if already `Critical` — the escalation update is still recorded but marks "no change"
- Only fires once per matched ticket — if a `recurrence_escalation` update already exists, downgrades to Branch A
- Sends a `recurrence_reminder` notification (🔁) to the assigned employee
- Absorbs the new ticket: sets status → `Linked`, `linked_ticket_code` → matched code
- Stops the pipeline (`_recurrence_handled = True`)

### Branch C — resolved < 30 days ago

- Reopens the matched ticket: status → `Reopened`, `first_response_at` → NULL, `priority_assigned_at` → now()
- Resets SLA: the DB trigger `sync_ticket_priority_sla` recomputes `respond_due_at` / `resolve_due_at` from the new `priority_assigned_at`
- Adds a `recurrence_reopen` update with prior resolution text and new submission text
- Archives the prior resolution as a `previous_resolution` update (JSON: `{resolved_at, resolution}`) — shown in employee ticket detail under "Previous Resolutions"
- Sends a `recurrence_reminder` notification (🔁) to the assigned employee
- Absorbs the new ticket: sets status → `Linked`, `linked_ticket_code` → matched code
- Stops the pipeline (`_recurrence_handled = True`)

**Re-resolution tracking**: Each time Branch C fires, the prior `final_resolution` and `resolved_at` are archived before the ticket is reopened. After the ticket is re-resolved, the employee detail view shows both the current resolution and all previous ones with their original dates.

**SLA chain**: After the second re-resolve, `resolved_at` on the matched ticket is the second resolution date. A third submission checks against that date — so the 30-day window restarts with each resolution.

### Branch D — resolved ≥ 30 days ago

- Lets the new ticket continue through the full pipeline unchanged
- Writes `linked_ticket_code` and `is_recurring = TRUE` on the new ticket (reference only)
- Injects prior context into state for downstream agents:
  - `prior_ticket_code`
  - `prior_ticket_resolution`
  - `prior_ticket_details`
- Does **not** absorb or cancel the new ticket
- Does **not** affect the old ticket in any way

---

## Ticket statuses set by the agent

| Scenario | New ticket status | Old ticket status |
|---|---|---|
| No match | `Open` (unchanged) | — |
| Branch A | `Linked` | unchanged |
| Branch B | `Linked` | unchanged (priority bumped) |
| Branch C | `Linked` | `Reopened` |
| Branch D | `Open` (continues pipeline) | unchanged |

**`Linked`** means the ticket was a confirmed recurring duplicate and was absorbed into an existing ticket. The `linked_ticket_code` field points to the ticket that covers the issue.

---

## Notifications

Recurrence notifications use type `recurrence_reminder` and display with a 🔁 icon in the employee notifications page.

| Branch | Title | Message |
|---|---|---|
| A | Recurring Ticket Submission | "A recurring submission was received for ticket {old}. New submission: {new}. SLA < 50% elapsed — no priority change." |
| B | Recurring Ticket Submission | "A recurring submission was received for ticket {old}. New submission: {new}. SLA ≥ 50% elapsed — priority escalated to {level}." |
| C | Ticket Reopened — Recurring Issue | "Ticket {old} has been reopened due to a recurring submission within 1 month of resolution." |

---

## State fields written by the agent

**Non-recurring:**
```
is_recurring       = False
recurrence_branch  = "none"
similarity_score   = best score seen (or None)
recurrence_mode    = "transformer" | "heuristic_fallback"
```

**Recurring (all branches):**
```
is_recurring             = True
similar_ticket_code      = matched ticket code
similar_ticket_subject   = matched ticket subject
similarity_score         = rounded cosine score
recurrence_branch        = "A" | "B" | "C" | "D"
recurrence_reason        = human-readable action summary
recurrence_mode          = "transformer" | "heuristic_fallback"
```

**Branches A/B/C only:**
```
_recurrence_handled = True   ← queue manager stops pipeline here
```

**Branch D only:**
```
prior_ticket_code        = matched ticket code
prior_ticket_resolution  = matched ticket final_resolution
prior_ticket_details     = matched ticket details (first 500 chars)
```

---

## Customer-facing UI

When a customer views a `Linked` ticket:

- Status badge shows "Linked" in grey
- A notice card is displayed: *"Your submission was linked — This issue is already being addressed under ticket [code]. The assigned team has been notified."*
- The normal pipeline progress bar is not shown

When a customer views a `Reopened` ticket (they submitted the original):

- Status badge shows "Reopened" in orange

---

## Employee-facing UI

When an employee views a `Reopened` ticket that has been through Branch C:

- **Previous Resolutions** section appears below **Final Resolution**, showing each prior resolution with its original resolved date (muted)
- If the ticket has been reopened multiple times, all prior resolutions are listed in chronological order

---

## is_recurring in the prioritization model

`is_recurring` is **always passed as `False`** to the prioritization model regardless of the ticket's actual recurrence status. Priority escalation for recurring open tickets is handled by Branch B directly — not by the model. The `is_recurring` field is also hidden from the AI Explainability UI priority breakdown.

---

## Test scenarios

The automated test suite (`test_recurrence.py`) covers:

| Suite | Scenario | Expected |
|---|---|---|
| 1 | Branch C: resolved 3 days ago | Reopened, Linked, SLA reset, previous_resolution archived |
| 1 | Third submission after re-resolve | Matches original, not linked pointer |
| 2 | Assigned, SLA < 50% | Branch A |
| 2 | In Progress, SLA < 50% | Branch A |
| 2 | Reopened, SLA < 50% | Branch A |
| 2 | Assigned, SLA ≥ 50% | Branch B |
| 2 | In Progress, SLA ≥ 50% | Branch B |
| 2 | Escalated, SLA ≥ 50% | Branch B |
| 2 | Reopened, SLA ≥ 50% | Branch B |
| 2 | Overdue (past deadline) | Branch B |
| 2 | Linked ticket | Excluded from candidates |
| 3 | Unrelated text | Not recurring |
| 3 | Same text, different user | Not recurring |
| 3 | Already escalated, SLA ≥ 50% | Downgrades to Branch A |
| 3 | Resolved 45 days ago | Branch D, pipeline continues, old ticket untouched |
| 3 | No ticket_id in state | Runs without crash |

Run with:

```bash
docker cp test_recurrence.py innovacx-orchestrator:/app/test_recurrence.py
docker exec innovacx-orchestrator python /app/test_recurrence.py
```

---

## Environment variables

| Variable | Default | Description |
|---|---|---|
| `RECURRENCE_ENCODER_MODEL` | `/app/models/recurrence/all-MiniLM-L6-v2` | Preferred HuggingFace model id or local path; loader falls back to the repo-local model dir, then the upstream HF model id if needed |
| `RECURRENCE_SIMILARITY_THRESHOLD` | `0.70` | Cosine similarity threshold (0–1) |
