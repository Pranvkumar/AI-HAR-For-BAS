"""CPU-only MediaPipe Holistic hand tracking adapter."""

from dataclasses import dataclass
import importlib
from typing import Any


@dataclass(frozen=True)
class Landmark:
    x: float
    y: float
    z: float = 0.0
    visibility: float = 1.0


@dataclass(frozen=True)
class HandState:
    hands: dict[str, tuple[Landmark, ...]]
    image_size: tuple[int, int]
    timestamp: float = 0.0


class HandTracker:
    """MediaPipe Holistic configured for CPU inference only."""

    def __init__(
        self,
        *,
        min_detection_confidence: float = 0.5,
        min_tracking_confidence: float = 0.5,
    ) -> None:
        try:
            mp = importlib.import_module("mediapipe")
        except ImportError as error:
            raise RuntimeError(
                "mediapipe is required to construct HandTracker"
            ) from error
        self._holistic = mp.solutions.holistic.Holistic(
            min_detection_confidence=min_detection_confidence,
            min_tracking_confidence=min_tracking_confidence,
        )

    def track(self, frame: Any, timestamp: float = 0.0) -> HandState:
        height, width = frame.shape[:2]
        result = self._holistic.process(frame)
        hands: dict[str, tuple[Landmark, ...]] = {}
        for name, points in (
            ("left", result.left_hand_landmarks),
            ("right", result.right_hand_landmarks),
        ):
            if points:
                hands[name] = tuple(
                    Landmark(p.x, p.y, p.z, getattr(p, "visibility", 1.0))
                    for p in points.landmark
                )
        return HandState(hands, (width, height), timestamp)
