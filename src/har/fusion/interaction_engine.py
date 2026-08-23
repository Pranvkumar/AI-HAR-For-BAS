"""Orientation-agnostic hand-object contact and grasp event generation."""

from dataclasses import dataclass
from math import hypot
from typing import Iterable

from har.vision.mediapipe_wrapper import HandState
from har.vision.yolo_wrapper import Detection


@dataclass(frozen=True)
class InteractionEvent:
    hand: str
    object: str
    track_id: int | None
    state: str
    timestamp: float
    confidence: float
    iou: float


def _iou(
    left: tuple[float, float, float, float], right: tuple[float, float, float, float]
) -> float:
    x1, y1 = max(left[0], right[0]), max(left[1], right[1])
    x2, y2 = min(left[2], right[2]), min(left[3], right[3])
    intersection = max(0.0, x2 - x1) * max(0.0, y2 - y1)
    area_left = max(0.0, left[2] - left[0]) * max(0.0, left[3] - left[1])
    area_right = max(0.0, right[2] - right[0]) * max(0.0, right[3] - right[1])
    union = area_left + area_right - intersection
    return intersection / union if union else 0.0


class InteractionEngine:
    def __init__(
        self,
        *,
        grasp_distance: float = 0.06,
        min_iou: float = 0.0,
        visibility: float = 0.5,
    ) -> None:
        self.grasp_distance = grasp_distance
        self.min_iou = min_iou
        self.visibility = visibility
        self._last: dict[tuple[str, int | str | None], str] = {}

    def update(
        self, hands: HandState, detections: Iterable[Detection]
    ) -> list[InteractionEvent]:
        events: list[InteractionEvent] = []
        width, height = hands.image_size
        for hand_name, landmarks in hands.hands.items():
            visible = [
                point for point in landmarks if point.visibility >= self.visibility
            ]
            if len(visible) < 2:
                continue
            region = (
                min(p.x for p in visible) * width,
                min(p.y for p in visible) * height,
                max(p.x for p in visible) * width,
                max(p.y for p in visible) * height,
            )
            pinch = (
                hypot(landmarks[4].x - landmarks[8].x, landmarks[4].y - landmarks[8].y)
                <= self.grasp_distance
            )
            for detection in detections:
                overlap = _iou(region, detection.xyxy)
                state = (
                    "grasp_start"
                    if overlap > self.min_iou and pinch
                    else "contact" if overlap > self.min_iou else "open"
                )
                key = (
                    hand_name,
                    (
                        detection.track_id
                        if detection.track_id is not None
                        else detection.cls
                    ),
                )
                previous = self._last.get(key)
                self._last[key] = state
                if previous != state:
                    events.append(
                        InteractionEvent(
                            hand_name,
                            str(detection.cls),
                            detection.track_id,
                            state,
                            hands.timestamp,
                            detection.conf,
                            overlap,
                        )
                    )
        return events
