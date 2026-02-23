# Ticket Status (Simple)

## Main statuses used
- `Open`
- `In Progress`
- `Assigned`
- `Escalated`
- `Overdue`
- `Resolved`

(Enum also includes `Unassigned` and `Reopened`.)

## Lifecycle in current flow
1. Ticket is created as `Open`.
2. When sentiment analysis starts, status updates to `In Progress`.
3. After routing/final priority + department, status updates to `Assigned`.
4. Employee can resolve ticket -> status becomes `Resolved`.
5. If SLA is missed, status can become `Overdue`.
6. If auto-escalation rule triggers, status becomes `Escalated`.

## Timestamp behavior
- `assigned_at` is set when ticket first enters `Assigned` or `In Progress`.
- `resolved_at` is set when ticket becomes `Resolved`.

## Where implemented
- Status timestamps trigger: `database/scripts/ticket_status.sql`
- Orchestrator status updates: `ai-models/MultiAgentPipeline/Orchestrator/...`
- Employee resolve endpoint: `backend/api/main.py` (`/api/employee/tickets/{ticket_code}/resolve`)
