"""
Validator — maps FSM validation results to alert severity and log records.
"""
from typing import Any, Dict

from .fsm import ExperimentFSM, ValidationStatus

SEVERITY_BY_STATUS = {
    ValidationStatus.CORRECT: "INFO",
    ValidationStatus.DUPLICATE: "INFO",
    ValidationStatus.WARNING: "WARNING",
    ValidationStatus.SEQUENCE_VIOLATION: "CRITICAL",
}

# Statuses that should surface to the crew as an alert. Duplicates are the
# normal result of frame-rate re-detection, so they stay out of the alert feed.
ALERTING_STATUSES = (ValidationStatus.WARNING, ValidationStatus.SEQUENCE_VIOLATION)


class ExperimentValidator:
    """
    Thin policy layer over the FSM: decides severity, alerting and logging.
    """

    def validate(
        self,
        fsm: ExperimentFSM,
        detected_activity: str,
        confidence: float,
    ) -> Dict[str, Any]:
        """
        Run one validation step and return a packet for downstream systems.

        Note: this advances the FSM when the activity is correct.
        """
        status, context = fsm.process_activity(detected_activity, confidence)

        return {
            "status": status.value,
            "severity": SEVERITY_BY_STATUS.get(status, "INFO"),
            "message": context.get("message", ""),
            "context": context,
            "alert_required": status in ALERTING_STATUSES,
            "log_entry": {
                "step_number": context.get("step_number"),
                "validation_status": status.value,
                "timestamp": context.get("timestamp"),
            },
        }

    def get_guidance_context(self, fsm: ExperimentFSM) -> Dict[str, Any]:
        """Deterministic context packet for the guidance layer."""
        return fsm.get_context()
