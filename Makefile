# Make sure command-style targets always run (even when files/folders share names)
.PHONY: \
	backend backend-build \
	frontend frontend-build \
	chatbot chatbot-build \
	audio audio-build \
	feature-agent feature-agent-build \
	orchestrator orchestrator-build \
	dev dev-build \
	down

# =========================
# BACKEND + DATABASE
# =========================

backend:
	docker compose --profile backend up

backend-build:
	docker compose --profile backend up --build


# =========================
# FRONTEND + BACKEND + DATABASE
# =========================
# Frontend profile includes:
# - frontend
# - backend
# - postgres

frontend:
	docker compose --profile frontend up

frontend-build:
	docker compose --profile frontend up --build


# =========================
# OPTIONAL: CHATBOT ONLY
# (useful for debugging, not required for normal use)
# =========================

chatbot:
	docker compose --profile chatbot up

chatbot-build:
	docker compose --profile chatbot up --build


# =========================
# OPTIONAL: AUDIO (WHISPER) ONLY
# =========================

audio:
	docker compose --profile audio up

audio-build:
	docker compose --profile audio up --build



# Feature Engineering Agent:

feature-agent:
	docker compose --profile feature-engineering up

feature-agent-build:
	docker compose --profile feature-engineering up --build


# =========================
# ORCHESTRATOR
# (Classifier + Orchestrator + Backend + DB + Whisper + Sentiment)
# =========================

orchestrator:
	docker compose --profile backend up orchestrator

orchestrator-build:
	docker compose --profile backend up --build orchestrator


# =========================
# FULL DEV STACK
# (Frontend + Backend + DB + Transcriber + Sentiment + Chatbot)
# =========================

dev:
	docker compose --profile dev up

dev-build:
	docker compose --profile dev up --build


# =========================
# CLEANUP
# =========================

down:
	docker compose down --remove-orphans
