# InnovaCX Docker Profiles Guide

Single source of truth for running the project with Docker profiles.

## Profiles

### `frontend`
Runs:
- `frontend`
- `backend`
- `postgres`

Command:
```bash
docker compose --profile frontend up
```

### `pipeline`
Runs:
- `frontend`
- `backend`
- `postgres`
- `orchestrator`

Command:
```bash
docker compose --profile pipeline up
```

### `dev`
Runs:
- `frontend`
- `backend`
- `postgres`
- `orchestrator`
- `chatbot`
- `transcriber`

Command:
```bash
docker compose --profile dev up
```

## Build + Run

```bash
docker compose --profile frontend up --build
docker compose --profile pipeline up --build
docker compose --profile dev up --build
```

## Stop / Cleanup

```bash
docker compose down --remove-orphans
```

## Service URLs

- Frontend: `http://localhost:5173`
- Backend API: `http://localhost:8000`
- Orchestrator API (`pipeline`/`dev`): `http://localhost:8004`
- Chatbot (`dev`): `http://localhost:8001`
- Transcriber (`dev`): `http://localhost:3001`
- Postgres host port: `5433`

## Notes

- Orchestrator handles runtime pipeline flow including sentiment path integration.
- `chatbot` and `transcriber` are intentionally `dev`-only.
- Use one profile at a time for predictable logs and resource usage.
