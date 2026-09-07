"""CPU-only current MediaPipe hand-landmark wrapper."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from har.events import HandState
from har.vision.gesture_recognizer import HandGestureRecognizer, RecognizedGesture


class HandTracker:
    """Extract current MediaPipe task hand landmarks on CPU."""

    def __init__(self, model_path: str | Path = "models/gesture_recognizer.task") -> None:
        self._recognizer = HandGestureRecognizer(model_path)

    def track(self, frame: Any) -> HandState:
        """Return landmarks for the frame; no GPU delegate is used."""

        hand_state, _ = self._recognizer.track_and_recognize(frame, int(time.monotonic() * 1000))
        return hand_state

    def track_with_gestures(self, frame: Any, timestamp_ms: int) -> tuple[HandState, list[RecognizedGesture]]:
        """Return hand landmarks plus optional built-in gesture classifications."""

        return self._recognizer.track_and_recognize(frame, timestamp_ms)

    def close(self) -> None:
        """Release MediaPipe CPU resources."""

        self._recognizer.close()
