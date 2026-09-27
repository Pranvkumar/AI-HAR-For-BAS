"""
Mock pose estimator for DEMO_MODE.
Simulates human skeleton keypoint detection without requiring GPU or models.
"""
import numpy as np
import random
from typing import List, Dict, Any
from .base import BasePoseEstimator


# COCO keypoint names for reference
COCO_KEYPOINTS = [
    "nose", "left_eye", "right_eye", "left_ear", "right_ear",
    "left_shoulder", "right_shoulder", "left_elbow", "right_elbow",
    "left_wrist", "right_wrist", "left_hip", "right_hip",
    "left_knee", "right_knee", "left_ankle", "right_ankle"
]

# Roughly fixed body proportions (normalized 0-1) for a frontal standing pose
_BASE_POSE = [
    [0.50, 0.10],  # nose
    [0.52, 0.08],  # left_eye
    [0.48, 0.08],  # right_eye
    [0.54, 0.09],  # left_ear
    [0.46, 0.09],  # right_ear
    [0.58, 0.22],  # left_shoulder
    [0.42, 0.22],  # right_shoulder
    [0.62, 0.38],  # left_elbow
    [0.38, 0.38],  # right_elbow
    [0.66, 0.52],  # left_wrist
    [0.34, 0.52],  # right_wrist
    [0.55, 0.55],  # left_hip
    [0.45, 0.55],  # right_hip
    [0.56, 0.73],  # left_knee
    [0.44, 0.73],  # right_knee
    [0.57, 0.90],  # left_ankle
    [0.43, 0.90],  # right_ankle
]


class MockPoseEstimator(BasePoseEstimator):
    """
    Generates synthetic human pose keypoints with small random jitter.
    Useful for testing overlays and activity recognition pipeline.
    """

    def __init__(self, jitter: float = 0.015):
        """
        Args:
            jitter: Maximum positional noise applied to each keypoint per frame.
        """
        self.jitter = jitter
        self._loaded = True

    def estimate_pose(self, frame: np.ndarray) -> List[Dict[str, Any]]:
        """
        Return a single synthetic pose for the frame.

        Each keypoint: [x, y, visibility] all normalized to [0, 1].
        visibility is 1.0 if above a confidence threshold, else 0.5.
        """
        keypoints = []
        for base_x, base_y in _BASE_POSE:
            x = float(np.clip(base_x + random.uniform(-self.jitter, self.jitter), 0.0, 1.0))
            y = float(np.clip(base_y + random.uniform(-self.jitter, self.jitter), 0.0, 1.0))
            visibility = round(random.uniform(0.80, 1.0), 3)
            keypoints.append([round(x, 4), round(y, 4), visibility])

        overall_confidence = round(random.uniform(0.82, 0.97), 3)

        return [{
            "keypoints": keypoints,        # List of [x, y, visibility]
            "keypoint_names": COCO_KEYPOINTS,
            "confidence": overall_confidence,
        }]

    def is_loaded(self) -> bool:
        return self._loaded
