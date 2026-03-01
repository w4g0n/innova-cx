from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.chat import router as chat_router
from core.llm import get_llm_diagnostics

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(chat_router, prefix="/api")


@app.get("/health")
def health():
    return {"status": "healthy", "service": "chatbot", **get_llm_diagnostics()}
