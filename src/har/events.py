"""Typed messages exchanged between asynchronous HAR pipeline stages."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class Detection:
    """Tracked object detection in pixel coordinates."""

    cls: str
    conf: float
    xyxy: tuple[float, float, float, float]
    track_id: int | None = None


@dataclass(frozen=True)
class HandLandmark:
    """Normalized MediaPipe landmark with an optional visibility score."""

    x: float
    y: float
    z: float = 0.0
    visibility: float = 1.0


@dataclass(frozen=True)
class HandState:
    """Landmarks seen in a single frame, indexed by left/right hand."""

    timestamp_s: float
    hands: dict[str, tuple[HandLandmark, ...]]


@dataclass(frozen=True)
class InteractionEvent:
    """A material change in a hand-to-object interaction."""

    timestamp_s: float
    hand: str
    object_class: str
    track_id: int | None
    interaction: str
    grasped: bool
    overlap: float

    @property
    def evidence(self) -> str:
        """Stable, config-friendly representation used by the protocol FSM."""

        return f"{self.object_class}:{self.interaction}"


@dataclass(frozen=True)
class FSMTransitionEvent:
    """A protocol state transition intended for output sinks."""

    timestamp_s: float
    from_step: str
    to_step: str
    message: str
    short_message: str


@dataclass(frozen=True)
class ViolationEvent:
    """An out-of-order or skipped-protocol observation."""

    timestamp_s: float
    message: str
    short_message: str
    safety_critical: bool
    expected_step: str | None = None


def event_to_dict(event: Any) -> dict[str, Any]:
    """Convert a typed event to a JSON-compatible payload."""

    payload = asdict(event)
    payload["event_type"] = type(event).__name__
    return payload
