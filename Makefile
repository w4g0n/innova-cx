# Make sure command-style targets always run (even when files/folders share names)
.PHONY: \
	frontend frontend-build \
	frontend-logs \
	pipeline pipeline-build \
	pipeline-logs \
	ticket-flow-logs \
	dev dev-build \
	dev-logs \
	down

# =========================
# PROFILE 1: FRONTEND
# (Frontend + Backend + DB)
# =========================

frontend:
	docker compose --profile frontend up -d

frontend-build:
	docker compose --profile frontend up --build -d

frontend-logs:
	docker compose --profile frontend logs -f


# =========================
# PROFILE 2: PIPELINE
# (Frontend + Backend + DB + Orchestrator)
# =========================

pipeline:
	docker compose --profile pipeline up -d

pipeline-build:
	docker compose --profile pipeline up --build -d

pipeline-logs:
	docker compose --profile pipeline logs -f

ticket-flow-logs:
	bash scripts/ticket_flow_logs.sh

# =========================
# PROFILE 3: DEV
# (Frontend + Backend + DB + Orchestrator + Chatbot + Transcriber)
# =========================

dev:
	docker compose --profile dev up -d

dev-build:
	docker compose --profile dev up --build -d

dev-logs:
	docker compose --profile dev logs -f


# =========================
# CLEANUP
# =========================

down:
	COMPOSE_PROFILES=frontend,pipeline,dev docker compose down --remove-orphans
