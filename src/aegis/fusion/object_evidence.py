"""Does the object in the operator's hand match the one the step calls for?

Tier 0 verifies *a hand doing the right kind of motion in the right place*. That
is genuinely useful and it is also genuinely blind: perform the correct gesture
holding the wrong container and Tier 0 confirms the step. Closing that gap is the
whole reason the detector exists, and this module is where the detections finally
change a decision.

Three outcomes matter, and they are deliberately not collapsed into one number:

``MATCH``
    A confirmed track carrying the expected label is the object nearest the
    operator's hand. Supports the step.

``MISMATCH``
    A confirmed track is in hand, and it is *not* the expected label. This is the
    interesting one -- it actively argues against the step rather than merely
    failing to support it, and it is the only object outcome that can reject.

``ABSENT``
    Nothing confirmed is near the hand. Could be a genuinely empty hand, could be
    an occluded object, could be a detector that has not warmed up. This is not
    evidence of wrongdoing and must never be scored as though it were, so it
    lands mid-scale and lets the other sources decide.

The asymmetry between MISMATCH and ABSENT is the important design choice here. A
system that treats "I can't see the object" the same as "I can see the wrong
object" will fabricate violations every time a sleeve blocks the camera.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

import numpy as np

from aegis.fusion.evidence import Evidence, Source


class ObjectMatch(str, Enum):
    MATCH = "match"
    MISMATCH = "mismatch"
    ABSENT = "absent"
    NOT_REQUIRED = "not_required"     # the step names no object
    NO_DETECTOR = "no_detector"       # Tier 2 unavailable this session


#: How strongly each outcome argues for the step. MISMATCH sits low enough to
#: drag a fused score under any threshold in the protocol; ABSENT sits at the
#: neutral point so an unseen object neither helps nor hurts.
_SCORES = {
    ObjectMatch.MATCH: 0.95,
    ObjectMatch.MISMATCH: 0.05,
    ObjectMatch.ABSENT: 0.40,
    ObjectMatch.NOT_REQUIRED: 0.50,
    ObjectMatch.NO_DETECTOR: 0.50,
}

#: Trust placed in the object channel. MISMATCH is weighted far above the others
#: because a confidently detected wrong object is the single most decisive piece
#: of evidence this system can produce -- and because the failure mode it guards
#: against (silently approving the wrong container) is the expensive one.
_WEIGHTS = {
    ObjectMatch.MATCH: 0.30,
    ObjectMatch.MISMATCH: 0.55,
    ObjectMatch.ABSENT: 0.10,
    ObjectMatch.NOT_REQUIRED: 0.0,
    ObjectMatch.NO_DETECTOR: 0.0,
}


@dataclass
class ObjectAssessment:
    """The object channel's verdict on one step, with its reasoning intact."""

    match: ObjectMatch
    expected: str | None = None
    observed: str | None = None
    track_id: int | None = None
    distance_px: float | None = None
    confidence: float = 0.0
    detail: dict = field(default_factory=dict)

    @property
    def score(self) -> float:
        return _SCORES[self.match]

    @property
    def weight(self) -> float:
        return _WEIGHTS[self.match]

    @property
    def contributes(self) -> bool:
        return self.weight > 0.0

    @property
    def label(self) -> str:
        if self.match is ObjectMatch.MATCH:
            return f"'{self.observed}' in hand as expected"
        if self.match is ObjectMatch.MISMATCH:
            return f"WRONG OBJECT: expected '{self.expected}', hand holds '{self.observed}'"
        if self.match is ObjectMatch.ABSENT:
            return f"'{self.expected}' not visible near the hand"
        if self.match is ObjectMatch.NO_DETECTOR:
            return "object detector unavailable"
        return "step names no specific object"

    def as_evidence(self) -> Evidence | None:
        """Render as fuser input, or None when this channel has nothing to say."""
        if not self.contributes:
            return None
        return Evidence(
            source=Source.OBJECT,
            label=self.label,
            score=self.score,
            weight=self.weight,
            detail={
                "match": self.match.value,
                "expected": self.expected,
                "observed": self.observed,
                "track_id": self.track_id,
                "distance_px": (round(self.distance_px, 1)
                                if self.distance_px is not None else None),
                "detector_confidence": round(self.confidence, 3),
                **self.detail,
            },
        )


class ObjectVerifier:
    """Decides which tracked object is 'in hand' and whether it is the right one.

    'In hand' is deliberately geometric rather than learned: the nearest confirmed
    track whose centre falls within ``contact_px`` of a hand centroid, preferring
    tracks the state machine already believes are grasped. Geometry is what a
    reviewer can check against the recorded clip; a learned in-hand classifier is
    one more thing that could be wrong without anyone noticing.
    """

    def __init__(self, *, contact_px: float = 110.0, min_track_confidence: float = 0.35) -> None:
        self.contact_px = float(contact_px)
        self.min_track_confidence = float(min_track_confidence)

    def assess(
        self,
        expected: str | None,
        tracks,
        hands_px,
        *,
        detector_available: bool = True,
    ) -> ObjectAssessment:
        """Judge one frame. ``hands_px`` is a list of (x, y) hand centroids."""
        if not expected:
            return ObjectAssessment(ObjectMatch.NOT_REQUIRED)
        if not detector_available:
            return ObjectAssessment(ObjectMatch.NO_DETECTOR, expected=expected)

        confirmed = [
            t for t in (tracks or [])
            if getattr(t, "confirmed", False)
            and float(getattr(t, "confidence", 0.0)) >= self.min_track_confidence
        ]
        if not confirmed or not len(hands_px or []):
            return ObjectAssessment(
                ObjectMatch.ABSENT, expected=expected,
                detail={"reason": "no confirmed tracks" if not confirmed else "no hands visible"},
            )

        def nearest(candidates):
            found, best_distance = None, float("inf")
            for track in candidates:
                centre = np.asarray(track.centre, dtype=np.float32)
                for hand in hands_px:
                    distance = float(np.linalg.norm(centre - np.asarray(hand, dtype=np.float32)))
                    if distance < best_distance:
                        found, best_distance = track, distance
            return found, best_distance

        # A track the state machine already calls grasped outranks every other
        # candidate outright, rather than winning by a distance fudge factor.
        # An object resting under the operator's palm should not displace the one
        # actually in their fingers just because its centroid is a few pixels
        # closer -- and "it was held" is a reason a reviewer can check on video.
        held = [t for t in confirmed
                if str(getattr(getattr(t, "state", ""), "value", getattr(t, "state", "")))
                .lower().endswith("grasped")]

        best, best_distance = nearest(held)
        if best is None or best_distance > self.contact_px:
            best, best_distance = nearest(confirmed)

        if best is None or best_distance > self.contact_px:
            return ObjectAssessment(
                ObjectMatch.ABSENT, expected=expected,
                distance_px=(best_distance if best is not None else None),
                detail={"reason": "nearest object beyond contact range",
                        "contact_px": self.contact_px},
            )

        observed = str(getattr(best, "label", "") or "")
        match = ObjectMatch.MATCH if observed == expected else ObjectMatch.MISMATCH
        return ObjectAssessment(
            match,
            expected=expected,
            observed=observed,
            track_id=int(getattr(best, "track_id", 0)),
            distance_px=best_distance,
            confidence=float(getattr(best, "confidence", 0.0)),
            detail={"track_state": str(getattr(best, "state", "unknown"))},
        )
