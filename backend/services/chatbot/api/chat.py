import re
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, field_validator

from core.controller import handle_message
from core.llm import generate_response
from core.session import create_session, session_belongs_to_user

router = APIRouter()
MAX_CHAT_MESSAGE_WORDS = 250


def _word_count(value: str) -> int:
    return len(str(value or "").split())


class ChatRequest(BaseModel):
    session_id: Optional[str] = None
    user_id: str = Field(..., min_length=1)
    message: Optional[str] = None

    @field_validator("message")
    @classmethod
    def message_within_word_limit(cls, value: Optional[str]) -> Optional[str]:
        if value is not None and _word_count(value) > MAX_CHAT_MESSAGE_WORDS:
            raise ValueError(f"message must be {MAX_CHAT_MESSAGE_WORDS} words or fewer.")
        return value


class ChatResponse(BaseModel):
    session_id: str
    response: str
    response_type: str
    show_buttons: list[str]


class SubjectSuggestionRequest(BaseModel):
    details: str = Field(..., min_length=1)

    @field_validator("details")
    @classmethod
    def details_within_word_limit(cls, value: str) -> str:
        if _word_count(value) > MAX_CHAT_MESSAGE_WORDS:
            raise ValueError(f"details must be {MAX_CHAT_MESSAGE_WORDS} words or fewer.")
        return value


class SubjectSuggestionResponse(BaseModel):
    subject: str


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


@router.post("/suggest-subject", response_model=SubjectSuggestionResponse)
def suggest_subject(req: SubjectSuggestionRequest):
    try:
        prompt = (
            "Generate a clear subject line (5-8 words) for this support ticket.\n"
            "Use sentence case.\n"
            "Do not use quotes, prefixes, labels, or punctuation at the end.\n"
            "Return only the subject line.\n\n"
            f"Ticket: {req.details}"
        )
        subject = generate_response(
            [{"role": "user", "content": prompt}],
            max_new_tokens=12,
            do_sample=False,
        ).strip()
        subject = subject.splitlines()[0].strip() if subject else ""
        subject = re.sub(r'^["\']|["\']$', "", subject).strip()
        subject = re.sub(r"[.!?;:,]+$", "", subject).strip()
        if not subject:
            raise HTTPException(status_code=502, detail="Model returned empty subject")
        return {"subject": subject}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Subject suggestion error: {e}") from e
