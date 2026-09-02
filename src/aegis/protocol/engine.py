"""Sequence-validation engine.

This is the component that turns "we recognised an action" into
"the experiment is / is not being performed correctly".

Design notes
------------
The engine is deliberately a *pure* state machine: it takes observations and a
timestamp, and returns events. It touches no camera, no audio, no disk. That
makes the safety-critical logic unit-testable without hardware, which is what
lets us claim the sequence validation is verified rather than demoed.

Rules implemented (mapped straight onto the SIH statement):

* ``suggest the next step``      -> ``next_step`` / ``StepArmed`` event
* ``alert when a step is skipped``  -> ``StepSkipped`` (+ ``SafetyBlock`` if the
  skipped step was safety-critical)
* ``out of sequence step is added`` -> ``OutOfSequence`` (repeat of a completed
  step, or an action that belongs to no upcoming step)
* per-step ``timeout``            -> ``StepTimeout`` nudge
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import time
from typing import Iterable

from aegis.protocol.spec import Protocol, Step


class StepState(str, Enum):
    PENDING = "pending"
    ACTIVE = "active"
    DONE = "done"
    SKIPPED = "skipped"
    BLOCKED = "blocked"   # safety-critical step was bypassed; awaiting recovery
    FAILED = "failed"


class Severity(str, Enum):
    INFO = "info"
    SUCCESS = "success"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass
class ProtocolEvent:
    """Anything the engine wants the rest of the system to know about."""

    kind: str
    severity: Severity
    message: str
    speech: str | None = None          # what the voice alert should say
    step_id: int | None = None
    step_name: str | None = None
    confidence: float | None = None
    monotonic: float = field(default_factory=time.monotonic)
    detail: dict = field(default_factory=dict)


@dataclass
class Observation:
    """A stabilised recognition result handed to the engine."""

    action: str | None
    confidence: float
    zone: str | None = None
    hand: str | None = None
    source: str = "heuristic"          # heuristic | learned | manual


@dataclass
class StepRecord:
    step: Step
    state: StepState = StepState.PENDING
    started_at: float | None = None    # wall-clock epoch
    finished_at: float | None = None
    confidence: float = 0.0
    source: str = ""
    note: str = ""

    @property
    def duration_s(self) -> float | None:
        if self.started_at is None or self.finished_at is None:
            return None
        return max(0.0, self.finished_at - self.started_at)


class ProtocolEngine:
    """Validates that observed actions follow the protocol order."""

    def __init__(self, protocol: Protocol, *, clock=time.monotonic) -> None:
        self.protocol = protocol
        self._clock = clock
        self.records: list[StepRecord] = [StepRecord(step) for step in protocol.steps]
        self.cursor = 0                      # index of the expected step
        self.blocked = False                 # safety block latch
        self.block_reason = ""
        self.completed = False
        self.started_wall: float | None = None
        self._step_armed_at = self._clock()
        self._dwell_action: str | None = None
        self._dwell_since: float | None = None
        self._last_violation_at = -1e9
        self._last_violation_key = ""
        self._last_reminder_at = self._clock()
        self._timeout_fired = False

    # ------------------------------------------------------------------ state

    @property
    def current_step(self) -> Step | None:
        if self.completed or self.cursor >= len(self.protocol):
            return None
        return self.protocol[self.cursor]

    @property
    def next_instruction(self) -> str:
        if self.blocked:
            return f"HALTED - {self.block_reason}"
        step = self.current_step
        if step is None:
            return "Experiment complete. All steps verified."
        return step.instruction

    def progress(self) -> tuple[int, int]:
        done = sum(1 for r in self.records if r.state is StepState.DONE)
        return done, len(self.records)

    def snapshot(self) -> dict:
        step = self.current_step
        done, total = self.progress()
        return {
            "experiment": self.protocol.experiment,
            "cursor": self.cursor,
            "blocked": self.blocked,
            "block_reason": self.block_reason,
            "completed": self.completed,
            "done": done,
            "total": total,
            "current_step_id": step.id if step else None,
            "current_step_name": step.name if step else None,
            "next_instruction": self.next_instruction,
            "steps": [
                {
                    "id": r.step.id,
                    "name": r.step.name,
                    "state": r.state.value,
                    "confidence": round(r.confidence, 3),
                    "duration_s": None if r.duration_s is None else round(r.duration_s, 2),
                    "safety_critical": r.step.safety_critical,
                    "note": r.note,
                }
                for r in self.records
            ],
        }

    # ----------------------------------------------------------------- helpers

    def _emit_armed(self) -> list[ProtocolEvent]:
        step = self.current_step
        self._step_armed_at = self._clock()
        self._timeout_fired = False
        self._last_reminder_at = self._clock()
        if step is None:
            return []
        self.records[self.cursor].state = StepState.ACTIVE
        self.records[self.cursor].started_at = time.time()
        return [
            ProtocolEvent(
                kind="step_armed",
                severity=Severity.INFO,
                message=f"Next: {step.name} - {step.instruction}",
                speech=f"Next step. {step.instruction}",
                step_id=step.id,
                step_name=step.name,
            )
        ]

    def _rate_limited(self, key: str) -> bool:
        now = self._clock()
        if key == self._last_violation_key and now - self._last_violation_at < self.protocol.out_of_sequence_cooldown_s:
            return True
        self._last_violation_key = key
        self._last_violation_at = now
        return False

    def _reset_dwell(self) -> None:
        self._dwell_action = None
        self._dwell_since = None

    # ------------------------------------------------------------------- API

    def start(self) -> list[ProtocolEvent]:
        self.started_wall = time.time()
        events = [
            ProtocolEvent(
                kind="session_started",
                severity=Severity.INFO,
                message=f"Session started - {self.protocol.experiment} ({len(self.protocol)} steps)",
                speech=f"Starting {self.protocol.experiment}.",
            )
        ]
        events += self._emit_armed()
        return events

    def acknowledge(self) -> list[ProtocolEvent]:
        """Operator clears a safety block after correcting the situation."""
        if not self.blocked:
            return []
        self.blocked = False
        reason, self.block_reason = self.block_reason, ""
        events = [
            ProtocolEvent(
                kind="block_cleared",
                severity=Severity.INFO,
                message=f"Safety block acknowledged by operator ({reason})",
                speech="Safety block cleared. Resuming.",
                detail={"cleared": reason},
            )
        ]
        events += self._emit_armed()
        return events

    def manual_skip(self) -> list[ProtocolEvent]:
        """Operator deliberately marks the current step as not applicable."""
        step = self.current_step
        if step is None or self.blocked:
            return []
        if not step.allow_manual_skip:
            return [
                ProtocolEvent(
                    kind="skip_refused",
                    severity=Severity.WARNING,
                    message=f"Step {step.id} '{step.name}' is safety-critical and cannot be skipped manually.",
                    speech="This step is safety critical and cannot be skipped.",
                    step_id=step.id,
                    step_name=step.name,
                )
            ]
        rec = self.records[self.cursor]
        rec.state = StepState.SKIPPED
        rec.finished_at = time.time()
        rec.note = "manual skip"
        rec.source = "manual"
        self.cursor += 1
        self._reset_dwell()
        events = [
            ProtocolEvent(
                kind="step_skipped_manual",
                severity=Severity.WARNING,
                message=f"Step {step.id} '{step.name}' skipped by operator.",
                speech=f"Step {step.id} skipped.",
                step_id=step.id,
                step_name=step.name,
            )
        ]
        events += self._finish_or_arm()
        return events

    def force_complete(self) -> list[ProtocolEvent]:
        """Operator confirms the current step manually (recogniser fallback)."""
        step = self.current_step
        if step is None or self.blocked:
            return []
        return self._complete_current(1.0, "manual", note="operator confirmed")

    def _finish_or_arm(self) -> list[ProtocolEvent]:
        if self.cursor >= len(self.protocol):
            self.completed = True
            return [
                ProtocolEvent(
                    kind="session_completed",
                    severity=Severity.SUCCESS,
                    message="All protocol steps accounted for. Experiment complete.",
                    speech="Experiment complete. All steps verified.",
                )
            ]
        return self._emit_armed()

    def _complete_current(self, confidence: float, source: str, note: str = "") -> list[ProtocolEvent]:
        step = self.protocol[self.cursor]
        rec = self.records[self.cursor]
        rec.state = StepState.DONE
        rec.finished_at = time.time()
        if rec.started_at is None:
            rec.started_at = rec.finished_at
        rec.confidence = confidence
        rec.source = source
        rec.note = note
        self.cursor += 1
        self._reset_dwell()
        events = [
            ProtocolEvent(
                kind="step_completed",
                severity=Severity.SUCCESS,
                message=f"Step {step.id} '{step.name}' verified ({confidence:.0%}, {source}).",
                speech=f"Step {step.id} complete.",
                step_id=step.id,
                step_name=step.name,
                confidence=confidence,
                detail={"source": source, "outcome": step.outcome_hint or "nominal"},
            )
        ]
        events += self._finish_or_arm()
        return events

    def _handle_forward_jump(self, target: int, confidence: float, source: str) -> list[ProtocolEvent]:
        """An action belonging to a *later* step fired -> steps were skipped."""
        skipped = list(range(self.cursor, target))
        critical = [i for i in skipped if self.protocol[i].safety_critical]
        names = ", ".join(f"{self.protocol[i].id} ({self.protocol[i].name})" for i in skipped)
        events: list[ProtocolEvent] = []

        if critical:
            first = self.protocol[critical[0]]
            self.blocked = True
            self.block_reason = f"safety-critical step {first.id} '{first.name}' was skipped"
            for i in skipped:
                self.records[i].state = StepState.BLOCKED if i in critical else StepState.SKIPPED
                self.records[i].finished_at = time.time()
                self.records[i].note = (
                    "BYPASSED - safety critical, awaiting recovery" if i in critical else "skipped"
                )
            events.append(
                ProtocolEvent(
                    kind="safety_block",
                    severity=Severity.CRITICAL,
                    message=(
                        f"SAFETY BLOCK. Detected '{self.protocol[target].name}' but "
                        f"safety-critical step {first.id} '{first.name}' was not performed. Halting guidance."
                    ),
                    speech=(
                        f"Warning. Safety critical step {first.id}, {first.name}, was skipped. "
                        "Stop and complete it before continuing."
                    ),
                    step_id=first.id,
                    step_name=first.name,
                    confidence=confidence,
                    detail={"skipped": names, "trigger": self.protocol[target].name},
                )
            )
            # Cursor stays on the first critical step so the operator is guided back to it.
            self.cursor = critical[0]
            self._reset_dwell()
            return events

        for i in skipped:
            self.records[i].state = StepState.SKIPPED
            self.records[i].finished_at = time.time()
            self.records[i].note = "auto-detected skip"
        events.append(
            ProtocolEvent(
                kind="step_skipped",
                severity=Severity.WARNING,
                message=f"Out of sequence: step(s) {names} were skipped. Continuing from step {self.protocol[target].id}.",
                speech=(
                    f"Alert. Step {self.protocol[skipped[0]].id} was skipped. "
                    f"Now performing step {self.protocol[target].id}."
                ),
                step_id=self.protocol[skipped[0]].id,
                step_name=self.protocol[skipped[0]].name,
                detail={"skipped": names},
            )
        )
        self.cursor = target
        events += self._complete_current(confidence, source, note="performed after skip")
        return events

    def observe(self, obs: Observation) -> list[ProtocolEvent]:
        """Feed one stabilised observation. Returns events to publish."""
        now = self._clock()
        events: list[ProtocolEvent] = []

        if self.completed:
            return events

        # --- idle / timeout nudges happen regardless of what was observed ----
        step = self.current_step
        if step is not None and not self.blocked:
            elapsed = now - self._step_armed_at
            if not self._timeout_fired and elapsed > step.timeout_s:
                self._timeout_fired = True
                events.append(
                    ProtocolEvent(
                        kind="step_timeout",
                        severity=Severity.WARNING,
                        message=f"Step {step.id} '{step.name}' has exceeded {step.timeout_s:.0f}s.",
                        speech=f"Step {step.id} is taking longer than expected. {step.instruction}",
                        step_id=step.id,
                        step_name=step.name,
                    )
                )
            elif now - self._last_reminder_at > self.protocol.idle_reminder_s:
                self._last_reminder_at = now
                events.append(
                    ProtocolEvent(
                        kind="step_reminder",
                        severity=Severity.INFO,
                        message=f"Reminder - {step.instruction}",
                        speech=step.instruction,
                        step_id=step.id,
                        step_name=step.name,
                    )
                )

        if obs.action is None:
            self._reset_dwell()
            return events

        # --- while blocked we only listen for the missed critical step ------
        if self.blocked:
            expected = self.current_step
            if expected is not None and obs.action == expected.action and obs.confidence >= expected.min_confidence:
                self.blocked = False
                reason, self.block_reason = self.block_reason, ""
                events.append(
                    ProtocolEvent(
                        kind="block_cleared",
                        severity=Severity.SUCCESS,
                        message=f"Recovery: missed step {expected.id} '{expected.name}' has now been performed.",
                        speech="Good. Safety step recovered.",
                        step_id=expected.id,
                        step_name=expected.name,
                        detail={"cleared": reason},
                    )
                )
                events += self._complete_current(obs.confidence, obs.source, note="recovered after block")
            elif not self._rate_limited(f"blocked:{obs.action}"):
                events.append(
                    ProtocolEvent(
                        kind="blocked_action",
                        severity=Severity.CRITICAL,
                        message=f"Ignored '{obs.action}' - guidance is halted until the missed safety step is completed.",
                        speech="Halted. Complete the missed safety step first.",
                        confidence=obs.confidence,
                    )
                )
            return events

        # --- unknown action -------------------------------------------------
        candidates = self.protocol.indices_of_action(obs.action)
        if not candidates:
            if not self._rate_limited(f"unknown:{obs.action}"):
                events.append(
                    ProtocolEvent(
                        kind="unexpected_action",
                        severity=Severity.WARNING,
                        message=f"Observed '{obs.action}' which is not part of this protocol.",
                        speech="Unexpected action detected. This is not part of the protocol.",
                        confidence=obs.confidence,
                    )
                )
            self._reset_dwell()
            return events

        # --- expected step? -------------------------------------------------
        expected = self.current_step
        if expected is not None and obs.action == expected.action:
            if obs.confidence < expected.min_confidence:
                self._reset_dwell()
                return events
            if expected.zone and obs.zone and obs.zone != expected.zone:
                if not self._rate_limited(f"zone:{obs.action}"):
                    events.append(
                        ProtocolEvent(
                            kind="wrong_zone",
                            severity=Severity.WARNING,
                            message=f"'{expected.name}' seen in zone '{obs.zone}' but expected '{expected.zone}'.",
                            speech=f"Wrong location. Perform this step at the {expected.zone.replace('_', ' ')}.",
                            step_id=expected.id,
                            step_name=expected.name,
                        )
                    )
                self._reset_dwell()
                return events
            # dwell gate: the action must persist to count
            if self._dwell_action != obs.action:
                self._dwell_action = obs.action
                self._dwell_since = now
            if self._dwell_since is not None and (now - self._dwell_since) < expected.dwell_s:
                return events
            events += self._complete_current(obs.confidence, obs.source)
            return events

        # --- an already-completed step repeated ------------------------------
        past = [i for i in candidates if self.records[i].state in (StepState.DONE, StepState.SKIPPED)
                and i < self.cursor]
        future = [i for i in candidates if i > self.cursor]

        if future and obs.confidence >= self.protocol[future[0]].min_confidence:
            self._reset_dwell()
            events += self._handle_forward_jump(future[0], obs.confidence, obs.source)
            return events

        if past:
            if not self._rate_limited(f"repeat:{obs.action}"):
                prev = self.protocol[past[-1]]
                nxt = self.current_step
                events.append(
                    ProtocolEvent(
                        kind="out_of_sequence",
                        severity=Severity.WARNING,
                        message=(
                            f"Out of sequence: step {prev.id} '{prev.name}' was repeated. "
                            + (f"Expected step {nxt.id} '{nxt.name}'." if nxt else "")
                        ),
                        speech=(
                            f"Out of sequence. That was step {prev.id}, already completed. "
                            + (f"Please perform step {nxt.id}. {nxt.instruction}" if nxt else "")
                        ),
                        step_id=prev.id,
                        step_name=prev.name,
                        confidence=obs.confidence,
                    )
                )
        self._reset_dwell()
        return events
