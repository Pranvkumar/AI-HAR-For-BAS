"""Rack localisation confidence manager.

The rack tracker already degrades gracefully: live ArUco, then a held homography
during brief occlusion, then a calibrated static quad, then whole-image
normalisation. What it did not do was *tell anyone* which of those it was using,
or how much to trust the result.

That silence is the dangerous part. Whole-image normalisation is not a rack
frame at all -- zone membership computed against it is meaningless -- yet
downstream code would happily keep validating steps.

This manager formalises the chain into a traffic light:

    GREEN   live fiducials, four markers, fresh homography
    YELLOW  held or static: usable, but zone edges may have drifted
    RED     no rack frame: zone-based evidence must be vetoed

It also tracks *homography age*, because a held frame that was good 20 ms ago is
very different from one held for four seconds while the operator reorganised the
rack underneath it.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from enum import Enum
import time

import numpy as np


class RackMode(str, Enum):
    ARUCO = "aruco"           # live marker detection this frame
    HELD = "aruco_hold"       # last good marker frame, within grace
    STATIC = "static"         # operator-calibrated quad
    IDENTITY = "identity"     # whole image; not a rack frame
    UNKNOWN = "unknown"


class RackHealth(str, Enum):
    GREEN = "green"
    YELLOW = "yellow"
    RED = "red"

    @property
    def usable_for_zones(self) -> bool:
        return self is not RackHealth.RED


@dataclass
class RackStatus:
    mode: RackMode = RackMode.UNKNOWN
    health: RackHealth = RackHealth.RED
    confidence: float = 0.0
    homography_age_s: float = 0.0
    visible_markers: int = 0
    roll_deg: float = 0.0
    stability: float = 1.0            # 1.0 = rock steady, 0 = jumping around
    reasons: list[str] = field(default_factory=list)

    @property
    def locked(self) -> bool:
        return self.health is RackHealth.GREEN

    @property
    def evidence_weight(self) -> float:
        """Multiplier for zone-derived evidence.

        YELLOW does not disqualify zone reasoning, it discounts it -- a held
        homography is usually still approximately right, and refusing to use it
        would make the system brittle for the sake of purity.
        """
        return {RackHealth.GREEN: 1.0, RackHealth.YELLOW: 0.65, RackHealth.RED: 0.0}[self.health]

    def summary(self) -> str:
        if self.health is RackHealth.GREEN:
            return f"rack locked ({self.mode.value}, {self.visible_markers} markers)"
        return f"rack {self.health.value}: {'; '.join(self.reasons) or self.mode.value}"

    def to_dict(self) -> dict:
        return {
            "mode": self.mode.value,
            "health": self.health.value,
            "confidence": round(self.confidence, 3),
            "homography_age_s": round(self.homography_age_s, 3),
            "visible_markers": self.visible_markers,
            "roll_deg": round(self.roll_deg, 1),
            "stability": round(self.stability, 3),
            "reasons": list(self.reasons),
        }


class RackHealthManager:
    """Turns a :class:`RackFrame` into an explicit, reportable health state."""

    def __init__(
        self,
        *,
        hold_yellow_s: float = 0.35,     # held longer than this -> YELLOW
        hold_red_s: float = 2.5,         # held longer than this -> RED
        min_confidence: float = 0.35,
        history: int = 20,
    ) -> None:
        self.hold_yellow_s = hold_yellow_s
        self.hold_red_s = hold_red_s
        self.min_confidence = min_confidence
        self._last_live = 0.0
        self._corners: deque = deque(maxlen=history)
        self._status = RackStatus()
        self._transitions: list[tuple[float, RackHealth, RackHealth]] = []

    @property
    def status(self) -> RackStatus:
        return self._status

    def _stability(self, corners) -> float:
        """How much the rack quad is moving between frames.

        A rack that jitters by tens of pixels frame to frame indicates marker
        mis-detection rather than genuine motion, and the resulting zone
        boundaries are unreliable even though every individual frame "worked".
        """
        if corners is None:
            return 1.0
        self._corners.append(np.asarray(corners, dtype=np.float32).reshape(-1, 2))
        if len(self._corners) < 4:
            return 1.0
        arr = np.stack(list(self._corners)[-8:], axis=0)
        jitter = float(arr.std(axis=0).mean())
        return float(np.clip(1.0 - jitter / 14.0, 0.0, 1.0))

    def update(self, rack) -> RackStatus:
        """Evaluate one frame's rack solution."""
        now = time.monotonic()
        reasons: list[str] = []

        if rack is None:
            status = RackStatus(RackMode.UNKNOWN, RackHealth.RED, 0.0,
                                reasons=["no rack solution produced"])
            self._commit(status)
            return status

        try:
            mode = RackMode(getattr(rack, "source", "unknown"))
        except ValueError:
            mode = RackMode.UNKNOWN

        confidence = float(getattr(rack, "confidence", 0.0))
        corners = getattr(rack, "corners_px", None)
        stability = self._stability(corners)
        markers = 4 if mode is RackMode.ARUCO and confidence >= 0.9 else (
            1 if mode is RackMode.ARUCO else 0
        )

        if mode is RackMode.ARUCO:
            self._last_live = now
        age = now - self._last_live if self._last_live else float("inf")

        # ---- classify -------------------------------------------------
        if mode is RackMode.IDENTITY or mode is RackMode.UNKNOWN:
            health = RackHealth.RED
            reasons.append("no rack frame - zone evidence cannot be trusted")
        elif mode is RackMode.ARUCO:
            if confidence < self.min_confidence:
                health = RackHealth.YELLOW
                reasons.append(f"marker confidence {confidence:.2f}")
            elif stability < 0.45:
                health = RackHealth.YELLOW
                reasons.append(f"rack quad unstable (jitter {1 - stability:.2f})")
            elif markers < 4:
                health = RackHealth.YELLOW
                reasons.append("single-marker solution; span is assumed")
            else:
                health = RackHealth.GREEN
        elif mode is RackMode.HELD:
            if age > self.hold_red_s:
                health = RackHealth.RED
                reasons.append(f"homography held for {age:.1f}s - stale")
            elif age > self.hold_yellow_s:
                health = RackHealth.YELLOW
                reasons.append(f"fiducials occluded, holding for {age:.1f}s")
            else:
                health = RackHealth.GREEN
        elif mode is RackMode.STATIC:
            health = RackHealth.YELLOW
            reasons.append("static calibration in use - valid only if the camera has not moved")
        else:  # pragma: no cover
            health = RackHealth.RED
            reasons.append(f"unrecognised rack mode {mode}")

        status = RackStatus(
            mode=mode, health=health, confidence=confidence,
            homography_age_s=0.0 if mode is RackMode.ARUCO else min(age, 999.0),
            visible_markers=markers, roll_deg=float(getattr(rack, "roll_deg", 0.0)),
            stability=stability, reasons=reasons,
        )
        self._commit(status)
        return status

    def _commit(self, status: RackStatus) -> None:
        if status.health is not self._status.health:
            self._transitions.append((time.time(), self._status.health, status.health))
            if len(self._transitions) > 200:
                self._transitions = self._transitions[-200:]
        self._status = status

    def transitions(self) -> list[dict]:
        return [
            {"wall": w, "from": a.value, "to": b.value}
            for w, a, b in self._transitions
        ]

    def veto(self) -> list[str]:
        """Veto strings for the evidence fuser when the rack is unusable."""
        if self._status.health is RackHealth.RED:
            return [self._status.summary()]
        return []

    def reset(self) -> None:
        self._last_live = 0.0
        self._corners.clear()
        self._status = RackStatus()
        self._transitions.clear()
