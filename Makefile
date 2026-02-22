# Make sure command-style targets always run (even when files/folders share names)
.PHONY: \
	frontend frontend-build \
	pipeline pipeline-build \
	feature-agent feature-agent-build \
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
# (Frontend + Backend + DB + Classifier + Orchestrator)
# =========================

pipeline:
	docker compose --profile pipeline up

pipeline-build:
	docker compose --profile pipeline up --build


# Feature Engineering Agent (optional):

feature-agent:
	docker compose --profile feature-engineering up

feature-agent-build:
	docker compose --profile feature-engineering up --build


# =========================
# PROFILE 3: DEV
# (Frontend + Backend + DB + Orchestrator + Classifier + Chatbot + Transcriber)
# =========================

dev:
	docker compose --profile dev up

dev-build:
	docker compose --profile dev up --build


# =========================
# CLEANUP
# =========================

down:
	COMPOSE_PROFILES=frontend,pipeline,dev,feature-engineering docker compose down --remove-orphans
