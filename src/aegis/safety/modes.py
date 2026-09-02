"""Explicit operating modes.

The console currently has implicit state: whether a pipeline exists, whether it
is recording, whether a model loaded. Implicit state is why GUIs end up with
buttons that are enabled when they should not be, and why an operator can start
a mission run while the system is still in a degraded configuration.

Making the mode explicit does three things:

* the GUI can enable exactly the controls that make sense,
* the log records *what the system thought it was doing* at each moment, and
* illegal transitions (CALIBRATION straight to MISSION without saving zones)
  become impossible rather than merely discouraged.

The transition table is the specification. It is small enough to read in one
sitting, which is the point.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import time
from typing import Callable


class Mode(str, Enum):
    STANDBY = "standby"                # idle, nothing running
    CALIBRATION = "calibration"        # defining rack quad and zones
    DATA_COLLECTION = "data_collection"  # recording labelled clips
    MISSION = "mission"                # live protocol validation
    DEGRADED = "degraded"              # running, but a subsystem is impaired
    SAFE = "safe"                      # validation suspended; observation only
    REPLAY = "replay"                  # re-running recorded video
    SHUTDOWN = "shutdown"

    @property
    def label(self) -> str:
        return self.value.replace("_", " ").upper()

    @property
    def validates(self) -> bool:
        """Does this mode advance the protocol? SAFE deliberately does not."""
        return self in (Mode.MISSION, Mode.DEGRADED, Mode.REPLAY)

    @property
    def records(self) -> bool:
        return self in (Mode.MISSION, Mode.DEGRADED, Mode.DATA_COLLECTION)


TRANSITIONS: dict[Mode, set[Mode]] = {
    Mode.STANDBY: {Mode.CALIBRATION, Mode.DATA_COLLECTION, Mode.MISSION, Mode.REPLAY, Mode.SHUTDOWN},
    Mode.CALIBRATION: {Mode.STANDBY, Mode.SHUTDOWN},
    Mode.DATA_COLLECTION: {Mode.STANDBY, Mode.SHUTDOWN},
    Mode.MISSION: {Mode.DEGRADED, Mode.SAFE, Mode.STANDBY, Mode.SHUTDOWN},
    Mode.DEGRADED: {Mode.MISSION, Mode.SAFE, Mode.STANDBY, Mode.SHUTDOWN},
    Mode.SAFE: {Mode.MISSION, Mode.DEGRADED, Mode.STANDBY, Mode.SHUTDOWN},
    Mode.REPLAY: {Mode.STANDBY, Mode.SHUTDOWN},
    Mode.SHUTDOWN: set(),
}


@dataclass
class ModeChange:
    frm: Mode
    to: Mode
    reason: str
    wall: float = field(default_factory=time.time)
    monotonic: float = field(default_factory=time.monotonic)
    automatic: bool = False

    def describe(self) -> str:
        how = "auto" if self.automatic else "operator"
        return f"{self.frm.label} -> {self.to.label} ({how}: {self.reason})"


class ModeManager:
    """Owns the current mode and enforces legal transitions."""

    def __init__(self, initial: Mode = Mode.STANDBY) -> None:
        self._mode = initial
        self.history: list[ModeChange] = []
        self._listeners: list[Callable[[ModeChange], None]] = []
        self._entered = time.monotonic()

    @property
    def mode(self) -> Mode:
        return self._mode

    @property
    def time_in_mode_s(self) -> float:
        return time.monotonic() - self._entered

    def on_change(self, callback: Callable[[ModeChange], None]) -> None:
        self._listeners.append(callback)

    def can_enter(self, target: Mode) -> bool:
        return target in TRANSITIONS.get(self._mode, set())

    def request(self, target: Mode, reason: str = "", *, automatic: bool = False) -> ModeChange | None:
        """Attempt a transition. Returns None and stays put if illegal."""
        if target is self._mode:
            return None
        if not self.can_enter(target):
            return None
        change = ModeChange(self._mode, target, reason or "unspecified", automatic=automatic)
        self._mode = target
        self._entered = time.monotonic()
        self.history.append(change)
        if len(self.history) > 200:
            self.history = self.history[-200:]
        for cb in list(self._listeners):
            try:
                cb(change)
            except Exception:
                pass
        return change

    # ---------------------------------------------------------- auto policy

    def evaluate(self, *, camera_usable: bool, rack_usable: bool,
                 critical_worker_fault: bool) -> ModeChange | None:
        """Move between MISSION / DEGRADED / SAFE from subsystem health.

        The policy is deliberately conservative: anything that makes protocol
        validation unsound drops to SAFE, where the system keeps observing and
        recording but stops asserting that steps were completed. Continuing to
        validate on unusable input is the failure this exists to prevent.
        """
        if self._mode not in (Mode.MISSION, Mode.DEGRADED, Mode.SAFE):
            return None

        if critical_worker_fault or not camera_usable:
            reason = ("critical worker faulted" if critical_worker_fault
                      else "camera unusable")
            return self.request(Mode.SAFE, reason, automatic=True)

        if not rack_usable:
            return self.request(Mode.SAFE, "rack not localised", automatic=True)

        if self._mode is Mode.SAFE:
            return self.request(Mode.MISSION, "subsystems recovered", automatic=True)

        return None

    def snapshot(self) -> dict:
        return {
            "mode": self._mode.value,
            "label": self._mode.label,
            "validates": self._mode.validates,
            "records": self._mode.records,
            "time_in_mode_s": round(self.time_in_mode_s, 1),
            "allowed_next": sorted(m.value for m in TRANSITIONS.get(self._mode, set())),
        }
