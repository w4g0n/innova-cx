import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.chat import router as chat_router
from core.llm import get_llm_diagnostics, warm_llm

app = FastAPI()

_cors_origins = [
    o.strip()
    for o in os.getenv("ALLOWED_ORIGINS", "").split(",")
    if o.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=False,
    allow_methods=["POST", "GET", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)
app.include_router(chat_router, prefix="/api")


@app.on_event("startup")
def warm_chatbot_model():
    try:
        warm_llm()
    except Exception:
        # Health should still come up even if the local model fails and the
        # service falls back to template mode.
        pass


@app.get("/health")
def health():
    return {"status": "healthy", "service": "chatbot", **get_llm_diagnostics()}
