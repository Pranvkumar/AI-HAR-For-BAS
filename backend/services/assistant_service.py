"""
Assistant service — contextual guidance grounded in FSM state.

The guidance layer only ever receives the FSM's deterministic context packet,
so replies cannot drift from the validated experiment state.
"""
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from ai_engine.nlp.template_fallback import TemplateLLM
from db import models
from schemas.dto import AssistantChatRequest, AssistantChatResponse
from services.monitoring_service import monitoring_service

SUGGESTED_QUESTIONS: List[str] = [
    "What is the current experiment step?",
    "What should I do next?",
    "Show current experiment status.",
    "Show the full procedure.",
]

# Baseline packet for when nothing is running, so procedure questions still work.
IDLE_CONTEXT: Dict[str, Any] = {
    "current_step": 0,
    "total_steps": 0,
    "expected_activity": None,
    "detected_activity": None,
    "confidence": 0.0,
    "fsm_status": "AWAITING_ACTIVITY",
    "status": None,
    "progress": 0.0,
    "is_complete": False,
    "expected_sequence": [],
    "completed_steps": [],
}


class AssistantService:
    """Answers crew questions using the template guidance engine."""

    def __init__(self):
        self.llm = TemplateLLM()

    def _fallback_context(self, db: Session) -> Dict[str, Any]:
        """
        Context when no session is active: load the procedure from the first
        experiment so "what are the steps" still answers usefully.
        """
        context = dict(IDLE_CONTEXT)

        experiment = (
            db.query(models.Experiment)
            .order_by(models.Experiment.code)
            .first()
        )
        if experiment is None:
            return context

        steps = (
            db.query(models.ExperimentStep)
            .filter(models.ExperimentStep.experiment_id == experiment.id)
            .order_by(models.ExperimentStep.step_number)
            .all()
        )
        sequence = [step.expected_activity for step in steps]

        context["expected_sequence"] = sequence
        context["total_steps"] = len(sequence)
        context["current_step"] = 1 if sequence else 0
        context["expected_activity"] = sequence[0] if sequence else None
        return context

    def resolve_context(
        self,
        db: Session,
        session_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Pick the best available context: the named session, any running session,
        then the static procedure fallback.
        """
        active = None
        if session_id is not None:
            active = monitoring_service.get_session(session_id)
        if active is None:
            active = monitoring_service.get_any_session()

        if active is not None:
            return active.fsm.get_context()

        return self._fallback_context(db)

    async def chat(
        self,
        db: Session,
        request: AssistantChatRequest,
    ) -> AssistantChatResponse:
        """Answer a chat message in the context of the current experiment state."""
        context = self.resolve_context(db, request.session_id)
        reply = await self.llm.chat(request.message, context)

        return AssistantChatResponse(
            reply=reply,
            context=context,
            timestamp=datetime.now(timezone.utc),
        )

    async def get_current_guidance(self, db: Session, session_id: Optional[int] = None) -> str:
        """Render guidance for the current step."""
        context = self.resolve_context(db, session_id)
        return await self.llm.generate_guidance(context)


assistant_service = AssistantService()
