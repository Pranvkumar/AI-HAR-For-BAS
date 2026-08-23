"""Interface tests for YoloDetector without network, weights, or a GPU."""

from __future__ import annotations

from types import SimpleNamespace

from har.vision.yolo_wrapper import YoloDetector


def test_detect_returns_typed_tracked_detections(tmp_path, monkeypatch) -> None:
    weights = tmp_path / "best.pt"
    weights.touch()
    detector = object.__new__(YoloDetector)
    detector.model_path = weights
    detector.tracker = "bytetrack.yaml"
    detector.frame_skip, detector._frame_number, detector._previous = 1, 0, []
    box = SimpleNamespace(
        cls=SimpleNamespace(item=lambda: 0),
        conf=SimpleNamespace(item=lambda: 0.91),
        xyxy=[SimpleNamespace(tolist=lambda: [1, 2, 30, 40])],
    )
    class Boxes(list):
        pass

    boxes = Boxes([box])
    boxes.id = SimpleNamespace(int=lambda: SimpleNamespace(tolist=lambda: [7]))
    detector.model = SimpleNamespace(track=lambda *args, **kwargs: [SimpleNamespace(boxes=boxes, names={0: "tool"})])
    result = detector.detect(object())
    assert result[0].cls == "tool"
    assert result[0].track_id == 7


def test_engine_path_uses_adjacent_cpu_weights_when_engine_is_missing(tmp_path) -> None:
    weights = tmp_path / "best.pt"
    weights.touch()
    assert YoloDetector._resolve_model(tmp_path / "best.engine") == weights


def test_onnx_backend_and_frame_skip_are_configurable(tmp_path) -> None:
    model = tmp_path / "best.onnx"
    model.touch()
    detector = YoloDetector.__new__(YoloDetector)
    detector.model_path, detector.tracker, detector.backend = model, "bytetrack.yaml", "onnx"
    detector.frame_skip, detector._frame_number, detector._previous = 2, 0, []
    detector.model = SimpleNamespace(track=lambda *args, **kwargs: [])
    assert detector.detect(object()) == []
