"""
Assistant router — conversational guidance grounded in FSM context.
"""
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from db.session import get_session
from schemas.dto import (
    AssistantChatRequest,
    AssistantChatResponse,
    AssistantSuggestionsResponse,
)
from services.assistant_service import SUGGESTED_QUESTIONS, assistant_service

router = APIRouter(prefix="/api/v1/assistant", tags=["assistant"])


@router.post("/chat", response_model=AssistantChatResponse)
async def chat(request: AssistantChatRequest, db: Session = Depends(get_session)):
    """Send a message and receive guidance for the current experiment state."""
    return await assistant_service.chat(db, request)


@router.get("/suggestions", response_model=AssistantSuggestionsResponse)
def suggestions():
    """Suggested prompts shown before the crew types anything."""
    return AssistantSuggestionsResponse(suggestions=SUGGESTED_QUESTIONS)


@router.get("/guidance")
async def get_guidance(
    session_id: Optional[int] = Query(None),
    db: Session = Depends(get_session),
):
    """Rendered guidance for the current step of the active session."""
    guidance = await assistant_service.get_current_guidance(db, session_id)
    return {"session_id": session_id, "guidance": guidance}
