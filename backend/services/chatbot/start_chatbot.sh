#!/bin/sh
set -eu

MODEL_PATH="$(python /app/startup/download_model.py)"
export CHATBOT_MODEL="${MODEL_PATH}"

exec uvicorn app:app --host 0.0.0.0 --port 8000
