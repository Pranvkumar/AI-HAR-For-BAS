"""
Template-based guidance engine — the zero-dependency default.

Renders astronaut-facing instructions purely from the FSM context packet.
No inference, no network calls, no GPU. Because every string is a fixed
template keyed on deterministic state, guidance can never contradict the FSM,
which is the property that matters for a safety-monitoring system.

A real local LLM can be swapped in behind BaseLLM; this stays as the fallback.
"""
from typing import Any, Dict, List, Optional

from .base_llm import BaseLLM

# Procedure text per expected activity. Written as crew-facing instructions.
ACTIVITY_INSTRUCTIONS: Dict[str, str] = {
    "PICK_CONTAINER": (
        "Grasp the sample container with both hands. Confirm the grip is secure "
        "before moving it — in microgravity an unsecured container will drift."
    ),
    "OPEN_CONTAINER": (
        "Open the container lid with a slow counter-clockwise turn. Keep the "
        "opening facing the sample collection port and verify the O-ring seal is intact."
    ),
    "POUR_SAMPLE": (
        "Transfer the sample into the collection vessel using controlled micro-movements. "
        "Liquid forms spheres in microgravity — guide the transfer with the collection funnel."
    ),
    "MIX_SAMPLE": (
        "Mix the sample with the sterile stirring tool for 30 seconds using a steady "
        "circular motion. Keep the container closed to avoid contamination."
    ),
    "PLACE_CONTAINER": (
        "Place the container in its designated rack slot, aligned with the colour-coded "
        "marker. Wait for the magnetic lock to engage before releasing."
    ),
    "CLOSE_CONTAINER": (
        "Seal the lid clockwise until you feel resistance. Confirm the pressure seal "
        "indicator reads green, and engage the biohazard lock for biological samples."
    ),
    "RETRIEVE_RED_BOX": (
        "Carefully reach into the outer container and retrieve the red inner box. "
        "Ensure a stable two-finger or palm grasp so the box does not drift in microgravity."
    ),
    "RETRIEVE_SECOND_COLORED_BOX": (
        "Retrieve the second coloured inner box from the outer container slot. "
        "Maintain visual orientation markers aligned with the rack frame."
    ),
    "RETURN_RED_BOX": (
        "Align the red inner box with the designated internal compartment in the outer container. "
        "Slide it in until the physical retention latch engages."
    ),
    "RETURN_SECOND_COLORED_BOX": (
        "Return the second coloured inner box into its respective bay inside the outer container. "
        "Verify both inner boxes are safely secured before closing."
    ),
}

STATUS_TEMPLATES: Dict[str, str] = {
    "CORRECT": (
        "Step {step}/{total} confirmed: {detected} completed "
        "(confidence {confidence:.0%})."
    ),
    "WARNING": (
        "Detection unclear at step {step}/{total}: read {detected} at "
        "{confidence:.0%} confidence, below the reliability threshold. "
        "The step has not been marked complete — repeat the action within camera view."
    ),
    "SEQUENCE_VIOLATION": (
        "SEQUENCE VIOLATION at step {step}/{total}. Detected {detected}, "
        "expected {expected}. Stop the current action and resume the procedure "
        "at step {step}."
    ),
    "DUPLICATE": (
        "Step {step}/{total} in progress. {detected} is already confirmed — "
        "continue with {expected}."
    ),
    "AWAITING": (
        "Monitoring step {step}/{total}. Awaiting {expected}."
    ),
}


def _next_activity(context: Dict[str, Any]) -> Optional[str]:
    """
    Activity the crew should perform next.

    After a CORRECT result the FSM has already advanced, so its
    expected_activity is the next step. Otherwise the current step stands.
    """
    return context.get("expected_activity")


def _resolve_status(context: Dict[str, Any]) -> str:
    """Pick the template key from the FSM's own validation status."""
    status = context.get("status")
    if status in STATUS_TEMPLATES:
        return status
    return "AWAITING"


class TemplateLLM(BaseLLM):
    """
    Deterministic guidance renderer over the FSM context packet.
    """

    async def generate_guidance(self, context: Dict[str, Any]) -> str:
        """
        Render guidance for the current experiment state.

        Args:
            context: FSM context packet (see ExperimentFSM.get_context).
        """
        total_steps = context.get("total_steps", 0)

        if context.get("is_complete"):
            return (
                f"Experiment sequence complete — all {total_steps} steps validated. "
                "Seal all containers, stow the equipment in the designated storage bay, "
                "and log completion in BAS Mission Control."
            )

        status_key = _resolve_status(context)
        header = STATUS_TEMPLATES[status_key].format(
            step=context.get("current_step", 0),
            total=total_steps,
            expected=context.get("expected_activity") or "n/a",
            detected=context.get("detected_activity") or "no activity",
            confidence=context.get("confidence", 0.0) or 0.0,
        )

        next_activity = _next_activity(context)
        instruction = ACTIVITY_INSTRUCTIONS.get(next_activity or "")

        if not instruction:
            return header

        return f"{header}\n\nNext — {next_activity}: {instruction}"

    async def chat(self, user_message: str, context: Dict[str, Any]) -> str:
        """
        Answer a crew question about experiment state.

        The message is used only to route between fixed responses; it is never
        echoed into generated text, so the reply cannot be steered off-procedure.
        """
        message = user_message.lower()

        def mentions(*keywords: str) -> bool:
            return any(keyword in message for keyword in keywords)

        if mentions("progress", "how far", "how many steps", "remaining"):
            completed = len(context.get("completed_steps", []))
            total = context.get("total_steps", 0)
            percent = int((context.get("progress", 0.0) or 0.0) * 100)
            return (
                f"Progress: {percent}% — {completed} of {total} steps confirmed. "
                f"Current step {context.get('current_step', 0)}: "
                f"{context.get('expected_activity') or 'sequence complete'}."
            )

        if mentions("status", "what step", "where am i", "current"):
            return (
                f"Step {context.get('current_step', 0)}/{context.get('total_steps', 0)}\n"
                f"Expected activity: {context.get('expected_activity') or 'sequence complete'}\n"
                f"Last detection: {context.get('detected_activity') or 'none'} "
                f"({(context.get('confidence') or 0.0):.0%})\n"
                f"FSM state: {context.get('fsm_status', 'unknown')}"
            )

        if mentions("procedure", "all steps", "sequence", "full list"):
            sequence: List[str] = context.get("expected_sequence", [])
            if not sequence:
                return "No procedure is loaded for this session."
            completed = set(context.get("completed_steps", []))
            lines = [
                f"{index}. {activity}" + (" (done)" if activity in completed else "")
                for index, activity in enumerate(sequence, start=1)
            ]
            return "Experiment procedure:\n" + "\n".join(lines)

        if mentions("help", "how do i", "explain", "instruction"):
            activity = context.get("expected_activity")
            instruction = ACTIVITY_INSTRUCTIONS.get(activity or "")
            if instruction:
                return f"{activity}: {instruction}"
            return "No procedure step is currently active."

        # Default to current guidance — covers "what next" and anything unrouted.
        return await self.generate_guidance(context)

    def is_available(self) -> bool:
        """Always available: no external dependencies."""
        return True
