"""Fault-tolerant, config-driven protocol finite-state machine."""

from __future__ import annotations

from collections import Counter, deque
from typing import Callable

from transitions import Machine

from har.config.models import ProtocolConfig
from har.events import FSMTransitionEvent, InteractionEvent, ViolationEvent

Event = FSMTransitionEvent | ViolationEvent


class ProtocolFSM:
    """Confirm ordered protocol evidence while tolerating transient ambiguity."""

    def __init__(self, config: ProtocolConfig, publish: Callable[[Event], None] | None = None) -> None:
        self.config, self.publish = config, publish or (lambda _event: None)
        self.index = 0
        self.blocked = False
        self._counts: Counter[str] = Counter()
        self._lookback: deque[InteractionEvent] = deque()
        states = [step.id for step in config.steps] + ["PENDING_CONFIRMATION", "BLOCKED", "COMPLETE"]
        self.machine = Machine(model=self, states=states, initial=config.steps[0].id, auto_transitions=False)

    @property
    def current_step(self) -> str:
        """Return the current protocol state."""

        return self.state

    def _expected(self, index: int) -> bool:
        return 0 <= index < len(self.config.steps)

    def _emit(self, event: Event) -> Event:
        self.publish(event)
        return event

    def _advance(self, timestamp_s: float) -> FSMTransitionEvent:
        old = self.config.steps[self.index]
        self.index += 1
        next_id = "COMPLETE" if self.index == len(self.config.steps) else self.config.steps[self.index].id
        self.machine.set_state(next_id, self)
        self._counts.clear()
        return self._emit(FSMTransitionEvent(timestamp_s, old.id, next_id, f"Completed: {old.name}", f"Completed {old.name}"))

    def _has_recent_evidence(self, step_index: int, now: float) -> bool:
        if not self._expected(step_index):
            return False
        expected = set(self.config.steps[step_index].expects)
        return any(now - item.timestamp_s <= self.config.lookback_window_s and item.evidence in expected for item in self._lookback)

    def handle(self, event: InteractionEvent) -> list[Event]:
        """Consume one interaction event and return emitted state/violation events."""

        if self.blocked or self.current_step == "COMPLETE":
            return []
        self._lookback.append(event)
        while self._lookback and event.timestamp_s - self._lookback[0].timestamp_s > self.config.lookback_window_s:
            self._lookback.popleft()
        if event.evidence in self.config.anomaly_messages:
            message = self.config.anomaly_messages[event.evidence]
            return [self._emit(ViolationEvent(event.timestamp_s, message, message, True, self.config.steps[self.index].id))]
        expected = self.config.steps[self.index]
        if event.evidence in expected.expects:
            self._counts[event.evidence] += 1
            if self._counts[event.evidence] >= self.config.debounce_frames:
                return [self._advance(event.timestamp_s)]
            self.machine.set_state("PENDING_CONFIRMATION", self)
            return []
        self.machine.set_state(expected.id, self)
        for future_index in range(self.index + 1, len(self.config.steps)):
            if event.evidence not in self.config.steps[future_index].expects:
                continue
            skipped = list(range(self.index, future_index))
            recoverable = future_index == self.index + 2 and self._has_recent_evidence(self.index + 1, event.timestamp_s)
            if recoverable:
                self.index = future_index
                self.machine.set_state(self.config.steps[self.index].id, self)
                return [self._advance(event.timestamp_s)]
            critical = any(self.config.steps[item].safety_critical for item in skipped)
            violated_step = next(
                (self.config.steps[item] for item in skipped if self.config.steps[item].violation_message),
                next((self.config.steps[item] for item in skipped if self.config.steps[item].safety_critical), expected),
            )
            message = violated_step.violation_message or f"Out-of-order evidence: {event.evidence}"
            short_message = violated_step.violation_short_message or "Protocol order issue"
            violation = self._emit(ViolationEvent(event.timestamp_s, message, short_message, critical, expected.id))
            if critical:
                self.blocked = True
                self.machine.set_state("BLOCKED", self)
            return [violation]
        return []
