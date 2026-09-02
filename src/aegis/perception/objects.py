"""Object detection: the Tier-2 producer the tracker has been waiting for.

``tracking.py`` and ``fusion/interaction.py`` were written against a detection
contract long before a detector existed. This module finally satisfies it. The
contract is small on purpose::

    Detection(label="red_box", confidence=0.91, box=(x1, y1, x2, y2))

Everything downstream -- the IoU tracker, the object state machine, the
hand-object interaction engine, the evidence fuser -- consumes that and nothing
else, so the detector can be swapped without touching any of them.

Why ONNX rather than PyTorch
----------------------------
``onnxruntime`` is already a runtime dependency because the Tier-1 action model
ships as ONNX. Reusing it for objects means the flight-side install stays free of
PyTorch and CUDA toolkits: ~50 MB of wheels instead of ~2.5 GB, no GPU driver
coupling, and the same offline guarantee the rest of the system makes. Training
still happens with PyTorch on the ground -- see ``tools/train_objects.py`` -- but
none of that reaches the payload computer.

The detector is optional and fails soft. A missing model file, a corrupt export
or a missing ``onnxruntime`` degrades to :class:`NullDetector`, which returns no
detections. The pipeline then behaves exactly as it did before this module
existed: Tier 0 keeps running on hands and zones. A perception component that
takes the whole console down with it when its weights are missing would be worse
than no component at all.

Frame budget
------------
Detection does not have to run on every frame. The tracker carries a
constant-velocity model and tolerates 20 consecutive misses, so running the
detector every Nth frame and letting the tracker predict between hits costs
almost nothing in accuracy and gives back most of the frame time. See
``objects_interval`` in ``configs/app.yaml``.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
import json
import logging
from pathlib import Path
import time

import numpy as np

from aegis.perception.tracking import Detection

LOGGER = logging.getLogger(__name__)

try:  # pragma: no cover - exercised implicitly by the runtime
    import onnxruntime as ort
except Exception:  # pragma: no cover
    ort = None  # type: ignore

try:  # pragma: no cover
    import cv2
except Exception:  # pragma: no cover
    cv2 = None  # type: ignore


# =============================================================== geometry ===

@dataclass
class LetterboxTransform:
    """How a frame was fitted into the square network input.

    Stored so detections can be mapped back to original frame pixels. Getting
    this wrong is the classic YOLO integration bug: boxes that look plausible but
    sit a few percent off, which then quietly poisons every IoU in the tracker.
    """

    scale: float
    pad_x: float
    pad_y: float
    src_w: int
    src_h: int

    def to_source(self, boxes: np.ndarray) -> np.ndarray:
        """Map (N, 4) x1y1x2y2 boxes from network space back to frame pixels."""
        if boxes.size == 0:
            return boxes
        out = boxes.astype(np.float32).copy()
        out[:, [0, 2]] -= self.pad_x
        out[:, [1, 3]] -= self.pad_y
        out /= max(self.scale, 1e-9)
        out[:, [0, 2]] = np.clip(out[:, [0, 2]], 0.0, self.src_w)
        out[:, [1, 3]] = np.clip(out[:, [1, 3]], 0.0, self.src_h)
        return out


def letterbox(frame: np.ndarray, size: int, pad_value: int = 114) -> tuple[np.ndarray, LetterboxTransform]:
    """Resize preserving aspect ratio, pad to a square ``size`` x ``size``."""
    src_h, src_w = frame.shape[:2]
    scale = min(size / max(src_h, 1), size / max(src_w, 1))
    new_w = max(1, int(round(src_w * scale)))
    new_h = max(1, int(round(src_h * scale)))

    if cv2 is not None:
        resized = cv2.resize(frame, (new_w, new_h), interpolation=cv2.INTER_LINEAR)
    else:  # pragma: no cover - nearest-neighbour fallback, tests only
        ys = (np.arange(new_h) / scale).astype(np.int32).clip(0, src_h - 1)
        xs = (np.arange(new_w) / scale).astype(np.int32).clip(0, src_w - 1)
        resized = frame[ys][:, xs]

    canvas = np.full((size, size, 3), pad_value, dtype=frame.dtype)
    pad_x = (size - new_w) // 2
    pad_y = (size - new_h) // 2
    canvas[pad_y:pad_y + new_h, pad_x:pad_x + new_w] = resized
    return canvas, LetterboxTransform(scale, float(pad_x), float(pad_y), src_w, src_h)


def nms(boxes: np.ndarray, scores: np.ndarray, iou_threshold: float) -> list[int]:
    """Greedy non-maximum suppression. Pure NumPy so it is testable offline."""
    if boxes.size == 0:
        return []
    x1, y1, x2, y2 = boxes[:, 0], boxes[:, 1], boxes[:, 2], boxes[:, 3]
    areas = np.maximum(0.0, x2 - x1) * np.maximum(0.0, y2 - y1)
    order = scores.argsort()[::-1]

    keep: list[int] = []
    while order.size > 0:
        i = int(order[0])
        keep.append(i)
        if order.size == 1:
            break
        rest = order[1:]
        ix1 = np.maximum(x1[i], x1[rest])
        iy1 = np.maximum(y1[i], y1[rest])
        ix2 = np.minimum(x2[i], x2[rest])
        iy2 = np.minimum(y2[i], y2[rest])
        inter = np.maximum(0.0, ix2 - ix1) * np.maximum(0.0, iy2 - iy1)
        union = areas[i] + areas[rest] - inter
        iou = np.where(union > 0, inter / np.maximum(union, 1e-9), 0.0)
        order = rest[iou <= iou_threshold]
    return keep


# ============================================================ postprocess ===

def decode_yolo_output(
    raw: np.ndarray,
    transform: LetterboxTransform,
    labels: list[str],
    *,
    confidence: float = 0.45,
    iou_threshold: float = 0.5,
    max_detections: int = 30,
) -> list[Detection]:
    """Turn a raw YOLO head tensor into :class:`Detection` objects.

    Handles both common export layouts:

    * ``(1, 4 + nc, N)`` -- Ultralytics YOLOv8/v11 default, channels first
    * ``(1, N, 4 + nc)`` -- already transposed

    Boxes arrive as centre-x, centre-y, width, height in network pixels. There is
    no separate objectness column in v8; class scores carry the confidence.
    Suppression is per class, so a red box and a blue box overlapping in the
    frame do not suppress one another -- which matters here, because
    distinguishing them is the entire point of having a detector.
    """
    arr = np.asarray(raw, dtype=np.float32)
    if arr.ndim == 3:
        arr = arr[0]
    if arr.ndim != 2:
        raise ValueError(f"unexpected detector output shape: {np.asarray(raw).shape}")

    # Orient to (N, 4 + nc). Prefer an exact match against the label list; fall
    # back to "the anchor axis is the longer one", which holds for any realistic
    # class count and anchor grid.
    n_expected = 4 + len(labels) if labels else None
    if n_expected is not None and arr.shape[0] == n_expected and arr.shape[1] != n_expected:
        arr = arr.T
    elif n_expected is None and arr.shape[0] < arr.shape[1]:
        arr = arr.T

    # Last resort: a feature axis needs at least 4 box columns plus one class.
    # This catches single-anchor outputs, where "longer axis" is meaningless.
    if arr.shape[1] < 5 <= arr.shape[0]:
        arr = arr.T

    if arr.shape[1] < 5:
        return []

    xywh = arr[:, :4]
    class_scores = arr[:, 4:]
    best = class_scores.argmax(axis=1)
    conf = class_scores[np.arange(class_scores.shape[0]), best]

    keep_mask = conf >= confidence
    if not np.any(keep_mask):
        return []
    xywh, best, conf = xywh[keep_mask], best[keep_mask], conf[keep_mask]

    boxes = np.empty_like(xywh)
    boxes[:, 0] = xywh[:, 0] - xywh[:, 2] / 2.0
    boxes[:, 1] = xywh[:, 1] - xywh[:, 3] / 2.0
    boxes[:, 2] = xywh[:, 0] + xywh[:, 2] / 2.0
    boxes[:, 3] = xywh[:, 1] + xywh[:, 3] / 2.0
    boxes = transform.to_source(boxes)

    out: list[Detection] = []
    for cls in np.unique(best):
        idx = np.where(best == cls)[0]
        kept = nms(boxes[idx], conf[idx], iou_threshold)
        for k in kept:
            j = idx[k]
            label = labels[int(cls)] if int(cls) < len(labels) else f"class_{int(cls)}"
            out.append(Detection(
                label=label,
                confidence=float(conf[j]),
                box=(float(boxes[j, 0]), float(boxes[j, 1]),
                     float(boxes[j, 2]), float(boxes[j, 3])),
            ))

    out.sort(key=lambda d: d.confidence, reverse=True)
    return out[:max_detections]


def load_labels(model_path: Path, session=None) -> list[str]:
    """Recover class names from ONNX metadata, a sidecar file, or neither.

    Ultralytics writes ``names`` into the ONNX custom metadata at export time, so
    the usual case needs no sidecar. A ``<model>.names.json`` or ``<model>.txt``
    beside the model overrides it, which is the escape hatch for exports produced
    by other tooling.
    """
    sidecar_json = model_path.with_suffix(".names.json")
    if sidecar_json.exists():
        try:
            data = json.loads(sidecar_json.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return [data[k] for k in sorted(data, key=lambda x: int(x))]
            if isinstance(data, list):
                return [str(x) for x in data]
        except Exception as exc:
            LOGGER.warning("could not read %s: %s", sidecar_json.name, exc)

    sidecar_txt = model_path.with_suffix(".txt")
    if sidecar_txt.exists():
        lines = [ln.strip() for ln in sidecar_txt.read_text(encoding="utf-8").splitlines()]
        names = [ln for ln in lines if ln]
        if names:
            return names

    if session is not None:
        try:
            meta = session.get_modelmeta().custom_metadata_map or {}
            raw = meta.get("names")
            if raw:
                # Ultralytics writes a Python dict *repr* -- "{0: 'red_box'}" --
                # whose integer keys are unquoted, so it is not valid JSON and no
                # amount of quote-swapping makes it so. literal_eval reads it
                # natively; JSON is the fallback for other exporters.
                try:
                    parsed = ast.literal_eval(raw)
                except (ValueError, SyntaxError):
                    parsed = json.loads(raw)
                if isinstance(parsed, dict):
                    return [str(parsed[k]) for k in sorted(parsed, key=lambda x: int(x))]
                if isinstance(parsed, (list, tuple)):
                    return [str(x) for x in parsed]
        except Exception as exc:
            LOGGER.debug("no usable class names in ONNX metadata: %s", exc)

    return []


# =============================================================== detectors ===

class NullDetector:
    """The no-op detector. Returns nothing, forever, without complaining.

    This is what runs when object detection is disabled or unavailable, and it is
    what makes the feature genuinely optional: the pipeline calls the same method
    either way and Tier 0 carries on untouched.
    """

    available = False

    def __init__(self, reason: str = "object detection disabled") -> None:
        self.reason = reason
        self.labels: list[str] = []

    def detect(self, frame) -> list[Detection]:
        return []

    def describe(self) -> str:
        return self.reason

    def stats(self) -> dict:
        return {"available": False, "reason": self.reason, "inferences": 0}

    def close(self) -> None:
        pass


class OnnxObjectDetector:
    """A YOLO-family detector running on onnxruntime, CPU or CUDA.

    Constructed through :func:`build_detector` rather than directly, so that a
    missing model degrades to :class:`NullDetector` instead of raising into the
    pipeline thread.
    """

    available = True

    def __init__(
        self,
        model_path: str | Path,
        *,
        confidence: float = 0.45,
        iou_threshold: float = 0.5,
        input_size: int | None = None,
        providers: list[str] | None = None,
        max_detections: int = 30,
    ) -> None:
        if ort is None:
            raise RuntimeError("onnxruntime is not installed")
        self.model_path = Path(model_path)
        if not self.model_path.exists():
            raise FileNotFoundError(f"detector model not found: {self.model_path}")

        self.confidence = float(confidence)
        self.iou_threshold = float(iou_threshold)
        self.max_detections = int(max_detections)

        available = list(ort.get_available_providers())
        wanted = providers or ["CUDAExecutionProvider", "CPUExecutionProvider"]
        chosen = [p for p in wanted if p in available] or ["CPUExecutionProvider"]

        options = ort.SessionOptions()
        options.log_severity_level = 3
        self.session = ort.InferenceSession(
            str(self.model_path), sess_options=options, providers=chosen
        )
        self.providers = list(self.session.get_providers())

        inp = self.session.get_inputs()[0]
        self.input_name = inp.name
        shape = list(inp.shape)
        # NCHW with possibly-dynamic H/W; fall back to 640 which is the
        # Ultralytics default export size.
        inferred = None
        if len(shape) == 4 and isinstance(shape[2], int) and shape[2] > 0:
            inferred = int(shape[2])
        self.input_size = int(input_size or inferred or 640)

        self.labels = load_labels(self.model_path, self.session)
        self._inferences = 0
        self._total_ms = 0.0

    # -----------------------------------------------------------------

    def detect(self, frame) -> list[Detection]:
        """Run one inference. Returns [] on any failure rather than raising."""
        if frame is None or getattr(frame, "size", 0) == 0:
            return []
        try:
            started = time.perf_counter()
            padded, transform = letterbox(np.asarray(frame), self.input_size)
            # BGR -> RGB, HWC -> CHW, 0-255 -> 0-1
            blob = padded[:, :, ::-1].astype(np.float32) / 255.0
            blob = np.transpose(blob, (2, 0, 1))[None, ...]
            blob = np.ascontiguousarray(blob)

            raw = self.session.run(None, {self.input_name: blob})[0]
            detections = decode_yolo_output(
                raw, transform, self.labels,
                confidence=self.confidence,
                iou_threshold=self.iou_threshold,
                max_detections=self.max_detections,
            )
            self._inferences += 1
            self._total_ms += (time.perf_counter() - started) * 1000.0
            return detections
        except Exception as exc:  # pragma: no cover - defensive
            LOGGER.warning("object detection failed: %s", exc)
            return []

    @property
    def mean_latency_ms(self) -> float:
        return self._total_ms / self._inferences if self._inferences else 0.0

    def describe(self) -> str:
        backend = "CUDA" if any("CUDA" in p for p in self.providers) else "CPU"
        classes = ", ".join(self.labels[:6]) if self.labels else "unnamed classes"
        return f"{self.model_path.name} [{backend}] {self.input_size}px ({classes})"

    def stats(self) -> dict:
        return {
            "available": True,
            "model": self.model_path.name,
            "providers": self.providers,
            "input_size": self.input_size,
            "labels": list(self.labels),
            "inferences": self._inferences,
            "mean_latency_ms": round(self.mean_latency_ms, 2),
        }

    def close(self) -> None:
        self.session = None


def build_detector(config) -> NullDetector | OnnxObjectDetector:
    """Construct the configured detector, degrading to a no-op on any problem.

    Every failure path here is a warning, never an exception. Object detection is
    an enhancement to a system that already works without it, and the cost of a
    missing weights file should be reduced capability, not a dead console.
    """
    if not getattr(config, "objects_enabled", False):
        return NullDetector("object detection disabled in config")

    if ort is None:
        return NullDetector("onnxruntime not installed")

    path = config.objects_model_file
    if not path.exists():
        return NullDetector(f"detector model missing: {path.name}")

    if path.suffix.lower() != ".onnx":
        return NullDetector(
            f"detector model must be .onnx, got '{path.suffix}' "
            f"(export it: python -m aegis.tools.train_objects --export {path.name})"
        )

    try:
        detector = OnnxObjectDetector(
            path,
            confidence=getattr(config, "objects_confidence", 0.45),
            iou_threshold=getattr(config, "objects_iou", 0.5),
            input_size=getattr(config, "objects_input_size", None) or None,
            providers=getattr(config, "objects_providers", None) or None,
        )
        LOGGER.info("object detector ready: %s", detector.describe())
        return detector
    except Exception as exc:
        LOGGER.warning("object detector unavailable: %s", exc)
        return NullDetector(f"detector failed to load: {exc}")
