"""Single-instance Ultralytics tracking adapter with a CPU fallback."""

from dataclasses import dataclass
import importlib
import logging
from pathlib import Path
from typing import Any

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class Detection:
    cls: int | str
    conf: float
    xyxy: tuple[float, float, float, float]
    track_id: int | None = None


class YoloDetector:
    """Load exactly one model and normalize tracked results to ``Detection``."""

    def __init__(
        self,
        model_path: str | Path,
        *,
        conf: float = 0.25,
        tracker: str = "bytetrack.yaml",
        backend: str = "auto",
        frame_skip: int = 1,
    ) -> None:
        self.model_path = Path(model_path)
        self.conf = conf
        self.tracker = tracker
        self.backend = backend
        self.frame_skip = max(1, frame_skip)
        self._frame_index = 0
        self._previous: list[Detection] = []
        self._latest: list[Detection] = []
        self._model: Any = None
        self._names: dict[int, str] = {}
        self._load()

    def _load(self) -> None:
        try:
            YOLO = importlib.import_module("ultralytics").YOLO
        except ImportError as error:
            raise RuntimeError(
                "ultralytics is required to construct YoloDetector"
            ) from error
        if self.backend.lower() == "onnx" and self.model_path.suffix != ".onnx":
            onnx_path = self.model_path.with_suffix(".onnx")
            if onnx_path.exists():
                self.model_path = onnx_path
            else:
                LOGGER.warning("ONNX backend requested but %s was not found; using %s", onnx_path, self.model_path)
        if self.model_path.suffix != ".engine":
            LOGGER.warning(
                "TensorRT engine not selected; using CPU-compatible model %s",
                self.model_path,
            )
        self._model = YOLO(str(self.model_path))
        self._names = getattr(self._model, "names", {}) or {}

    def detect(self, frame: Any) -> list[Detection]:
        """Track one frame; the model owns persistent tracker state."""
        self._frame_index += 1
        if self.frame_skip > 1 and self._frame_index % self.frame_skip != 1:
            return self._interpolate()
        results = self._model.track(
            frame, persist=True, tracker=self.tracker, conf=self.conf, verbose=False
        )
        if not results:
            return []
        result = results[0]
        boxes = getattr(result, "boxes", None)
        if boxes is None:
            return []
        output = []
        for box in boxes:
            coords = tuple(float(value) for value in box.xyxy[0].tolist())
            class_id = int(box.cls[0].item())
            track = getattr(box, "id", None)
            track_id = int(track[0].item()) if track is not None else None
            output.append(
                Detection(
                    self._names.get(class_id, class_id),
                    float(box.conf[0].item()),
                    coords,
                    track_id,
                )
            )
        self._previous, self._latest = self._latest, output
        return output

    def _interpolate(self) -> list[Detection]:
        """Coast tracked boxes linearly between the last two YOLO results."""
        if not self._latest:
            return []
        predictions = []
        for current in self._latest:
            prior = next((item for item in self._previous if item.track_id == current.track_id), None)
            if prior is None:
                predictions.append(current)
                continue
            delta = tuple(current.xyxy[index] - prior.xyxy[index] for index in range(4))
            predictions.append(Detection(current.cls, current.conf,
                                         tuple(current.xyxy[index] + delta[index] / 2 for index in range(4)),
                                         current.track_id))
        return predictions
