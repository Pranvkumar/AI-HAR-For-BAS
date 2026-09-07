"""Thin, tracked YOLO detector with an offline CPU fallback."""

from __future__ import annotations

import logging
from dataclasses import replace
from pathlib import Path
from typing import Any

from har.events import Detection

LOGGER = logging.getLogger(__name__)


class YoloDetector:
    """Run a single YOLO model instance and return ByteTrack/BoT-SORT detections."""

    def __init__(self, model_path: str | Path, tracker: str = "bytetrack.yaml", backend: str = "tensorrt", frame_skip: int = 1) -> None:
        requested = Path(model_path)
        self.backend = backend.lower()
        if self.backend not in {"auto", "tensorrt", "onnx"}:
            raise ValueError("backend must be 'tensorrt' or 'onnx'")
        if frame_skip < 1:
            raise ValueError("frame_skip must be at least one")
        self.model_path = self._resolve_model(requested)
        self.tracker, self.frame_skip = tracker, frame_skip
        self._frame_number = 0
        self._previous: list[Detection] = []
        self.model = self._load_model(self.model_path)

    @staticmethod
    def _resolve_model(requested: Path) -> Path:
        """Prefer an existing engine; otherwise use an adjacent or requested .pt file."""

        if requested.suffix in {".engine", ".onnx"} and requested.exists():
            return requested
        if requested.suffix in {".engine", ".onnx"}:
            fallback = requested.with_suffix(".pt")
            if fallback.exists():
                LOGGER.warning("TensorRT engine missing; falling back to CPU weights: %s", fallback)
                return fallback
            raise FileNotFoundError(f"Neither engine nor CPU fallback exists for {requested}")
        if requested.exists():
            return requested
        raise FileNotFoundError(f"YOLO weights not found: {requested}")

    @staticmethod
    def _load_model(path: Path) -> Any:
        """Import Ultralytics lazily so non-vision tests remain lightweight."""

        try:
            from ultralytics import YOLO
        except ImportError as error:
            raise RuntimeError("Install the project's vision dependencies before loading YOLO.") from error
        return YOLO(str(path))

    def detect(self, frame: Any) -> list[Detection]:
        """Track objects in a BGR frame without silently downloading any model."""

        self._frame_number += 1
        if self.frame_skip > 1 and self._previous and self._frame_number % self.frame_skip:
            return list(self._previous)
        device = "cpu" if self.model_path.suffix in {".pt", ".onnx"} else None
        results = self.model.track(frame, persist=True, tracker=self.tracker, verbose=False, device=device)
        if not results:
            return []
        result = results[0]
        boxes = getattr(result, "boxes", None)
        if boxes is None:
            return []
        names = getattr(result, "names", {})
        ids = boxes.id.int().tolist() if getattr(boxes, "id", None) is not None else []
        detections: list[Detection] = []
        for index, box in enumerate(boxes):
            class_index = int(box.cls.item())
            label = str(names.get(class_index, class_index)) if isinstance(names, dict) else str(class_index)
            detections.append(
                Detection(
                    cls=label,
                    conf=float(box.conf.item()),
                    xyxy=tuple(float(value) for value in box.xyxy[0].tolist()),
                    track_id=int(ids[index]) if index < len(ids) else None,
                )
            )
        self._previous = detections
        return detections
