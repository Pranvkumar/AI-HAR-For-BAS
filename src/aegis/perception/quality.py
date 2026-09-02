"""Frame-quality and camera-health monitoring.

Running inference on a dark, blurred or occluded frame and reporting a confident
answer is worse than reporting nothing. This module inspects every frame before
the perception stack sees it and publishes a health verdict the rest of the
system can act on.

Four cheap, well-understood measures:

* **Brightness** -- mean luma. Catches a dark room or a dead sensor.
* **Contrast** -- luma standard deviation. Catches a lens cap or a white-out.
* **Sharpness** -- variance of the Laplacian, the standard no-reference blur
  metric. Catches motion blur and defocus.
* **Occlusion** -- fraction of the frame that is both very dark and very flat,
  which is what a hand or a sleeve over the lens actually looks like.

Plus two temporal measures the frame itself cannot show: capture FPS and the
staleness of the last good frame.

The verdict is deliberately a small enum rather than a score, because the
consumers are a state machine and a human, and neither benefits from a float.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from enum import Enum
import time

import numpy as np

try:  # pragma: no cover
    import cv2
except Exception:  # pragma: no cover
    cv2 = None  # type: ignore


class HealthState(str, Enum):
    """Traffic-light verdict on whether the video is usable."""

    NOMINAL = "nominal"        # analyse normally
    DEGRADED = "degraded"      # analyse, but flag reduced confidence
    UNUSABLE = "unusable"      # suspend validation; do not guess


@dataclass
class FrameQuality:
    brightness: float = 0.0        # 0-1, mean luma
    contrast: float = 0.0          # 0-1, luma std
    sharpness: float = 0.0         # variance of Laplacian, unnormalised
    occlusion: float = 0.0         # 0-1, fraction dark+flat
    fps: float = 0.0
    staleness_s: float = 0.0
    state: HealthState = HealthState.NOMINAL
    reasons: list[str] = field(default_factory=list)

    @property
    def usable(self) -> bool:
        return self.state is not HealthState.UNUSABLE

    @property
    def confidence_scale(self) -> float:
        """Multiplier applied to recognition confidence.

        Degraded video should not produce full-confidence assertions. This is
        the single number the evidence fusion layer uses to discount everything
        downstream of a poor frame.
        """
        return {
            HealthState.NOMINAL: 1.0,
            HealthState.DEGRADED: 0.75,
            HealthState.UNUSABLE: 0.0,
        }[self.state]

    def summary(self) -> str:
        if self.state is HealthState.NOMINAL:
            return "camera nominal"
        return f"camera {self.state.value}: {'; '.join(self.reasons) or 'unspecified'}"

    def to_dict(self) -> dict:
        return {
            "state": self.state.value,
            "brightness": round(self.brightness, 3),
            "contrast": round(self.contrast, 3),
            "sharpness": round(self.sharpness, 1),
            "occlusion": round(self.occlusion, 3),
            "fps": round(self.fps, 1),
            "staleness_s": round(self.staleness_s, 2),
            "reasons": list(self.reasons),
        }


@dataclass
class QualityThresholds:
    """Tunable limits. Defaults suit an indoor webcam at 720p."""

    brightness_low: float = 0.12
    brightness_high: float = 0.94
    contrast_low: float = 0.045
    sharpness_low: float = 22.0        # var(Laplacian) below this is soft
    sharpness_critical: float = 7.0
    sharpness_drop_ratio: float = 0.22     # fraction of baseline that means blur
    sharpness_drop_critical: float = 0.08
    occlusion_high: float = 0.45
    occlusion_critical: float = 0.72
    fps_low: float = 8.0
    fps_critical: float = 3.0
    stale_critical_s: float = 2.0


class FrameQualityMonitor:
    """Scores frames and smooths the verdict over a short window.

    Smoothing matters: a single dark frame while someone walks past the light
    should not suspend the whole session. The state only changes when the
    condition persists, which is the same debounce philosophy used for action
    recognition.
    """

    def __init__(
        self,
        thresholds: QualityThresholds | None = None,
        *,
        history: int = 12,
        sample_width: int = 320,
    ) -> None:
        self.t = thresholds or QualityThresholds()
        self.sample_width = sample_width
        self._hist: deque = deque(maxlen=history)
        self._frame_times: deque = deque(maxlen=30)
        # Absolute Laplacian-variance thresholds are content-dependent: a frame
        # of fine texture scores orders of magnitude higher than a smooth one,
        # so a fixed cut-off either misses blur on busy scenes or false-alarms
        # on plain ones. We therefore also watch for a *relative collapse*
        # against a rolling baseline, which is what vibration onset looks like.
        self._sharp_hist: deque = deque(maxlen=90)
        self._last_good = time.monotonic()
        self._state = HealthState.NOMINAL

    # ---------------------------------------------------------------- measure

    def _downsample(self, frame_bgr: np.ndarray) -> np.ndarray:
        h, w = frame_bgr.shape[:2]
        if cv2 is None:
            return frame_bgr
        if w > self.sample_width:
            scale = self.sample_width / w
            return cv2.resize(frame_bgr, (self.sample_width, max(1, int(h * scale))))
        return frame_bgr

    def measure(self, frame_bgr: np.ndarray) -> tuple[float, float, float, float]:
        """Return (brightness, contrast, sharpness, occlusion) for one frame."""
        small = self._downsample(frame_bgr)
        if cv2 is not None:
            gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
        else:  # pragma: no cover
            gray = small.mean(axis=2).astype(np.uint8)

        g = gray.astype(np.float32) / 255.0
        brightness = float(g.mean())
        contrast = float(g.std())

        if cv2 is not None:
            sharpness = float(cv2.Laplacian(gray, cv2.CV_64F).var())
        else:  # pragma: no cover
            dx = np.diff(g, axis=1)
            dy = np.diff(g, axis=0)
            sharpness = float((dx.var() + dy.var()) * 5000.0)

        # A hand over the lens is dark AND textureless. Either alone is normal.
        dark = g < 0.18
        if cv2 is not None:
            local_std = cv2.blur((g - cv2.blur(g, (9, 9))) ** 2, (9, 9))
            flat = local_std < 1.2e-3
        else:  # pragma: no cover
            flat = np.ones_like(dark)
        occlusion = float(np.logical_and(dark, flat).mean())

        return brightness, contrast, sharpness, occlusion

    # ----------------------------------------------------------------- verdict

    def _baseline_sharpness(self) -> float | None:
        """Median of recent sharpness, ignoring the current frame."""
        vals = [v for v in self._sharp_hist if v is not None]
        if len(vals) < 12:
            return None
        return float(np.median(vals))

    def _classify(self, b: float, c: float, s: float, o: float, fps: float, stale: float):
        reasons: list[str] = []
        state = HealthState.NOMINAL

        def escalate(new: HealthState) -> HealthState:
            order = [HealthState.NOMINAL, HealthState.DEGRADED, HealthState.UNUSABLE]
            return new if order.index(new) > order.index(state) else state

        if o >= self.t.occlusion_critical:
            reasons.append(f"lens occluded ({o:.0%})")
            state = escalate(HealthState.UNUSABLE)
        elif o >= self.t.occlusion_high:
            reasons.append(f"partial occlusion ({o:.0%})")
            state = escalate(HealthState.DEGRADED)

        if b <= self.t.brightness_low:
            reasons.append(f"insufficient illumination ({b:.2f})")
            state = escalate(HealthState.DEGRADED if b > self.t.brightness_low * 0.5 else HealthState.UNUSABLE)
        elif b >= self.t.brightness_high:
            reasons.append(f"over-exposed ({b:.2f})")
            state = escalate(HealthState.DEGRADED)

        if c <= self.t.contrast_low:
            reasons.append(f"very low contrast ({c:.3f})")
            state = escalate(HealthState.DEGRADED)

        baseline = self._baseline_sharpness()
        if s <= self.t.sharpness_critical:
            reasons.append(f"severe blur (var {s:.0f})")
            state = escalate(HealthState.UNUSABLE)
        elif s <= self.t.sharpness_low:
            reasons.append(f"soft focus or motion blur (var {s:.0f})")
            state = escalate(HealthState.DEGRADED)
        elif baseline and s <= baseline * self.t.sharpness_drop_critical:
            reasons.append(f"severe motion blur ({s / baseline:.0%} of baseline sharpness)")
            state = escalate(HealthState.UNUSABLE)
        elif baseline and s <= baseline * self.t.sharpness_drop_ratio:
            reasons.append(f"motion blur ({s / baseline:.0%} of baseline sharpness)")
            state = escalate(HealthState.DEGRADED)

        if fps and fps <= self.t.fps_critical:
            reasons.append(f"frame rate collapsed ({fps:.1f} fps)")
            state = escalate(HealthState.UNUSABLE)
        elif fps and fps <= self.t.fps_low:
            reasons.append(f"low frame rate ({fps:.1f} fps)")
            state = escalate(HealthState.DEGRADED)

        if stale >= self.t.stale_critical_s:
            reasons.append(f"no fresh frame for {stale:.1f}s")
            state = escalate(HealthState.UNUSABLE)

        return state, reasons

    def update(self, frame_bgr: np.ndarray | None) -> FrameQuality:
        """Score a frame. Pass None when no frame arrived this tick."""
        now = time.monotonic()

        if frame_bgr is None:
            stale = now - self._last_good
            q = FrameQuality(fps=self._fps(), staleness_s=stale)
            q.state, q.reasons = self._classify(0.5, 0.2, 100.0, 0.0, q.fps, stale)
            self._state = self._smooth(q.state)
            q.state = self._state
            return q

        self._frame_times.append(now)
        self._last_good = now

        b, c, s, o = self.measure(frame_bgr)
        fps = self._fps()
        raw_state, reasons = self._classify(b, c, s, o, fps, 0.0)
        self._sharp_hist.append(s)
        self._state = self._smooth(raw_state)

        return FrameQuality(
            brightness=b, contrast=c, sharpness=s, occlusion=o,
            fps=fps, staleness_s=0.0, state=self._state, reasons=reasons,
        )

    def _smooth(self, raw: HealthState) -> HealthState:
        """Require a condition to persist before changing state.

        Entering a worse state needs a majority of the window; returning to
        NOMINAL needs the whole window clean. Asymmetric on purpose -- we are
        quick to doubt and slow to trust.
        """
        self._hist.append(raw)
        if len(self._hist) < 3:
            return raw
        window = list(self._hist)
        unusable = window.count(HealthState.UNUSABLE)
        degraded = window.count(HealthState.DEGRADED)
        n = len(window)

        if unusable >= max(2, n // 3):
            return HealthState.UNUSABLE
        if unusable + degraded >= max(2, n // 2):
            return HealthState.DEGRADED
        if all(x is HealthState.NOMINAL for x in window):
            return HealthState.NOMINAL
        return self._state if self._state is not HealthState.UNUSABLE else HealthState.DEGRADED

    def _fps(self) -> float:
        if len(self._frame_times) < 2:
            return 0.0
        span = self._frame_times[-1] - self._frame_times[0]
        return (len(self._frame_times) - 1) / span if span > 1e-6 else 0.0

    def reset(self) -> None:
        self._hist.clear()
        self._frame_times.clear()
        self._sharp_hist.clear()
        self._last_good = time.monotonic()
        self._state = HealthState.NOMINAL
