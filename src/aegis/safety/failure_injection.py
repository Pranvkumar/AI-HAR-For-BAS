"""Controlled failure injection.

Demonstrating the happy path proves very little. Any system looks competent when
the lights are on, the markers are visible and the operator behaves. What a
reviewer actually wants to know is what happens when they do not.

This module lets an operator inject specific faults on demand, from the GUI or
the keyboard, so that graceful degradation can be *shown* rather than claimed:

    press 1 -> lens occluded          -> validation suspends, GUI says why
    press 2 -> lights dim             -> DEGRADED, confidence discounted
    press 3 -> markers hidden         -> rack falls back, mode displayed
    press 4 -> camera unplugged       -> pipeline holds, reports, recovers
    press 5 -> action model disabled  -> Tier 1 drops to Tier 0, tier shown

Faults are applied as *transforms on the pipeline's inputs*, never by mutating
the components themselves. That matters: it means the code path exercised under
injection is exactly the production path, so a passing injection test is
evidence about the real system rather than about a mock.

Every injection is written to the session log, so a recording of the demo is
self-documenting -- a reviewer watching later can see that the degradation was
deliberate and when it started.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import time

import numpy as np

try:  # pragma: no cover
    import cv2
except Exception:  # pragma: no cover
    cv2 = None  # type: ignore


class FaultType(str, Enum):
    """The faults a reviewer is most likely to ask about."""

    NONE = "none"
    OCCLUDE_LENS = "occlude_lens"           # hand or debris over the camera
    DIM_LIGHTING = "dim_lighting"           # module lighting fails
    MOTION_BLUR = "motion_blur"             # vibration or fast pan
    HIDE_MARKERS = "hide_markers"           # arm across the rack fiducials
    ROTATE_CAMERA = "rotate_camera"         # microgravity reorientation
    FREEZE_CAMERA = "freeze_camera"         # frozen feed, still "connected"
    DROP_CAMERA = "drop_camera"             # disconnection
    DISABLE_MODEL = "disable_model"         # Tier 1 unavailable
    DISABLE_VOICE = "disable_voice"         # audio subsystem failure
    SLOW_PIPELINE = "slow_pipeline"         # CPU contention

    @property
    def label(self) -> str:
        return {
            FaultType.NONE: "No fault",
            FaultType.OCCLUDE_LENS: "Lens occluded",
            FaultType.DIM_LIGHTING: "Lighting failure",
            FaultType.MOTION_BLUR: "Vibration / motion blur",
            FaultType.HIDE_MARKERS: "Rack fiducials hidden",
            FaultType.ROTATE_CAMERA: "Camera reoriented",
            FaultType.FREEZE_CAMERA: "Video feed frozen",
            FaultType.DROP_CAMERA: "Camera disconnected",
            FaultType.DISABLE_MODEL: "Action model unavailable",
            FaultType.DISABLE_VOICE: "Voice subsystem down",
            FaultType.SLOW_PIPELINE: "CPU contention",
        }[self]

    @property
    def expected_response(self) -> str:
        """What the system is supposed to do. Shown in the GUI beside the fault
        so a reviewer can check the claim against the behaviour in real time."""
        return {
            FaultType.NONE: "nominal operation",
            FaultType.OCCLUDE_LENS: "camera UNUSABLE, validation suspended, no guessing",
            FaultType.DIM_LIGHTING: "camera DEGRADED, confidence discounted, session continues",
            FaultType.MOTION_BLUR: "camera DEGRADED, evidence weight reduced",
            FaultType.HIDE_MARKERS: "rack falls back: aruco -> held -> static quad, mode displayed",
            FaultType.ROTATE_CAMERA: "rack-relative features unchanged, recognition continues",
            FaultType.FREEZE_CAMERA: "staleness detected, camera UNUSABLE",
            FaultType.DROP_CAMERA: "pipeline holds, reports fault, reconnects automatically",
            FaultType.DISABLE_MODEL: "Tier 1 -> Tier 0, active tier displayed",
            FaultType.DISABLE_VOICE: "visual alerts continue, voice lamp goes dark",
            FaultType.SLOW_PIPELINE: "frames dropped not queued, latency reported",
        }[self]


@dataclass
class FaultRecord:
    fault: FaultType
    started: float
    stopped: float | None = None
    intensity: float = 1.0

    @property
    def active(self) -> bool:
        return self.stopped is None

    @property
    def duration_s(self) -> float:
        return (self.stopped or time.monotonic()) - self.started


class FailureInjector:
    """Applies faults to frames and exposes flags the pipeline consults.

    Frame-level faults are implemented as image transforms; subsystem faults are
    boolean flags the pipeline reads. Multiple faults can be active at once,
    which is how you demonstrate that degradation composes rather than
    collapsing into an unhandled state.
    """

    def __init__(self) -> None:
        self._active: dict[FaultType, FaultRecord] = {}
        self.history: list[FaultRecord] = []
        self._frozen_frame: np.ndarray | None = None
        self._listeners: list = []

    # ------------------------------------------------------------------ state

    def on_change(self, callback) -> None:
        """Register a callback fired on every inject/clear, for logging."""
        self._listeners.append(callback)

    def _notify(self, fault: FaultType, active: bool) -> None:
        for cb in list(self._listeners):
            try:
                cb(fault, active)
            except Exception:
                pass

    @property
    def any_active(self) -> bool:
        return bool(self._active)

    def is_active(self, fault: FaultType) -> bool:
        return fault in self._active

    def active_faults(self) -> list[FaultType]:
        return list(self._active)

    def describe(self) -> str:
        if not self._active:
            return ""
        return "INJECTED: " + ", ".join(f.label for f in self._active)

    # --------------------------------------------------------------- control

    def inject(self, fault: FaultType, intensity: float = 1.0) -> FaultRecord | None:
        if fault is FaultType.NONE:
            self.clear_all()
            return None
        if fault in self._active:
            return self._active[fault]
        record = FaultRecord(fault, time.monotonic(), intensity=float(np.clip(intensity, 0.0, 1.0)))
        self._active[fault] = record
        self.history.append(record)
        if fault is FaultType.FREEZE_CAMERA:
            self._frozen_frame = None       # captured on the next frame
        self._notify(fault, True)
        return record

    def clear(self, fault: FaultType) -> None:
        record = self._active.pop(fault, None)
        if record is not None:
            record.stopped = time.monotonic()
            if fault is FaultType.FREEZE_CAMERA:
                self._frozen_frame = None
            self._notify(fault, False)

    def toggle(self, fault: FaultType) -> bool:
        if self.is_active(fault):
            self.clear(fault)
            return False
        self.inject(fault)
        return True

    def clear_all(self) -> None:
        for fault in list(self._active):
            self.clear(fault)

    # ----------------------------------------------------------- frame faults

    def apply(self, frame: np.ndarray | None) -> np.ndarray | None:
        """Transform a frame according to the active faults.

        Returns None when the camera is simulated as disconnected, which is
        exactly what :class:`VideoSource` returns on a real failure -- so the
        pipeline cannot tell the difference, which is the point.
        """
        if frame is None or not self._active:
            return frame

        if FaultType.DROP_CAMERA in self._active:
            return None

        if FaultType.FREEZE_CAMERA in self._active:
            if self._frozen_frame is None:
                self._frozen_frame = frame.copy()
            return self._frozen_frame.copy()

        out = frame

        if FaultType.ROTATE_CAMERA in self._active and cv2 is not None:
            record = self._active[FaultType.ROTATE_CAMERA]
            angle = 180.0 * record.intensity
            h, w = out.shape[:2]
            m = cv2.getRotationMatrix2D((w / 2, h / 2), angle, 1.0)
            out = cv2.warpAffine(out, m, (w, h), borderValue=(18, 18, 18))

        if FaultType.DIM_LIGHTING in self._active:
            record = self._active[FaultType.DIM_LIGHTING]
            factor = 1.0 - 0.88 * record.intensity
            out = np.clip(out.astype(np.float32) * factor, 0, 255).astype(np.uint8)

        if FaultType.MOTION_BLUR in self._active and cv2 is not None:
            record = self._active[FaultType.MOTION_BLUR]
            k = int(3 + 28 * record.intensity) | 1
            kernel = np.zeros((k, k), np.float32)
            kernel[k // 2, :] = 1.0 / k          # horizontal smear
            out = cv2.filter2D(out, -1, kernel)

        if FaultType.HIDE_MARKERS in self._active:
            out = self._mask_borders(out)

        if FaultType.OCCLUDE_LENS in self._active:
            record = self._active[FaultType.OCCLUDE_LENS]
            out = self._occlude(out, record.intensity)

        return out

    @staticmethod
    def _mask_borders(frame: np.ndarray, band: float = 0.16) -> np.ndarray:
        """Blank the frame margins where rack fiducials are normally taped."""
        out = frame.copy()
        h, w = out.shape[:2]
        bh, bw = int(h * band), int(w * band)
        colour = (26, 26, 30)
        out[:bh, :] = colour
        out[-bh:, :] = colour
        out[:, :bw] = colour
        out[:, -bw:] = colour
        return out

    @staticmethod
    def _occlude(frame: np.ndarray, intensity: float) -> np.ndarray:
        """Cover a fraction of the frame with a dark, textureless region.

        Dark *and* flat, because that is what a hand over a lens actually looks
        like to the quality monitor -- and the monitor tests for exactly that
        conjunction rather than darkness alone.
        """
        out = frame.copy()
        h, w = out.shape[:2]
        covered = float(np.clip(0.35 + 0.6 * intensity, 0.0, 0.98))
        rows = int(h * covered)
        out[:rows, :] = 8
        return out

    # ------------------------------------------------------- subsystem faults

    @property
    def model_disabled(self) -> bool:
        return FaultType.DISABLE_MODEL in self._active

    @property
    def voice_disabled(self) -> bool:
        return FaultType.DISABLE_VOICE in self._active

    @property
    def markers_hidden(self) -> bool:
        return FaultType.HIDE_MARKERS in self._active

    @property
    def extra_latency_s(self) -> float:
        record = self._active.get(FaultType.SLOW_PIPELINE)
        return 0.12 * record.intensity if record else 0.0

    # ------------------------------------------------------------- reporting

    def report(self) -> list[dict]:
        return [
            {
                "fault": r.fault.value,
                "label": r.fault.label,
                "expected": r.fault.expected_response,
                "duration_s": round(r.duration_s, 2),
                "active": r.active,
                "intensity": r.intensity,
            }
            for r in self.history
        ]

    def reset(self) -> None:
        self.clear_all()
        self.history.clear()
        self._frozen_frame = None


DEMO_SEQUENCE: list[tuple[FaultType, float]] = [
    (FaultType.DIM_LIGHTING, 6.0),
    (FaultType.HIDE_MARKERS, 6.0),
    (FaultType.ROTATE_CAMERA, 8.0),
    (FaultType.OCCLUDE_LENS, 5.0),
    (FaultType.DROP_CAMERA, 4.0),
    (FaultType.DISABLE_MODEL, 6.0),
]
"""A scripted robustness demo, in the order that tells the best story:
degrade gently, then harder, then remove the input entirely, then remove the
model. Each step should visibly change the GUI without stopping the session."""
