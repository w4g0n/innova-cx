# Make sure command-style targets always run (even when files/folders share names)
.PHONY: \
	frontend frontend-build \
	pipeline pipeline-build \
	dev dev-build \
	down

# =========================
# PROFILE 1: FRONTEND
# (Frontend + Backend + DB)
# =========================

frontend:
	docker compose --profile frontend up

frontend-build:
	docker compose --profile frontend up --build


# =========================
# PROFILE 2: PIPELINE
# (Frontend + Backend + DB + Orchestrator)
# =========================

pipeline:
	docker compose --profile pipeline up

pipeline-build:
	docker compose --profile pipeline up --build

# =========================
# PROFILE 3: DEV
# (Frontend + Backend + DB + Orchestrator + Chatbot + Transcriber)
# =========================

dev:
	docker compose --profile dev up

dev-build:
	docker compose --profile dev up --build


# =========================
# CLEANUP
# =========================

down:
	COMPOSE_PROFILES=frontend,pipeline,dev docker compose down --remove-orphans
