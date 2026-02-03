# =========================
# BACKEND + DATABASE
# =========================

backend:
	docker compose --profile backend up

backend-build:
	docker compose --profile backend up --build


# =========================
# FRONTEND (VITE)
# =========================

frontend:
	docker compose --profile frontend up

frontend-build:
	docker compose --profile frontend up --build


# =========================
# AUDIO (WHISPER)
# =========================

audio:
	docker compose --profile audio up

audio-build:
	docker compose --profile audio up --build


# =========================
# CHATBOT
# =========================

chatbot:
	docker compose --profile chatbot up

chatbot-build:
	docker compose --profile chatbot up --build


# =========================
# COMBINATIONS
# =========================

dev:
	docker compose --profile backend --profile frontend up

dev-build:
	docker compose --profile backend --profile frontend up --build


# =========================
# CLEANUP
# =========================

down:
	docker compose down