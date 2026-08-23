"""Relational hand-object interaction inference with change-only events."""

from __future__ import annotations

import math
from dataclasses import dataclass

from har.events import Detection, HandState, InteractionEvent
from har.vision.gesture_recognizer import RecognizedGesture


@dataclass(frozen=True)
class InteractionConfig:
    """Tunable relational interaction thresholds."""

    grasp_distance: float = 0.08
    min_overlap: float = 0.01
    timestamp_tolerance_s: float = 0.08
    gesture_grasp_confidence: float = 0.75


class InteractionEngine:
    """Infer grasp/contact only from same-frame hand-object relationships."""

    def __init__(self, config: InteractionConfig | None = None) -> None:
        self.config = config or InteractionConfig()
        self._previous: dict[tuple[str, str, int | None], tuple[bool, str]] = {}

    @staticmethod
    def _hand_box(hand: tuple, width: int, height: int) -> tuple[float, float, float, float]:
        xs = [point.x * width for point in hand]
        ys = [point.y * height for point in hand]
        return min(xs), min(ys), max(xs), max(ys)

    @staticmethod
    def _iou(a: tuple[float, float, float, float], b: tuple[float, float, float, float]) -> float:
        left, top, right, bottom = max(a[0], b[0]), max(a[1], b[1]), min(a[2], b[2]), min(a[3], b[3])
        intersection = max(0.0, right - left) * max(0.0, bottom - top)
        area_a = max(0.0, a[2] - a[0]) * max(0.0, a[3] - a[1])
        area_b = max(0.0, b[2] - b[0]) * max(0.0, b[3] - b[1])
        union = area_a + area_b - intersection
        return intersection / union if union else 0.0

    def process(
        self,
        hands: HandState,
        detections: list[Detection],
        frame_size: tuple[int, int],
        gestures: list[RecognizedGesture] | None = None,
    ) -> list[InteractionEvent]:
        """Emit events only when a hand-object interaction state changes."""

        width, height = frame_size
        events: list[InteractionEvent] = []
        gesture_by_hand = {item.handedness.lower(): item for item in gestures or []}
        for hand_name, landmarks in hands.hands.items():
            if len(landmarks) <= 8:
                continue
            hand_box = self._hand_box(landmarks, width, height)
            grasp_distance = math.hypot(landmarks[4].x - landmarks[8].x, landmarks[4].y - landmarks[8].y)
            landmark_grasped = grasp_distance <= self.config.grasp_distance
            gesture = gesture_by_hand.get(hand_name)
            gesture_grasped = bool(
                gesture
                and gesture.name == "Closed_Fist"
                and gesture.confidence >= self.config.gesture_grasp_confidence
            )
            grasped = landmark_grasped or gesture_grasped
            for detection in detections:
                overlap = self._iou(hand_box, detection.xyxy)
                interaction = "grasp" if grasped and overlap >= self.config.min_overlap else "contact" if overlap >= self.config.min_overlap else "none"
                key = (hand_name, detection.cls, detection.track_id)
                state = (grasped, interaction)
                if self._previous.get(key) == state:
                    continue
                self._previous[key] = state
                events.append(InteractionEvent(hands.timestamp_s, hand_name, detection.cls, detection.track_id, interaction, grasped, overlap))
        return events
