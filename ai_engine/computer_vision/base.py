"""
Base interfaces for Computer Vision module.
Defines the contract for object detection, pose estimation, and tracking.
"""
from abc import ABC, abstractmethod
from typing import List, Tuple, Dict, Any, Optional
import numpy as np


class BaseDetector(ABC):
    """
    Abstract base class for object detectors.
    """

    @abstractmethod
    def detect(self, frame: np.ndarray) -> List[Dict[str, Any]]:
        """
        Detect objects in a frame.

        Args:
            frame: Input image as numpy array (H, W, C) in BGR format.

        Returns:
            List of detections, each detection is a dict with:
                - bbox: [x1, y1, x2, y2] (normalized coordinates 0-1)
                - class_id: int
                - class_name: str
                - confidence: float
        """
        pass

    @abstractmethod
    def is_loaded(self) -> bool:
        """
        Check if the model is loaded and ready.
        """
        pass


class BasePoseEstimator(ABC):
    """
    Abstract base class for pose estimation.
    """

    @abstractmethod
    def estimate_pose(self, frame: np.ndarray) -> List[Dict[str, Any]]:
        """
        Estimate human pose in a frame.

        Args:
            frame: Input image as numpy array (H, W, C) in BGR format.

        Returns:
            List of poses, each pose is a dict with:
                - keypoints: np.array of shape (N, 3) where N is number of keypoints,
                         each keypoint is [x, y, visibility] (normalized 0-1)
                - confidence: float (overall pose confidence)
        """
        pass

    @abstractmethod
    def is_loaded(self) -> bool:
        """
        Check if the model is loaded and ready.
        """
        pass


class BaseTracker(ABC):
    """
    Abstract base class for object tracking.
    """

    @abstractmethod
    def update(self, frame: np.ndarray, detections: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Update tracker with new detections and return tracked objects.

        Args:
            frame: Input image as numpy array (H, W, C) in BGR format.
            detections: List of detections from detector (same format as BaseDetector.detect).

        Returns:
            List of tracked objects, each track is a dict with:
                - track_id: int
                - bbox: [x1, y1, x2, y2] (normalized coordinates 0-1)
                - class_id: int
                - class_name: str
                - confidence: float
                - age: int (number of frames tracked)
        """
        pass

    @abstractmethod
    def is_loaded(self) -> bool:
        """
        Check if the tracker is initialized and ready.
        """
        pass