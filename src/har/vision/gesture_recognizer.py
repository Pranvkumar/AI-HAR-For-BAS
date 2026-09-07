"""Offline MediaPipe Tasks gesture recognizer for detailed hand signals."""

from __future__ import annotations

from dataclasses import dataclass
import logging
from pathlib import Path
from typing import Any

from har.events import HandLandmark, HandState

LOGGER = logging.getLogger(__name__)

@dataclass(frozen=True)
class RecognizedGesture:
    """One gesture classification attached to a detected hand."""

    handedness: str
    name: str
    confidence: float


class HandGestureRecognizer:
    """Recognize two hands locally from a pre-downloaded MediaPipe task model."""

    def __init__(self, model_path: str | Path, num_hands: int = 2) -> None:
        path = Path(model_path)
        try:
            import mediapipe as mp
        except ImportError as error:
            raise RuntimeError("Install mediapipe before using gesture recognition.") from error
        self._mp = mp
        self._recognizer = None
        self._holistic = None
        self._last_timestamp_ms = -1
        if not path.is_file():
            LOGGER.warning("Gesture model not found at %s; hand tracking is disabled", path)
            return
        from mediapipe.tasks import python
        from mediapipe.tasks.python import vision
        options = vision.GestureRecognizerOptions(
            base_options=python.BaseOptions(model_asset_path=str(path)),
            running_mode=vision.RunningMode.VIDEO,
            num_hands=num_hands,
            min_hand_detection_confidence=0.6,
            min_hand_presence_confidence=0.6,
            min_tracking_confidence=0.6,
        )
        self._recognizer = vision.GestureRecognizer.create_from_options(options)

    def track_and_recognize(
        self, frame: Any, timestamp_ms: int
    ) -> tuple[HandState, list[RecognizedGesture]]:
        """Return normalized hand landmarks and recognized gestures from one frame."""

        import cv2

        timestamp_ms = max(timestamp_ms, self._last_timestamp_ms + 1)
        self._last_timestamp_ms = timestamp_ms
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        if self._recognizer is None:
            return HandState(timestamp_ms / 1000.0, {}), []
        image = self._mp.Image(image_format=self._mp.ImageFormat.SRGB, data=rgb)
        result = self._recognizer.recognize_for_video(image, timestamp_ms)
        gestures: list[RecognizedGesture] = []
        hands: dict[str, tuple[HandLandmark, ...]] = {"left": (), "right": ()}
        for hand_index, hand_landmarks in enumerate(result.hand_landmarks):
            hand = result.handedness[hand_index][0].category_name if result.handedness[hand_index] else "Unknown"
            hand_key = hand.lower()
            if hand_key in hands:
                hands[hand_key] = tuple(
                    HandLandmark(point.x, point.y, point.z) for point in hand_landmarks
                )
            categories = result.gestures[hand_index] if hand_index < len(result.gestures) else ()
            if categories:
                category = categories[0]
                gestures.append(RecognizedGesture(hand, category.category_name, float(category.score)))
        return HandState(timestamp_ms / 1000.0, hands), gestures

    def recognize(self, frame: Any, timestamp_ms: int) -> list[RecognizedGesture]:
        """Recognize built-in gestures in a BGR OpenCV frame."""

        _, gestures = self.track_and_recognize(frame, timestamp_ms)
        return gestures

    def close(self) -> None:
        """Release local recognizer resources."""

        if self._recognizer is not None:
            self._recognizer.close()
        if self._holistic is not None:
            self._holistic.close()
