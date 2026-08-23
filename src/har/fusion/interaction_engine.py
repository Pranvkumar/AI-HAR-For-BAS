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
        synthesize_relations: bool = True,
    ) -> None:
        self.grasp_distance = grasp_distance
        self.min_iou = min_iou
        self.visibility = visibility
        self.synthesize_relations = synthesize_relations
        self._last: dict[tuple[str, int | str | None], str] = {}

    @staticmethod
    def _center(box: tuple[float, float, float, float]) -> tuple[float, float]:
        return ((box[0] + box[2]) / 2.0, (box[1] + box[3]) / 2.0)

    @staticmethod
    def _size(box: tuple[float, float, float, float]) -> tuple[float, float]:
        return (max(1.0, box[2] - box[0]), max(1.0, box[3] - box[1]))

    @staticmethod
    def _union_box(
        boxes: Iterable[tuple[float, float, float, float]]
    ) -> tuple[float, float, float, float]:
        values = list(boxes)
        return (
            min(box[0] for box in values),
            min(box[1] for box in values),
            max(box[2] for box in values),
            max(box[3] for box in values),
        )

    def _derive_relations(self, detections: list[Detection]) -> list[Detection]:
        """Create virtual detections that represent protocol-level spatial relations."""
        derived: list[Detection] = []
        red = [item for item in detections if str(item.cls) == "red_box"]
        blue = [item for item in detections if str(item.cls) == "blue_box"]

        if len(red) >= 2:
            ordered_red = sorted(red, key=lambda item: self._center(item.xyxy)[0])[:2]
            left, right = ordered_red
            (lx, ly), (rx, ry) = self._center(left.xyxy), self._center(right.xyxy)
            lw, lh = self._size(left.xyxy)
            rw, rh = self._size(right.xyxy)
            y_gap = abs(ly - ry)
            x_gap = abs(lx - rx)
            avg_w = (lw + rw) / 2.0
            avg_h = (lh + rh) / 2.0
            if y_gap <= avg_h * 0.6 and x_gap <= avg_w * 3.5:
                derived.append(
                    Detection(
                        "red_box_pair",
                        min(left.conf, right.conf),
                        self._union_box([left.xyxy, right.xyxy]),
                        None,
                    )
                )

        if len(red) >= 2 and len(blue) >= 2:
            red_sorted = sorted(red, key=lambda item: self._center(item.xyxy)[0])[:2]
            blue_sorted = sorted(blue, key=lambda item: self._center(item.xyxy)[0])[:2]
            matches = 0
            matched_blue: list[Detection] = []
            for red_box in red_sorted:
                rx, ry = self._center(red_box.xyxy)
                rw, rh = self._size(red_box.xyxy)
                candidate = next(
                    (
                        blue_box
                        for blue_box in blue_sorted
                        if blue_box not in matched_blue
                        and abs(self._center(blue_box.xyxy)[0] - rx) <= rw * 0.6
                        and 0.0 <= ry - self._center(blue_box.xyxy)[1] <= rh * 1.2
                    ),
                    None,
                )
                if candidate is not None:
                    matches += 1
                    matched_blue.append(candidate)
            if matches == 2 and len(matched_blue) == 2:
                derived.append(
                    Detection(
                        "blue_box_stack",
                        min(item.conf for item in matched_blue),
                        self._union_box([item.xyxy for item in matched_blue]),
                        None,
                    )
                )

        return derived

    def update(
        self, hands: HandState, detections: Iterable[Detection]
    ) -> list[InteractionEvent]:
        events: list[InteractionEvent] = []
        normalized = list(detections)
        if self.synthesize_relations:
            normalized.extend(self._derive_relations(normalized))
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
            for detection in normalized:
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
