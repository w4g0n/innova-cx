# Suggested Resolution Flow

## Goal
Generate a suggested employee resolution after priority and department are first assigned, capture employee acceptance/decline, and continuously improve future suggestions using captured outcomes.

## Components
- Suggestion generation agent (orchestrator pipeline):
  - `ai-models/MultiAgentPipeline/Orchestrator/agents/step02_suggestedresolution/step.py`
- Review and correction gate:
  - `ai-models/MultiAgentPipeline/Orchestrator/agents/step11_reviewagent/step.py`
- Backend integration and resolve workflow:
  - `backend/api/main.py`
- Employee resolve UI:
  - `frontend/src/pages/employee/ComplaintDetails.jsx`
- Learning schema:
  - `database/scripts/learning.sql`

## Prompt (Current)
The orchestrator suggested-resolution agent builds prompts directly from ticket context and SQL-backed learning examples from `suggested_resolution_usage`.

## End-to-End Workflow
1. Ticket receives first priority assignment (`priority_assigned_at`) with department.
2. Orchestrator generates suggestion and stores on ticket:
   - `suggested_resolution`
   - `suggested_resolution_model`
   - `suggested_resolution_generated_at`
3. Employee opens Resolve modal:
   - UI fetches suggestion via:
     - backend ticket details / resolution endpoints
4. Employee chooses:
   - `accepted` (use suggestion), or
   - `declined_custom` (provide own final resolution)
5. Resolve submit API:
   - `POST /api/employee/tickets/{ticket_code}/resolve`
   - Saves ticket as resolved and writes `final_resolution`.
   - Captures learning row in `suggested_resolution_usage`.
6. Future suggestions read directly from `suggested_resolution_usage`.

## Retraining Data Captured
`suggested_resolution_usage` includes:
- `decision` (`accepted` | `declined_custom`)
- `actor_role`
- `suggested_text`
- `final_text`
- `ticket_id`, `employee_user_id`, timestamps

## Important Clarification
Current learning is prompt-level and SQL-backed, not model weight fine-tuning.
There is no chatbot-owned suggested-resolution path anymore.
