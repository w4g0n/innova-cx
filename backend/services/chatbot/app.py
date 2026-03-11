from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.chat import router as chat_router
from core.llm import get_llm_diagnostics, warm_llm

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
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
