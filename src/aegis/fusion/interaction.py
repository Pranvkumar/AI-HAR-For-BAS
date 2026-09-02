"""Hand-object interaction: symbolic events instead of raw geometry.

A neural network asked to classify "transfer sample to tray" from pixels has to
implicitly discover that a hand approached, closed, co-moved with an object,
entered a region, and opened. That is a lot to learn from 315 clips.

This module computes those facts directly and emits them as discrete, named
events. The temporal model then only has to learn how events compose into
protocol steps -- a far easier problem -- and the deterministic tier can verify
steps from the events alone, with an explanation a human can check.

Events, in the order they normally occur for a pick-and-place:

    HAND_APPROACH -> CONTACT_BEGIN -> GRASP_CONFIRMED -> OBJECT_LIFTED
        -> OBJECT_MOVING -> ZONE_ENTER -> RELEASE_CONFIRMED -> CONTACT_END

Every event carries the evidence that produced it, so the audit log can answer
"why did you think it was grasped" without re-running the video.

The engine degrades cleanly: with no object detector it still emits hand-only
events (HAND_APPROACH, ZONE_ENTER, ZONE_EXIT, GRIP_CLOSE, GRIP_OPEN), which is
exactly what Tier 0 consumes today.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from enum import Enum
import time

import numpy as np


class EventType(str, Enum):
    HAND_APPROACH = "HAND_APPROACH"
    CONTACT_BEGIN = "CONTACT_BEGIN"
    GRASP_CONFIRMED = "GRASP_CONFIRMED"
    OBJECT_LIFTED = "OBJECT_LIFTED"
    OBJECT_MOVING = "OBJECT_MOVING"
    ZONE_ENTER = "ZONE_ENTER"
    ZONE_EXIT = "ZONE_EXIT"
    RELEASE_CONFIRMED = "RELEASE_CONFIRMED"
    CONTACT_END = "CONTACT_END"
    GRIP_CLOSE = "GRIP_CLOSE"
    GRIP_OPEN = "GRIP_OPEN"
    HAND_WITHDRAW = "HAND_WITHDRAW"


@dataclass
class InteractionEvent:
    """One symbolic fact about the scene, with the numbers that justified it."""

    type: EventType
    hand: str | None = None
    object_label: str | None = None
    object_id: int | None = None
    zone: str | None = None
    confidence: float = 1.0
    monotonic: float = field(default_factory=time.monotonic)
    wall: float = field(default_factory=time.time)
    evidence: dict = field(default_factory=dict)

    def describe(self) -> str:
        parts = [self.type.value]
        if self.hand:
            parts.append(f"hand={self.hand}")
        if self.object_label:
            oid = f"#{self.object_id}" if self.object_id is not None else ""
            parts.append(f"object={self.object_label}{oid}")
        if self.zone:
            parts.append(f"zone={self.zone}")
        return "  ".join(parts)

    def to_dict(self) -> dict:
        return {
            "type": self.type.value,
            "hand": self.hand,
            "object": self.object_label,
            "object_id": self.object_id,
            "zone": self.zone,
            "confidence": round(self.confidence, 3),
            "wall": self.wall,
            "evidence": self.evidence,
        }


@dataclass
class HandContext:
    """Per-hand rolling state the engine needs to detect transitions."""

    grip_history: deque = field(default_factory=lambda: deque(maxlen=14))
    zone: str | None = None
    contact_object: int | None = None
    contact_since: float | None = None
    approaching: int | None = None
    last_centre: np.ndarray | None = None

    def grip_trend(self) -> float:
        vals = [v for v in self.grip_history if v is not None]
        if len(vals) < 6:
            return 0.0
        half = len(vals) // 2
        return float(np.mean(vals[half:]) - np.mean(vals[:half]))

    def grip_now(self) -> float | None:
        vals = [v for v in self.grip_history if v is not None]
        return vals[-1] if vals else None


class InteractionEngine:
    """Turns landmarks + tracks + zones into a stream of symbolic events."""

    def __init__(
        self,
        *,
        approach_distance: float = 160.0,   # px, hand-to-object
        contact_distance: float = 85.0,     # px, closer than this counts as contact
        grasp_grip_max: float = 0.95,       # aperture below this is a closed hand
        release_grip_min: float = 1.15,     # aperture above this is an open hand
        comotion_tolerance: float = 0.55,   # object velocity vs hand velocity
        contact_dwell_s: float = 0.25,
        history: int = 400,
    ) -> None:
        self.approach_distance = approach_distance
        self.contact_distance = contact_distance
        self.grasp_grip_max = grasp_grip_max
        self.release_grip_min = release_grip_min
        self.comotion_tolerance = comotion_tolerance
        self.contact_dwell_s = contact_dwell_s
        self.hands: dict[str, HandContext] = {"left": HandContext(), "right": HandContext()}
        self.events: list[InteractionEvent] = []
        self._history = history

    # ---------------------------------------------------------------- helpers

    def _emit(self, event: InteractionEvent, out: list[InteractionEvent]) -> None:
        self.events.append(event)
        if len(self.events) > self._history:
            self.events = self._history and self.events[-self._history:]
        out.append(event)

    @staticmethod
    def _co_moving(hand_vel: np.ndarray, obj_vel: np.ndarray, tolerance: float) -> tuple[bool, float]:
        """Is the object moving with the hand? Returns (verdict, agreement)."""
        hs = float(np.linalg.norm(hand_vel))
        os_ = float(np.linalg.norm(obj_vel))
        if hs < 1.0 and os_ < 1.0:
            return False, 0.0
        if hs < 0.5:
            return False, 0.0
        cos = float(np.dot(hand_vel, obj_vel) / ((hs * os_) + 1e-6))
        ratio = min(os_, hs) / (max(os_, hs) + 1e-6)
        agreement = max(0.0, cos) * ratio
        return agreement >= tolerance, agreement

    # ------------------------------------------------------------------- main

    def update(
        self,
        perception,          # PerceptionResult
        tracks,              # list[Track] (may be empty)
        zones,
        rack,
    ) -> list[InteractionEvent]:
        """Process one frame. Returns only the events that fired this frame."""
        out: list[InteractionEvent] = []
        confirmed = [t for t in (tracks or []) if getattr(t, "confirmed", False)]

        for side in ("left", "right"):
            ctx = self.hands[side]
            hand = perception.hand(side) if perception is not None else None

            if hand is None:
                if ctx.contact_object is not None:
                    self._emit(InteractionEvent(
                        EventType.CONTACT_END, hand=side, object_id=ctx.contact_object,
                        evidence={"reason": "hand no longer visible"},
                    ), out)
                    ctx.contact_object = None
                    ctx.contact_since = None
                if ctx.zone is not None:
                    self._emit(InteractionEvent(EventType.ZONE_EXIT, hand=side, zone=ctx.zone,
                                                evidence={"reason": "hand lost"}), out)
                    ctx.zone = None
                ctx.grip_history.append(None)
                ctx.last_centre = None
                continue

            centre_px = hand.centroid_px
            hand_vel = (centre_px - ctx.last_centre) if ctx.last_centre is not None else np.zeros(2, np.float32)
            ctx.last_centre = centre_px.copy()

            # --- grip transitions -------------------------------------------
            grip = hand.grip_aperture()
            previous = ctx.grip_now()
            ctx.grip_history.append(grip)
            trend = ctx.grip_trend()
            if previous is not None:
                if previous >= self.grasp_grip_max > grip and trend < 0:
                    self._emit(InteractionEvent(
                        EventType.GRIP_CLOSE, hand=side, confidence=min(1.0, abs(trend) * 6),
                        evidence={"aperture": round(grip, 3), "trend": round(trend, 4)},
                    ), out)
                elif previous <= self.release_grip_min < grip and trend > 0:
                    self._emit(InteractionEvent(
                        EventType.GRIP_OPEN, hand=side, confidence=min(1.0, abs(trend) * 6),
                        evidence={"aperture": round(grip, 3), "trend": round(trend, 4)},
                    ), out)

            # --- zone transitions -------------------------------------------
            zone_now = None
            if rack is not None and zones is not None and len(zones):
                try:
                    rack_pt = np.asarray(hand.points_rack).mean(axis=0) if hand.points_rack is not None \
                        else rack.to_rack(centre_px.reshape(1, 2))[0]
                    zone_now = zones.locate(rack_pt)
                except Exception:
                    zone_now = None

            if zone_now != ctx.zone:
                if ctx.zone is not None:
                    self._emit(InteractionEvent(EventType.ZONE_EXIT, hand=side, zone=ctx.zone), out)
                if zone_now is not None:
                    self._emit(InteractionEvent(EventType.ZONE_ENTER, hand=side, zone=zone_now), out)
                ctx.zone = zone_now

            if not confirmed:
                continue

            # --- nearest object ---------------------------------------------
            distances = [(float(np.linalg.norm(centre_px - t.centre)), t) for t in confirmed]
            distances.sort(key=lambda p: p[0])
            distance, nearest = distances[0]

            # approach
            if distance <= self.approach_distance and ctx.approaching != nearest.track_id \
                    and distance > self.contact_distance:
                ctx.approaching = nearest.track_id
                self._emit(InteractionEvent(
                    EventType.HAND_APPROACH, hand=side, object_label=nearest.label,
                    object_id=nearest.track_id, zone=nearest.zone,
                    confidence=float(np.clip(1.0 - distance / self.approach_distance, 0, 1)),
                    evidence={"distance_px": round(distance, 1)},
                ), out)

            in_contact = distance <= self.contact_distance

            if in_contact and ctx.contact_object != nearest.track_id:
                ctx.contact_object = nearest.track_id
                ctx.contact_since = time.monotonic()
                self._emit(InteractionEvent(
                    EventType.CONTACT_BEGIN, hand=side, object_label=nearest.label,
                    object_id=nearest.track_id, zone=nearest.zone,
                    evidence={"distance_px": round(distance, 1)},
                ), out)

            elif not in_contact and ctx.contact_object is not None:
                self._emit(InteractionEvent(
                    EventType.CONTACT_END, hand=side, object_id=ctx.contact_object,
                    evidence={"distance_px": round(distance, 1)},
                ), out)
                ctx.contact_object = None
                ctx.contact_since = None
                ctx.approaching = None

            # --- grasp / release confirmation -------------------------------
            if ctx.contact_object == nearest.track_id and ctx.contact_since is not None:
                held = time.monotonic() - ctx.contact_since
                co_moving, agreement = self._co_moving(hand_vel, nearest.velocity, self.comotion_tolerance)
                closed = grip <= self.grasp_grip_max

                if held >= self.contact_dwell_s and closed and co_moving:
                    self._emit(InteractionEvent(
                        EventType.GRASP_CONFIRMED, hand=side, object_label=nearest.label,
                        object_id=nearest.track_id, zone=nearest.zone,
                        confidence=float(np.clip(0.5 + agreement / 2, 0, 1)),
                        evidence={
                            "aperture": round(grip, 3),
                            "co_motion": round(agreement, 3),
                            "contact_s": round(held, 2),
                        },
                    ), out)
                    if nearest.displacement(20) > 25:
                        self._emit(InteractionEvent(
                            EventType.OBJECT_LIFTED, hand=side, object_label=nearest.label,
                            object_id=nearest.track_id, zone=nearest.zone,
                            evidence={"displacement_px": round(nearest.displacement(20), 1)},
                        ), out)

                if grip >= self.release_grip_min and not co_moving and nearest.speed < 1.5:
                    self._emit(InteractionEvent(
                        EventType.RELEASE_CONFIRMED, hand=side, object_label=nearest.label,
                        object_id=nearest.track_id, zone=nearest.zone,
                        confidence=float(np.clip(grip / 2.0, 0, 1)),
                        evidence={"aperture": round(grip, 3), "object_speed": round(nearest.speed, 2)},
                    ), out)

        # object motion is hand-independent
        for t in confirmed:
            if t.speed >= 4.0:
                self._emit(InteractionEvent(
                    EventType.OBJECT_MOVING, object_label=t.label, object_id=t.track_id,
                    zone=t.zone, evidence={"speed_px": round(t.speed, 2)},
                ), out)

        return out

    # ------------------------------------------------------------------ query

    def recent(self, seconds: float = 3.0, types: set[EventType] | None = None) -> list[InteractionEvent]:
        cutoff = time.monotonic() - seconds
        return [e for e in self.events
                if e.monotonic >= cutoff and (types is None or e.type in types)]

    def has_recent(self, event_type: EventType, seconds: float = 3.0, **match) -> bool:
        for e in self.recent(seconds, {event_type}):
            if all(getattr(e, k, None) == v for k, v in match.items()):
                return True
        return False

    def reset(self) -> None:
        self.events.clear()
        for ctx in self.hands.values():
            ctx.grip_history.clear()
            ctx.zone = None
            ctx.contact_object = None
            ctx.contact_since = None
            ctx.approaching = None
            ctx.last_centre = None
