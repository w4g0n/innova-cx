from fastapi import APIRouter
from pydantic import BaseModel
from core.controller import handle_inquiry

router = APIRouter()

class ChatRequest(BaseModel):
    message: str

class ChatResponse(BaseModel):
    reply: str

@router.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    reply = handle_inquiry(req.message)
    return {"reply": reply}