"""
Mock object detector for DEMO_MODE.
Simulates YOLO-style object detection without requiring a GPU or trained weights.
"""
import random
from typing import Any, Dict, List

import numpy as np

from .base import BaseDetector

# Object classes relevant to BAS experiment activities and SIH box experiment
OBJECT_CLASSES = [
    "outer_container",
    "red_box",
    "second_colored_box",
    "astronaut_hand",
    "container",
    "sample_bag",
    "tool",
    "hand",
    "liquid",
    "mixing_stirrer",
    "cylinder",
]


class MockDetector(BaseDetector):
    """
    Generates synthetic bounding-box detections.
    Used when DEMO_MODE is enabled or no real model is available.
    """

    def __init__(self, num_objects: int = 3):
        self.num_objects = max(1, num_objects)
        self._loaded = True

    def detect(self, frame: np.ndarray) -> List[Dict[str, Any]]:
        """
        Generate synthetic detections.

        Returns:
            List of dicts with bbox [x1,y1,x2,y2] normalized to 0-1,
            plus class_id, class_name and confidence.
        """
        detections: List[Dict[str, Any]] = []

        for _ in range(self.num_objects):
            x1 = random.random() * 0.6
            y1 = random.random() * 0.6
            x2 = min(x1 + random.uniform(0.1, 0.3), 0.95)
            y2 = min(y1 + random.uniform(0.1, 0.3), 0.95)

            class_id = random.randrange(len(OBJECT_CLASSES))
            detections.append({
                "bbox": [round(x1, 3), round(y1, 3), round(x2, 3), round(y2, 3)],
                "class_id": class_id,
                "class_name": OBJECT_CLASSES[class_id],
                "confidence": round(random.uniform(0.55, 0.98), 3),
            })

        return detections

    def is_loaded(self) -> bool:
        return self._loaded
