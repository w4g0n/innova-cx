from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from core.controller import handle_message
from core.llm import generate_response
from core.resolution_retrainer import format_examples_for_prompt, retrain_resolution_examples
from core.session import create_session, session_belongs_to_user

router = APIRouter()


class ChatRequest(BaseModel):
    session_id: Optional[str] = None
    user_id: str = Field(..., min_length=1)
    message: Optional[str] = None


class ChatResponse(BaseModel):
    session_id: str
    response: str
    response_type: str
    show_buttons: list[str]


class ResolutionSuggestionRequest(BaseModel):
    ticket_code: str = Field(..., min_length=1)
    ticket_type: str = Field(default="Complaint")
    subject: str = Field(..., min_length=1)
    details: str = Field(..., min_length=1)
    priority: str = Field(default="Medium")
    department: str = Field(default="General")
    status: str = Field(default="Assigned")


class ResolutionSuggestionResponse(BaseModel):
    suggested_resolution: str


class ResolutionRetrainRequest(BaseModel):
    max_examples: int = Field(default=12, ge=1, le=50)


@router.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    try:
        if not req.session_id:
            session_id = create_session(req.user_id)
            result = handle_message(session_id, req.user_id, "__init__")
        else:
            if not session_belongs_to_user(req.session_id, req.user_id):
                raise HTTPException(status_code=403, detail="session_id does not belong to this user")
            user_text = (req.message or "").strip()
            if not user_text:
                raise HTTPException(status_code=400, detail="message is required when session_id is provided")
            result = handle_message(req.session_id, req.user_id, user_text)
        return result
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Chat processing error: {e}") from e


@router.post("/suggest-resolution", response_model=ResolutionSuggestionResponse)
def suggest_resolution(req: ResolutionSuggestionRequest):
    try:
        learned_examples = format_examples_for_prompt(limit=4)
        system_prompt = (
            "You are a senior support resolution assistant. "
            "Generate one practical, safe, concise suggested resolution for an employee to apply.\n"
            "Constraints:\n"
            "- Do not invent actions that require unmentioned access.\n"
            "- Include verification/closure steps.\n"
            "- Keep it under 180 words.\n"
            "- Output plain text only."
        )
        if learned_examples:
            system_prompt += (
                "\n\nUse these previous successful examples as style guidance:\n"
                f"{learned_examples}"
            )
        user_prompt = (
            f"Ticket: {req.ticket_code}\n"
            f"Type: {req.ticket_type}\n"
            f"Priority: {req.priority}\n"
            f"Status: {req.status}\n"
            f"Department: {req.department}\n"
            f"Subject: {req.subject}\n"
            f"Details: {req.details}\n\n"
            "Provide a suggested resolution for the employee."
        )
        suggestion = generate_response(
            [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ]
        ).strip()
        if not suggestion:
            raise HTTPException(status_code=502, detail="Model returned empty suggestion")
        return {"suggested_resolution": suggestion}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Resolution suggestion error: {e}") from e


@router.post("/retrain-resolution-model")
def retrain_resolution_model(req: ResolutionRetrainRequest):
    try:
        return retrain_resolution_examples(max_examples=req.max_examples)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Retraining error: {e}") from e
