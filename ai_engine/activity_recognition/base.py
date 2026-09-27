"""
Base interfaces for Human Activity Recognition (HAR) module.
Defines the contract for temporal activity recognition.
"""
from abc import ABC, abstractmethod
from typing import List, Tuple, Dict, Any, Optional
import numpy as np


class BaseTemporalHAR(ABC):
    """
    Abstract base class for temporal human activity recognition models.
    Takes a sequence of frame-level features and outputs activity classification.
    """

    @abstractmethod
    def predict(
        self,
        feature_sequence: List[Dict[str, Any]],
    ) -> Tuple[str, float]:
        """
        Predict activity from a sequence of frame features.

        Args:
            feature_sequence: List of dicts containing frame-level features:
                - detector_output: List[Dict] from object detector
                - pose_output: List[Dict] from pose estimator
                - tracker_output: List[Dict] from tracker
                - (optional) any custom features

        Returns:
            Tuple of (activity_name: str, confidence: float)
        """
        pass

    @abstractmethod
    def is_loaded(self) -> bool:
        """
        Check if the model is loaded and ready.
        """
        pass

    @property
    @abstractmethod
    def supported_activities(self) -> List[str]:
        """
        List of activity class names the model can recognize.
        """
        pass


class FrameBuffer:
    """
    Fixed-size buffer that accumulates frame-level metadata for temporal analysis.
    """

    def __init__(self, max_size: int = 16):
        """
        Args:
            max_size: Maximum number of frames to store in buffer.
        """
        self.max_size = max_size
        self.buffer: List[Dict[str, Any]] = []

    def add_frame(
        self,
        detector_output: Optional[List[Dict[str, Any]]] = None,
        pose_output: Optional[List[Dict[str, Any]]] = None,
        tracker_output: Optional[List[Dict[str, Any]]] = None,
        extra_features: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Add a new frame's features to the buffer.

        Args:
            detector_output: Output from object detector (BaseDetector.detect).
            pose_output: Output from pose estimator (BasePoseEstimator.estimate_pose).
            tracker_output: Output from tracker (BaseTracker.update).
            extra_features: Any additional custom features (dict).
        """
        frame_data = {
            "detector_output": detector_output or [],
            "pose_output": pose_output or [],
            "tracker_output": tracker_output or [],
            "extra_features": extra_features or {},
        }

        self.buffer.append(frame_data)

        # Maintain fixed size by dropping oldest frames
        if len(self.buffer) > self.max_size:
            self.buffer.pop(0)

    def get_sequence(self) -> List[Dict[str, Any]]:
        """
        Return a copy of the current buffered frame sequence.
        """
        return list(self.buffer)

    def is_full(self) -> bool:
        """
        Check if buffer has reached maximum capacity.
        """
        return len(self.buffer) >= self.max_size

    def clear(self) -> None:
        """
        Reset buffer to empty state.
        """
        self.buffer.clear()

    def __len__(self) -> int:
        return len(self.buffer)