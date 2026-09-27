"""
Mock hand-object tracker for DEMO_MODE.
Simulates tracking hands relative to experiment containers and tools.
"""
import random
from typing import Any, Dict, List

import numpy as np

from .base import BaseTracker
from .object_detector import OBJECT_CLASSES

# Classes a hand can meaningfully interact with, in priority order
INTERACTION_TARGETS = ("container", "tool", "sample_bag")

HAND_CLASS_ID = OBJECT_CLASSES.index("hand")


def compute_iou(box_a: List[float], box_b: List[float]) -> float:
    """Intersection-over-union for two [x1, y1, x2, y2] boxes."""
    ax1, ay1, ax2, ay2 = box_a
    bx1, by1, bx2, by2 = box_b

    inter_w = max(0.0, min(ax2, bx2) - max(ax1, bx1))
    inter_h = max(0.0, min(ay2, by2) - max(ay1, by1))
    intersection = inter_w * inter_h

    area_a = max(0.0, ax2 - ax1) * max(0.0, ay2 - ay1)
    area_b = max(0.0, bx2 - bx1) * max(0.0, by2 - by1)
    union = area_a + area_b - intersection

    return intersection / union if union > 0 else 0.0


def classify_interaction(hand_bbox: List[float], obj_bbox: List[float]) -> Dict[str, Any]:
    """IoU-based heuristic describing how a hand relates to an object."""
    iou = compute_iou(hand_bbox, obj_bbox)

    if iou > 0.25:
        return {"interacting": True, "interaction_type": "grasping", "iou": round(iou, 3)}
    if iou > 0.05:
        return {"interacting": True, "interaction_type": "nearby", "iou": round(iou, 3)}
    return {"interacting": False, "interaction_type": "clear", "iou": round(iou, 3)}


class MockTracker(BaseTracker):
    """
    Assigns a stable track_id per hand and reports hand-object interactions
    derived from the detector output.
    """

    def __init__(self, num_hands: int = 2):
        self.num_hands = max(1, num_hands)
        self.tracks: Dict[int, Dict[str, Any]] = {}
        self._frame_index = 0
        self._loaded = True

    def update(
        self,
        frame: np.ndarray,
        detections: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        Update tracker with the current frame's detections.

        Returns one track per simulated hand, each carrying interaction info
        for the nearest object of interest.
        """
        self._frame_index += 1

        targets = [
            d for d in detections
            if d.get("class_name") in INTERACTION_TARGETS
        ]

        hand_boxes = [d["bbox"] for d in detections if d.get("class_name") == "hand"]
        # Fall back to synthetic hand positions when the detector produced none
        while len(hand_boxes) < self.num_hands:
            offset = 0.15 * len(hand_boxes)
            hand_boxes.append([0.15 + offset, 0.30, 0.35 + offset, 0.50])

        updated: Dict[int, Dict[str, Any]] = {}

        for index, hand_bbox in enumerate(hand_boxes[: self.num_hands], start=1):
            interaction = {"interacting": False, "interaction_type": "clear", "iou": 0.0}
            for target in targets:
                candidate = classify_interaction(hand_bbox, target["bbox"])
                if candidate["iou"] > interaction["iou"]:
                    interaction = {**candidate, "target_class": target["class_name"]}

            previous = self.tracks.get(index)
            updated[index] = {
                "track_id": index,
                "bbox": hand_bbox,
                "class_id": HAND_CLASS_ID,
                "class_name": "hand",
                "confidence": round(random.uniform(0.85, 0.97), 3),
                "age": (previous["age"] + 1) if previous else 1,
                "interaction": interaction,
            }

        self.tracks = updated
        return list(self.tracks.values())

    def is_loaded(self) -> bool:
        return self._loaded
