"""Object tracking and object-state estimation.

Detection alone answers "is there a red container in frame". Protocol validation
needs "is *this* container, the one that was in storage, now in the tray". That
requires identity across frames, and identity requires tracking.

Two layers:

* :class:`ObjectTracker` -- a compact IoU + centroid tracker with a Kalman-free
  constant-velocity prediction. Deliberately not ByteTrack or DeepSORT: those
  solve crowded multi-person scenes with re-identification embeddings. A payload
  rack has under a dozen rigid objects on a static background, where a
  well-tuned IoU tracker is both sufficient and auditable.

* :class:`ObjectStateMachine` -- promotes a track from a box into a *state*:
  STORED, GRASPED, IN_TRANSIT, PLACED, RELEASED. Protocol steps are then written
  against states and transitions rather than raw detections, which is what makes
  the digital twin possible.

The tracker runs unchanged whether detections come from a trained YOLO model or
from the zone/hand geometry alone, so this module is useful before Tier 2 exists.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from enum import Enum
import itertools
import time

import numpy as np


# ============================================================ detections

@dataclass
class Detection:
    """One detected object in one frame, in pixel space."""

    label: str
    confidence: float
    box: tuple[float, float, float, float]   # x1, y1, x2, y2
    mask_area: float | None = None

    @property
    def centre(self) -> np.ndarray:
        x1, y1, x2, y2 = self.box
        return np.array([(x1 + x2) / 2.0, (y1 + y2) / 2.0], dtype=np.float32)

    @property
    def area(self) -> float:
        x1, y1, x2, y2 = self.box
        return max(0.0, x2 - x1) * max(0.0, y2 - y1)


def iou(a: tuple[float, float, float, float], b: tuple[float, float, float, float]) -> float:
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    iw, ih = max(0.0, ix2 - ix1), max(0.0, iy2 - iy1)
    inter = iw * ih
    if inter <= 0:
        return 0.0
    area_a = max(0.0, ax2 - ax1) * max(0.0, ay2 - ay1)
    area_b = max(0.0, bx2 - bx1) * max(0.0, by2 - by1)
    union = area_a + area_b - inter
    return float(inter / union) if union > 0 else 0.0


# ============================================================ object states

class ObjectState(str, Enum):
    UNKNOWN = "unknown"
    STORED = "stored"          # at rest inside a zone, untouched
    APPROACHED = "approached"  # a hand is near but not holding
    GRASPED = "grasped"        # hand contact + object moves with hand
    IN_TRANSIT = "in_transit"  # moving, not yet at a destination
    PLACED = "placed"          # at rest in a zone after transit
    RELEASED = "released"      # hand withdrawn after placement
    OCCLUDED = "occluded"      # was tracked, currently not visible
    LOST = "lost"              # gone long enough to retire


# Transitions the state machine will accept. Anything else is a protocol
# anomaly worth reporting rather than silently absorbing.
ALLOWED_TRANSITIONS: dict[ObjectState, set[ObjectState]] = {
    ObjectState.UNKNOWN: {ObjectState.STORED, ObjectState.APPROACHED, ObjectState.OCCLUDED},
    ObjectState.STORED: {ObjectState.APPROACHED, ObjectState.OCCLUDED, ObjectState.LOST},
    ObjectState.APPROACHED: {ObjectState.GRASPED, ObjectState.STORED, ObjectState.OCCLUDED},
    ObjectState.GRASPED: {ObjectState.IN_TRANSIT, ObjectState.PLACED, ObjectState.RELEASED, ObjectState.OCCLUDED},
    ObjectState.IN_TRANSIT: {ObjectState.PLACED, ObjectState.GRASPED, ObjectState.OCCLUDED},
    ObjectState.PLACED: {ObjectState.RELEASED, ObjectState.APPROACHED, ObjectState.OCCLUDED},
    ObjectState.RELEASED: {ObjectState.STORED, ObjectState.APPROACHED, ObjectState.OCCLUDED},
    ObjectState.OCCLUDED: set(ObjectState),
    ObjectState.LOST: {ObjectState.STORED, ObjectState.APPROACHED},
}


@dataclass
class StateTransition:
    track_id: int
    label: str
    frm: ObjectState
    to: ObjectState
    zone: str | None
    monotonic: float
    wall: float
    reason: str = ""
    legal: bool = True

    def describe(self) -> str:
        where = f" in {self.zone}" if self.zone else ""
        flag = "" if self.legal else "  [ILLEGAL TRANSITION]"
        return f"{self.label}#{self.track_id}: {self.frm.value} -> {self.to.value}{where}{flag}"


# ============================================================ tracks

@dataclass
class Track:
    """One physical object followed across frames."""

    track_id: int
    label: str
    box: tuple[float, float, float, float]
    confidence: float
    centre: np.ndarray
    velocity: np.ndarray = field(default_factory=lambda: np.zeros(2, dtype=np.float32))
    state: ObjectState = ObjectState.UNKNOWN
    zone: str | None = None
    zone_rack: np.ndarray | None = None
    hits: int = 1
    misses: int = 0
    born: float = field(default_factory=time.monotonic)
    last_seen: float = field(default_factory=time.monotonic)
    state_since: float = field(default_factory=time.monotonic)
    history: deque = field(default_factory=lambda: deque(maxlen=90))
    transitions: list[StateTransition] = field(default_factory=list)

    @property
    def confirmed(self) -> bool:
        """Tracks need corroboration before anything acts on them."""
        return self.hits >= 3

    @property
    def age_s(self) -> float:
        return time.monotonic() - self.born

    @property
    def state_age_s(self) -> float:
        return time.monotonic() - self.state_since

    @property
    def speed(self) -> float:
        return float(np.linalg.norm(self.velocity))

    def predict(self) -> tuple[float, float, float, float]:
        """Constant-velocity box prediction, used when a detection is missed."""
        dx, dy = float(self.velocity[0]), float(self.velocity[1])
        x1, y1, x2, y2 = self.box
        return (x1 + dx, y1 + dy, x2 + dx, y2 + dy)

    def displacement(self, frames: int = 15) -> float:
        if len(self.history) < 2:
            return 0.0
        pts = list(self.history)[-frames:]
        return float(np.linalg.norm(np.asarray(pts[-1]) - np.asarray(pts[0])))

    def to_dict(self) -> dict:
        return {
            "track_id": self.track_id,
            "label": self.label,
            "state": self.state.value,
            "zone": self.zone,
            "confidence": round(self.confidence, 3),
            "speed": round(self.speed, 2),
            "age_s": round(self.age_s, 2),
            "confirmed": self.confirmed,
        }


class ObjectTracker:
    """IoU + centroid tracker with velocity-based recovery through occlusion."""

    def __init__(
        self,
        *,
        iou_threshold: float = 0.28,
        max_misses: int = 20,
        max_centre_distance: float = 140.0,
    ) -> None:
        self.iou_threshold = iou_threshold
        self.max_misses = max_misses
        self.max_centre_distance = max_centre_distance
        self.tracks: dict[int, Track] = {}
        self._ids = itertools.count(1)

    def _match(self, detections: list[Detection]) -> dict[int, int]:
        """Greedy association, highest score first. Returns {det_idx: track_id}."""
        if not self.tracks or not detections:
            return {}
        pairs = []
        for di, det in enumerate(detections):
            for tid, tr in self.tracks.items():
                if tr.label != det.label:
                    continue
                overlap = iou(det.box, tr.predict())
                dist = float(np.linalg.norm(det.centre - tr.centre))
                if overlap < self.iou_threshold and dist > self.max_centre_distance:
                    continue
                # Blend overlap with proximity so small fast objects still match
                score = overlap + max(0.0, 1.0 - dist / self.max_centre_distance) * 0.5
                pairs.append((score, di, tid))

        pairs.sort(reverse=True)
        assigned: dict[int, int] = {}
        used_tracks: set[int] = set()
        for _score, di, tid in pairs:
            if di in assigned or tid in used_tracks:
                continue
            assigned[di] = tid
            used_tracks.add(tid)
        return assigned

    def update(self, detections: list[Detection]) -> list[Track]:
        """Advance the tracker one frame. Returns the live tracks."""
        assigned = self._match(detections)
        now = time.monotonic()
        matched_tracks: set[int] = set()

        for di, det in enumerate(detections):
            tid = assigned.get(di)
            if tid is None:
                tid = next(self._ids)
                self.tracks[tid] = Track(
                    track_id=tid, label=det.label, box=det.box,
                    confidence=det.confidence, centre=det.centre.copy(),
                )
                self.tracks[tid].history.append(det.centre.copy())
                continue

            tr = self.tracks[tid]
            new_centre = det.centre
            tr.velocity = 0.6 * tr.velocity + 0.4 * (new_centre - tr.centre)
            tr.centre = new_centre.copy()
            tr.box = det.box
            tr.confidence = det.confidence
            tr.hits += 1
            tr.misses = 0
            tr.last_seen = now
            tr.history.append(new_centre.copy())
            matched_tracks.add(tid)

        for tid, tr in list(self.tracks.items()):
            if tid in matched_tracks:
                continue
            tr.misses += 1
            tr.box = tr.predict()
            tr.centre = tr.centre + tr.velocity
            if tr.misses > self.max_misses:
                del self.tracks[tid]

        return [t for t in self.tracks.values() if t.misses == 0 or t.confirmed]

    def confirmed_tracks(self) -> list[Track]:
        return [t for t in self.tracks.values() if t.confirmed]

    def by_label(self, label: str) -> list[Track]:
        return [t for t in self.tracks.values() if t.label == label and t.confirmed]

    def reset(self) -> None:
        self.tracks.clear()
        self._ids = itertools.count(1)


# ============================================================ state machine

class ObjectStateMachine:
    """Derives object state from track motion, zone membership and hand contact.

    The rules are deliberately explicit rather than learned. For a system that
    has to justify itself to a reviewer, "the object entered the tray, the hand
    withdrew, and it stayed put for 1.4 s" is a far better answer than a
    softmax score -- and it is testable without a camera.
    """

    def __init__(
        self,
        *,
        move_speed: float = 3.5,        # px/frame above which an object is moving
        settle_s: float = 0.6,          # rest required before PLACED
        contact_distance: float = 90.0, # px hand-to-object for contact
    ) -> None:
        self.move_speed = move_speed
        self.settle_s = settle_s
        self.contact_distance = contact_distance
        self.transitions: list[StateTransition] = []

    def _set(self, track: Track, new: ObjectState, zone: str | None, reason: str) -> StateTransition | None:
        if track.state is new:
            return None
        legal = new in ALLOWED_TRANSITIONS.get(track.state, set(ObjectState))
        t = StateTransition(
            track_id=track.track_id, label=track.label, frm=track.state, to=new,
            zone=zone, monotonic=time.monotonic(), wall=time.time(),
            reason=reason, legal=legal,
        )
        track.state = new
        track.state_since = time.monotonic()
        track.transitions.append(t)
        self.transitions.append(t)
        if len(self.transitions) > 500:
            self.transitions = self.transitions[-500:]
        return t

    def update(
        self,
        tracks: list[Track],
        hands_px: list[np.ndarray],
        zones,
        rack,
    ) -> list[StateTransition]:
        """Update every track's state. Returns the transitions that fired."""
        fired: list[StateTransition] = []

        for tr in tracks:
            if not tr.confirmed:
                continue

            # locate the object in rack space
            zone_name = None
            if rack is not None and zones is not None and len(zones):
                try:
                    rack_pt = rack.to_rack(tr.centre.reshape(1, 2))[0]
                    tr.zone_rack = rack_pt
                    zone_name = zones.locate(rack_pt)
                except Exception:
                    zone_name = None
            tr.zone = zone_name

            near_hand = False
            if hands_px:
                dists = [float(np.linalg.norm(tr.centre - h)) for h in hands_px]
                near_hand = min(dists) <= self.contact_distance

            moving = tr.speed >= self.move_speed
            settled = (not moving) and tr.state_age_s >= self.settle_s

            if tr.misses > 0:
                t = self._set(tr, ObjectState.OCCLUDED, zone_name, "detection lost")
                if t:
                    fired.append(t)
                continue

            if near_hand and moving:
                t = self._set(tr, ObjectState.GRASPED if tr.state in
                              (ObjectState.APPROACHED, ObjectState.STORED, ObjectState.UNKNOWN,
                               ObjectState.PLACED, ObjectState.RELEASED)
                              else ObjectState.IN_TRANSIT,
                              zone_name, "hand contact with co-moving object")
            elif near_hand and not moving:
                if tr.state in (ObjectState.GRASPED, ObjectState.IN_TRANSIT):
                    t = self._set(tr, ObjectState.PLACED, zone_name, "motion stopped while held")
                else:
                    t = self._set(tr, ObjectState.APPROACHED, zone_name, "hand near stationary object")
            elif moving:
                t = self._set(tr, ObjectState.IN_TRANSIT, zone_name, "object moving without hand contact")
            elif settled:
                if tr.state in (ObjectState.GRASPED, ObjectState.IN_TRANSIT, ObjectState.PLACED):
                    t = self._set(tr, ObjectState.RELEASED, zone_name,
                                  f"at rest {tr.state_age_s:.1f}s after transit")
                elif tr.state in (ObjectState.RELEASED, ObjectState.UNKNOWN, ObjectState.OCCLUDED):
                    t = self._set(tr, ObjectState.STORED, zone_name, "at rest in zone")
                else:
                    t = None
            else:
                t = None

            if t:
                fired.append(t)

        return fired

    def snapshot(self, tracks: list[Track]) -> dict:
        return {
            t.label + "#" + str(t.track_id): {
                "state": t.state.value,
                "zone": t.zone,
                "for_s": round(t.state_age_s, 2),
            }
            for t in tracks if t.confirmed
        }

    def reset(self) -> None:
        self.transitions.clear()
