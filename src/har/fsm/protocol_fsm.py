"""Protocol FSM with debounce, pending evidence, look-ahead, and safety gates."""

from dataclasses import dataclass
from collections import deque
from typing import Any

from har.config.loader import ProtocolConfig, ProtocolStep
from har.fusion.interaction_engine import InteractionEvent


@dataclass(frozen=True)
class FSMTransitionEvent:
    from_step: int | str | None
    to_step: int | str | None
    step_id: int | str
    timestamp: float
    message: str


@dataclass(frozen=True)
class ViolationEvent:
    step_id: int | str
    timestamp: float
    message: str
    safety_critical: bool
    blocked: bool


class ProtocolFSM:
    def __init__(self, protocol: ProtocolConfig) -> None:
        self.protocol = protocol
        self.index = 0
        self.pending_count = 0
        self.state = "PENDING_CONFIRMATION"
        self.history: deque[InteractionEvent] = deque()
        self.completed: list[int | str] = []

    @property
    def current_step(self) -> ProtocolStep | None:
        return (
            self.protocol.steps[self.index]
            if self.index < len(self.protocol.steps)
            else None
        )

    def _matches(self, step: ProtocolStep, event: InteractionEvent) -> bool:
        return all(
            getattr(event, key, object()) == value
            for key, value in step.expects.items()
        )

    def _advance(
        self, event: InteractionEvent, step: ProtocolStep, inferred: bool = False
    ) -> FSMTransitionEvent:
        previous = self.current_step.id if self.current_step else None
        self.completed.append(step.id)
        self.index += 1
        self.pending_count = 0
        self.state = "COMPLETE" if self.current_step is None else "PENDING_CONFIRMATION"
        return FSMTransitionEvent(
            previous,
            self.current_step.id if self.current_step else None,
            step.id,
            event.timestamp,
            f"Completed step {step.id}"
            + (" by look-ahead recovery" if inferred else ""),
        )

    def process(
        self, event: InteractionEvent
    ) -> list[FSMTransitionEvent | ViolationEvent]:
        """Process one event without blocking on ambiguous or non-critical evidence."""
        self.history.append(event)
        cutoff = event.timestamp - self.protocol.lookback_window_s
        while self.history and self.history[0].timestamp < cutoff:
            self.history.popleft()
        step = self.current_step
        if step is None:
            return []
        if self._matches(step, event):
            self.pending_count += 1
            if self.pending_count >= self.protocol.debounce_frames:
                return [self._advance(event, step)]
            return []
        self.pending_count = 0
        later_index = next(
            (
                position
                for position, candidate in enumerate(
                    self.protocol.steps[self.index + 1 :], self.index + 1
                )
                if self._matches(candidate, event)
            ),
            None,
        )
        if later_index is not None:
            evidence = list(self.history)
            missing = self.protocol.steps[self.index : later_index]
            if all(
                any(self._matches(candidate, prior) for prior in evidence[:-1])
                for candidate in missing
            ):
                transitions = []
                for candidate in missing:
                    transitions.append(self._advance(event, candidate, inferred=True))
                return transitions + [
                    self._advance(event, self.current_step, inferred=False)
                ]
            if step.safety_critical:
                self.state = "BLOCKED"
                return [
                    ViolationEvent(
                        step.id,
                        event.timestamp,
                        f"Safety-critical step {step.id} was not confirmed",
                        True,
                        True,
                    )
                ]
            self.index = later_index
            self.pending_count = 0
            violation = ViolationEvent(
                step.id,
                event.timestamp,
                f"Step {step.id} was not confirmed; continuing",
                False,
                False,
            )
            return [violation, self._advance(event, self.current_step)]
        return []
