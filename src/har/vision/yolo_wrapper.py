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
    ) -> None:
        self.model_path = Path(model_path)
        self.conf = conf
        self.tracker = tracker
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
        if self.model_path.suffix != ".engine":
            LOGGER.warning(
                "TensorRT engine not selected; using CPU-compatible model %s",
                self.model_path,
            )
        self._model = YOLO(str(self.model_path))
        self._names = getattr(self._model, "names", {}) or {}

    def detect(self, frame: Any) -> list[Detection]:
        """Track one frame; the model owns persistent tracker state."""
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
        for index, box in enumerate(boxes):
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
        return output
