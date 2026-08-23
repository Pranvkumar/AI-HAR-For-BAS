"""CPU-only MediaPipe Holistic wrapper for per-hand landmarks."""

from __future__ import annotations

import os
import time
from typing import Any

from har.events import HandLandmark, HandState


class HandTracker:
    """Extract normalized hand landmarks using MediaPipe's CPU implementation."""

    def __init__(self) -> None:
        os.environ.setdefault("MEDIAPIPE_DISABLE_GPU", "1")
        try:
            import mediapipe as mp
        except ImportError as error:
            raise RuntimeError("Install MediaPipe before creating HandTracker.") from error
        self._cv2 = __import__("cv2")
        self._holistic = mp.solutions.holistic.Holistic(
            static_image_mode=False,
            model_complexity=1,
            smooth_landmarks=True,
            refine_face_landmarks=False,
        )

    @staticmethod
    def _convert(landmarks: Any) -> tuple[HandLandmark, ...]:
        if landmarks is None:
            return ()
        return tuple(HandLandmark(point.x, point.y, point.z) for point in landmarks.landmark)

    def track(self, frame: Any) -> HandState:
        """Return landmarks for the frame; no GPU delegate is used."""

        rgb = self._cv2.cvtColor(frame, self._cv2.COLOR_BGR2RGB)
        result = self._holistic.process(rgb)
        return HandState(
            timestamp_s=time.monotonic(),
            hands={
                "left": self._convert(result.left_hand_landmarks),
                "right": self._convert(result.right_hand_landmarks),
            },
        )

    def close(self) -> None:
        """Release MediaPipe CPU resources."""

        self._holistic.close()
