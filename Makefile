.PHONY: \
	frontend frontend-build \
	frontend-logs \
	pipeline pipeline-build \
	pipeline-logs \
	ticket-flow-logs \
	live live-build \
	live-logs \
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
# PROFILE 3: LIVE
# (Frontend + Backend + DB + Orchestrator + Chatbot + Transcriber)
# =========================

live:
	docker compose --profile live up -d

live-build:
	docker compose --profile live up --build -d

live-logs:
	docker compose --profile live logs -f


# =========================
# CLEANUP
# =========================

down:
	COMPOSE_PROFILES=frontend,pipeline,live docker compose down --remove-orphans
