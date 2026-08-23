"""Annotated local video recorder with a portable OpenCV fallback."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from har.events import Detection

LOGGER = logging.getLogger(__name__)


class VideoRecorder:
    """Render an annotated frame once and publish it to recording and streaming."""

    def __init__(self, output_path: str | Path, fps: float, frame_size: tuple[int, int], frame_hub: Any) -> None:
        import cv2

        self.cv2, self.frame_hub = cv2, frame_hub
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        self.writer = cv2.VideoWriter(str(output_path), fourcc, fps, frame_size)
        LOGGER.warning("Using cv2.VideoWriter fallback; provision NVENC/FFmpeg for accelerated encoding.")

    def annotate(self, frame: Any, detections: list[Detection], state: str) -> Any:
        """Draw tracking and protocol annotations exactly once."""

        annotated = frame.copy()
        for item in detections:
            x1, y1, x2, y2 = (int(value) for value in item.xyxy)
            self.cv2.rectangle(annotated, (x1, y1), (x2, y2), (0, 220, 0), 2)
            self.cv2.putText(annotated, f"{item.cls} {item.conf:.2f} #{item.track_id}", (x1, max(20, y1 - 8)), self.cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 220, 0), 1)
        self.cv2.putText(annotated, f"Step: {state}", (12, 28), self.cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2)
        return annotated

    def write(self, frame: Any, detections: list[Detection], state: str) -> None:
        """Write and share the same annotated frame."""

        annotated = self.annotate(frame, detections, state)
        self.writer.write(annotated)
        self.frame_hub.publish(annotated)

    def close(self) -> None:
        """Release the output file."""

        self.writer.release()
