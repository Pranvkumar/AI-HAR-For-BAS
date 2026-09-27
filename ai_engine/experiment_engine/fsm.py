"""
Deterministic finite state machine for experiment sequence validation.

The FSM is the single source of truth for experiment progress. It never
generates free-form text; it emits a structured context packet that the
guidance layer renders. This keeps astronaut-facing instructions grounded.
"""
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

# Activities scoring below this are treated as unreliable observations rather
# than sequence errors, so a blurry frame cannot trigger a false violation.
DEFAULT_CONFIDENCE_THRESHOLD = 0.70


class ValidationStatus(str, Enum):
    CORRECT = "CORRECT"
    WARNING = "WARNING"
    SEQUENCE_VIOLATION = "SEQUENCE_VIOLATION"
    DUPLICATE = "DUPLICATE"


class FSMState(str, Enum):
    AWAITING_ACTIVITY = "AWAITING_ACTIVITY"
    STEP_COMPLETED = "STEP_COMPLETED"
    VIOLATION_TRIGGERED = "VIOLATION_TRIGGERED"


class ExperimentFSM:
    """
    Validates detected activities against an ordered expected sequence.
    """

    def __init__(
        self,
        expected_sequence: List[str],
        confidence_threshold: float = DEFAULT_CONFIDENCE_THRESHOLD,
    ):
        """
        Args:
            expected_sequence: Ordered expected activities for the experiment.
            confidence_threshold: Minimum confidence to act on a detection.
        """
        self.expected_sequence = list(expected_sequence)
        self.confidence_threshold = confidence_threshold
        self.current_step_index = 0
        self.state = FSMState.AWAITING_ACTIVITY
        self.last_validation_status: Optional[ValidationStatus] = None
        self.last_detected_activity: Optional[str] = None
        self.last_confidence: float = 0.0
        self.last_timestamp: Optional[datetime] = None
        self.last_completed_activity: Optional[str] = None
        self.last_completed_step: Optional[int] = None
        self.completed_steps: List[str] = []

    def process_activity(
        self,
        detected_activity: str,
        confidence: float,
    ) -> Tuple[ValidationStatus, Dict[str, Any]]:
        """
        Validate one detected activity and advance state on success.

        Returns:
            (status, context) where context carries the deterministic packet
            used for logging, alerting and guidance rendering.
        """
        self.last_detected_activity = detected_activity
        self.last_confidence = confidence
        self.last_timestamp = datetime.now(timezone.utc)

        expected = self.current_expected_activity()

        context: Dict[str, Any] = {
            "detected_activity": detected_activity,
            "confidence": confidence,
            "expected_activity": expected,
            "step_number": self.current_step_index + 1,
            "total_steps": len(self.expected_sequence),
            "timestamp": self.last_timestamp.isoformat(),
        }

        if not self.expected_sequence:
            status = ValidationStatus.WARNING
            context["message"] = "No expected sequence defined for this experiment"
        elif self.is_complete():
            status = ValidationStatus.CORRECT
            context["message"] = "Experiment sequence already complete"
        elif confidence < self.confidence_threshold:
            # Low-confidence observations never advance or fail a step.
            status = ValidationStatus.WARNING
            context["message"] = (
                f"Low confidence ({confidence:.2f}) for '{detected_activity}'; "
                f"still awaiting '{expected}'"
            )
        elif detected_activity == expected:
            status = ValidationStatus.CORRECT
            context["message"] = (
                f"Step {self.current_step_index + 1}/{len(self.expected_sequence)}: "
                f"'{detected_activity}' confirmed"
            )
            self._advance_step(detected_activity)
        elif detected_activity in self.completed_steps:
            # A real recognizer emits the same label across consecutive frames.
            # Re-seeing a step we already confirmed is a duplicate observation,
            # not the crew performing it out of order.
            status = ValidationStatus.DUPLICATE
            context["message"] = (
                f"'{detected_activity}' already confirmed; still awaiting '{expected}'"
            )
        elif detected_activity not in self.expected_sequence:
            status = ValidationStatus.SEQUENCE_VIOLATION
            self.state = FSMState.VIOLATION_TRIGGERED
            context["message"] = (
                f"Unexpected activity '{detected_activity}' is not part of this experiment"
            )
        else:
            status = ValidationStatus.SEQUENCE_VIOLATION
            self.state = FSMState.VIOLATION_TRIGGERED
            context["message"] = (
                f"Out-of-order activity at step {self.current_step_index + 1}: "
                f"expected '{expected}', detected '{detected_activity}'"
            )

        self.last_validation_status = status
        context["fsm_state"] = self.state.value
        context["progress"] = self.progress()
        context["is_complete"] = self.is_complete()
        context["status"] = status.value
        return status, context

    def _advance_step(self, completed_activity: str) -> None:
        """Record the completed step and move to the next, if any."""
        self.last_completed_activity = completed_activity
        self.last_completed_step = self.current_step_index + 1
        self.completed_steps.append(completed_activity)

        if self.current_step_index < len(self.expected_sequence) - 1:
            self.current_step_index += 1
            self.state = FSMState.AWAITING_ACTIVITY
        else:
            # Final step done: index stays on the last step so progress reads 100%.
            self.current_step_index = len(self.expected_sequence)
            self.state = FSMState.STEP_COMPLETED

    def current_expected_activity(self) -> Optional[str]:
        """Expected activity for the current step, or None once complete."""
        if self.current_step_index < len(self.expected_sequence):
            return self.expected_sequence[self.current_step_index]
        return None

    def is_complete(self) -> bool:
        """True once every step has been confirmed."""
        return bool(self.expected_sequence) and \
            self.current_step_index >= len(self.expected_sequence)

    def progress(self) -> float:
        """Completion fraction in [0.0, 1.0]."""
        if not self.expected_sequence:
            return 1.0
        return len(self.completed_steps) / len(self.expected_sequence)

    def reset(self) -> None:
        """Return the FSM to its initial state."""
        self.current_step_index = 0
        self.state = FSMState.AWAITING_ACTIVITY
        self.last_validation_status = None
        self.last_detected_activity = None
        self.last_confidence = 0.0
        self.last_timestamp = None
        self.last_completed_activity = None
        self.last_completed_step = None
        self.completed_steps = []

    def get_context(self) -> Dict[str, Any]:
        """
        Deterministic context packet. This is the only data the guidance layer
        receives — no free-form or user-supplied content passes through here.
        """
        step_number = min(self.current_step_index + 1, len(self.expected_sequence)) \
            if self.expected_sequence else 0

        return {
            "current_step": step_number,
            "total_steps": len(self.expected_sequence),
            "expected_activity": self.current_expected_activity(),
            "detected_activity": self.last_detected_activity,
            "confidence": self.last_confidence,
            "last_completed_activity": self.last_completed_activity,
            "last_completed_step": self.last_completed_step,
            "fsm_status": self.state.value,
            "status": self.last_validation_status.value if self.last_validation_status else None,
            "progress": self.progress(),
            "is_complete": self.is_complete(),
            "expected_sequence": list(self.expected_sequence),
            "completed_steps": list(self.completed_steps),
        }
