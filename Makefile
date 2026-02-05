# =========================
# BACKEND + DATABASE
# =========================

backend:
	docker compose --profile backend up

backend-build:
	docker compose --profile backend up --build


# =========================
# FRONTEND (UI + CHATBOT + WHISPER)
# =========================
# Frontend profile now includes:
# - frontend
# - chatbot
# - whisper

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


# =========================
# FULL DEV STACK
# (Frontend + AI)
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
