# Agent Execution Logging — Setup Guide

## What This Does

Every time a ticket goes through the orchestrator pipeline, each of the 7 AI agents now logs its work to the database in JSON format. This gives you:

- **Full traceability**: See exactly what each agent received and produced
- **Timing data**: How long each agent took (in milliseconds)
- **Error tracking**: If an agent fails, the error is logged with the inputs it had
- **State diffs**: What changed after each agent ran (keys added or modified)

All logs are permanent — they live in the PostgreSQL database (Cloud SQL or local Docker).

---

## Database Tables

Two new tables are created:

### `model_execution_log`
One row per agent per pipeline run. Lightweight metrics for analytics dashboards.

| Column | What it stores |
|--------|---------------|
| execution_id | Groups all 7 agent rows from the same pipeline run |
| ticket_id | The ticket being processed |
| agent_name | Which agent (e.g. ClassificationAgent, SentimentAgent) |
| inference_time_ms | How long the agent took in milliseconds |
| confidence_score | The agent's confidence (0.0 to 1.0), if applicable |
| error_flag | true if the agent failed |
| error_message | What went wrong (only when error_flag is true) |

### `agent_output_log`
One row per agent per pipeline run. Full JSON snapshots for explainability.

| Column | What it stores |
|--------|---------------|
| execution_id | Same grouping ID as above |
| ticket_id | The ticket being processed |
| agent_name | Which agent ran |
| step_order | 1 through 7 (order in the pipeline) |
| input_state | Full JSON of what the agent received |
| output_state | Full JSON of what the agent produced |
| state_diff | Only the keys that were added or changed |
| inference_time_ms | Agent duration in milliseconds |
| error_flag / error_message | Error details if the agent failed |

---

## Setup on Cloud SQL

### If this is a fresh database (no existing data)

Run the full `init.sql` — it now includes the migration automatically:

```bash
psql -h YOUR_CLOUD_SQL_IP -U innovacx_user -d innovacx -f database/init.sql
```

### If the database already exists (has data, tables already set up)

Run only the migration file:

```bash
psql -h YOUR_CLOUD_SQL_IP -U innovacx_user -d innovacx -f database/migrations/001_agent_execution_logs.sql
```

This is safe to run multiple times — it uses `CREATE TABLE IF NOT EXISTS` and `CREATE INDEX IF NOT EXISTS`.

### If you forget to run the migration

Both the backend and orchestrator will automatically create the tables on startup. So even if you skip the manual step, the tables will be created the first time the services start.

---

## Setup for Local Docker

No extra steps needed. The tables are created automatically through either:

1. **Fresh volume**: `init.sql` runs and includes the migration
2. **Existing volume**: Backend's startup compatibility check creates the tables
3. **Orchestrator startup**: Also creates the tables if they don't exist

Just run:

```bash
docker compose --profile pipeline up --build
```

---

## How to Query the Logs

### See all agent steps for the most recent pipeline run

```sql
SELECT agent_name, step_order, inference_time_ms, error_flag, confidence_score
FROM agent_output_log
WHERE execution_id = (
    SELECT execution_id FROM agent_output_log ORDER BY created_at DESC LIMIT 1
)
ORDER BY step_order;
```

### See what changed at each step (state diffs)

```sql
SELECT agent_name, step_order, state_diff
FROM agent_output_log
WHERE execution_id = 'YOUR_EXECUTION_ID'
ORDER BY step_order;
```

### Find all errors in the last 24 hours

```sql
SELECT agent_name, ticket_id, error_message, created_at
FROM model_execution_log
WHERE error_flag = true
  AND created_at > now() - interval '24 hours'
ORDER BY created_at DESC;
```

### Get average agent latency over the last week

```sql
SELECT agent_name,
       AVG(inference_time_ms) AS avg_ms,
       MAX(inference_time_ms) AS max_ms,
       COUNT(*) AS runs
FROM model_execution_log
WHERE created_at > now() - interval '7 days'
GROUP BY agent_name
ORDER BY avg_ms DESC;
```

### View full input/output JSON for a specific ticket

```sql
SELECT agent_name, step_order, input_state, output_state
FROM agent_output_log
WHERE ticket_id = 'YOUR_TICKET_UUID'
ORDER BY step_order;
```

---

## Agent Name Registry

These are the exact agent names stored in the logs:

| Step | Agent Name | What it does |
|------|-----------|--------------|
| 1 | ClassificationAgent | Routes ticket as complaint or inquiry |
| 2 | AudioAnalysisAgent | Extracts sentiment from audio features |
| 3 | SentimentAgent | Analyzes text sentiment and extracts keywords |
| 4 | SentimentCombinerAgent | Merges text + audio sentiment scores |
| 5 | FeatureEngineeringAgent | Predicts business impact, safety, severity, urgency |
| 6 | PrioritizationAgent | Assigns priority using fuzzy logic |
| 7 | DepartmentRoutingAgent | Creates/updates the ticket in the backend |

---

## How It Works (Technical Summary)

1. When a ticket is submitted to `POST /process/text`, a unique `execution_id` (UUID) is generated
2. The pipeline runs 7 agents in sequence
3. Each agent is wrapped with a logging function that:
   - Takes a snapshot of the state before the agent runs
   - Runs the agent and measures wall-clock time
   - Takes a snapshot of the state after the agent runs
   - Computes what changed (the diff)
   - Writes both snapshots + metrics to the database
4. If an agent fails, the error is still logged, then the exception is re-raised
5. Logging failures never crash the pipeline — if the database is temporarily unreachable, the pipeline continues normally

---

## Files Changed

| File | What changed |
|------|-------------|
| `database/migrations/001_agent_execution_logs.sql` | New migration file (the tables) |
| `database/init.sql` | References the migration for fresh Docker volumes |
| `ai-models/MultiAgentPipeline/Orchestrator/db.py` | New DB connection helper for orchestrator |
| `ai-models/MultiAgentPipeline/Orchestrator/execution_logger.py` | New logging wrapper module |
| `ai-models/MultiAgentPipeline/Orchestrator/pipeline.py` | Each step wrapped with logging |
| `ai-models/MultiAgentPipeline/Orchestrator/main.py` | Generates execution_id, ensures tables on startup |
| `ai-models/MultiAgentPipeline/Orchestrator/requirements.txt` | Added psycopg2-binary |
| `docker-compose.yml` | Orchestrator gets DATABASE_URL + postgres dependency |
| `backend/api/main.py` | Backend also creates tables on startup (for existing DBs) |
