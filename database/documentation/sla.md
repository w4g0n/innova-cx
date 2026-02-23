# SLA (Simple)

## What this does
- Every ticket can get SLA due times:
  - `respond_due_at`
  - `resolve_due_at`
- Every ticket also stores remaining SLA time:
  - `respond_time_left_seconds`
  - `resolve_time_left_seconds`

## When SLA starts
- SLA starts when `priority_assigned_at` is set.
- This usually happens when priority is finalized by the backend/orchestrator update.

## SLA rules by priority
- `Low`: respond in 6 hours, resolve in 3 days
- `Medium`: respond in 3 hours, resolve in 2 days
- `High`: respond in 1 hour, resolve in 18 hours
- `Critical`: respond in 30 minutes, resolve in 6 hours

## Overdue behavior
- Ticket becomes `Overdue` if:
  - no first response after `respond_due_at`, or
  - not resolved after `resolve_due_at`.

## Auto-escalation behavior
- If 90% of response SLA time is consumed and there is still no first response:
  - priority auto-escalates one level (`Low -> Medium -> High -> Critical`)
  - status becomes `Escalated`.

## Heartbeat (every 5 minutes)
- Backend runs an SLA heartbeat every 5 minutes (300s default).
- Each heartbeat refreshes:
  - escalation checks
  - overdue checks
  - remaining time columns (`respond_time_left_seconds`, `resolve_time_left_seconds`)
- You can change interval with env var: `SLA_HEARTBEAT_SECONDS`.

## Where implemented
- SQL logic: `database/scripts/sla.sql`
- Backend calls policy function during reads: `backend/api/main.py`
