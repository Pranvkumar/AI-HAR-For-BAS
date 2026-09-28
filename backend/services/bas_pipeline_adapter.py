"""Adapter exposing the stable BAS pipeline to the web backend."""

from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from threading import Lock
from typing import Any

from aegis.config import load_config
from aegis.pipeline import HARPipeline, PipelineStatus


class BASPipelineAdapter:
    """Own one real BAS pipeline without reimplementing vision or validation."""

    def __init__(self, config_path: str | Path = "configs/app.yaml") -> None:
        self.config_path = Path(config_path)
        self._lock = Lock()
        self._pipeline: HARPipeline | None = None
        self._event_cursor = 0

    def start(self) -> PipelineStatus:
        with self._lock:
            if self._pipeline is None:
                config = load_config(self.config_path)
                self._pipeline = HARPipeline(config, on_event=lambda _event: None)
            self._event_cursor = 0
            return self._pipeline.start()

    def stop(self) -> Path | None:
        with self._lock:
            if self._pipeline is None:
                return None
            result = self._pipeline.stop()
            self._pipeline = None
            self._event_cursor = 0
            return result

    @property
    def pipeline(self) -> HARPipeline:
        with self._lock:
            if self._pipeline is None:
                raise RuntimeError("BAS pipeline has not been started")
            return self._pipeline

    def snapshot(self) -> dict[str, Any]:
        return asdict(self.pipeline.snapshot())

    def latest_frame(self):
        return self.pipeline.latest_frame()

    def drain_events(self) -> list[Any]:
        return self.pipeline.drain_events()

    def protocol_snapshot(self) -> dict[str, Any]:
        return self.pipeline.protocol_snapshot()

    def vision_payload(self) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[list[float]]]:
        """Project the latest BAS perception state into browser coordinates."""
        pipeline = self.pipeline
        frame = pipeline._raw
        if frame is None:
            return [], [], []
        height, width = frame.shape[:2]

        def point(point: Any) -> list[float]:
            return [float(point[0]) / max(width, 1), float(point[1]) / max(height, 1)]

        boxes: list[dict[str, Any]] = []
        for track in pipeline._last_tracks:
            x1, y1, x2, y2 = track.box
            boxes.append({
                "bbox": [x1 / width, y1 / height, x2 / width, y2 / height],
                "class_name": track.label,
                "confidence": float(track.confidence),
            })

        poses: list[dict[str, Any]] = []
        hand_points: list[list[float]] = []
        perception = pipeline._last_perception
        if perception is not None:
            for hand in perception.hands:
                hand_points.extend(point(p) for p in hand.points_px)
                boxes.append({
                    "bbox": [
                        float(hand.points_px[:, 0].min()) / width,
                        float(hand.points_px[:, 1].min()) / height,
                        float(hand.points_px[:, 0].max()) / width,
                        float(hand.points_px[:, 1].max()) / height,
                    ],
                    "class_name": f"{hand.label}_hand",
                    "confidence": float(hand.score),
                })
            if perception.pose is not None:
                poses.append({
                    "keypoints": [
                        [float(x) / width, float(y) / height, float(v)]
                        for (x, y), v in zip(perception.pose.points_px, perception.pose.visibility)
                    ]
                })
        return boxes, poses, hand_points

    def acknowledge(self) -> None:
        self.pipeline.acknowledge()

    def manual_skip(self) -> None:
        self.pipeline.manual_skip()

    def reset_protocol(self) -> None:
        self.pipeline.reset_protocol()

    def is_running(self) -> bool:
        return self.pipeline.running
