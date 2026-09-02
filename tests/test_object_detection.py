"""Tests for Tier-2 object detection and the object-identity evidence channel.

The decode path is tested against a real ONNX graph rather than a mock. A mocked
session would happily confirm a transposed-axis bug or an inverted letterbox
correction -- both of which produce boxes that look plausible and quietly poison
every IoU in the tracker. Building a tiny graph that emits a known detection at a
known pixel makes the geometry falsifiable.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pytest

from aegis.fusion.evidence import Source
from aegis.fusion.object_evidence import ObjectMatch, ObjectVerifier
from aegis.perception.objects import (
    LetterboxTransform,
    NullDetector,
    build_detector,
    decode_yolo_output,
    letterbox,
    load_labels,
    nms,
)
from aegis.perception.tracking import Detection


# ================================================================= geometry ===

def test_letterbox_preserves_aspect_ratio_and_centres_the_image():
    frame = np.zeros((720, 1280, 3), dtype=np.uint8)
    padded, transform = letterbox(frame, 640)

    assert padded.shape == (640, 640, 3)
    assert transform.scale == pytest.approx(0.5, abs=0.01)
    # 1280x720 -> 640x360, so 140px of padding above and below, none at the sides
    assert transform.pad_x == pytest.approx(0, abs=1)
    assert transform.pad_y == pytest.approx(140, abs=1)


def test_letterbox_round_trip_recovers_original_pixel_coordinates():
    """A box drawn in source pixels must survive the trip through network space."""
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    _, transform = letterbox(frame, 640)

    original = np.array([[100.0, 200.0, 300.0, 400.0]], dtype=np.float32)
    # forward: source -> network
    forward = original * transform.scale
    forward[:, [0, 2]] += transform.pad_x
    forward[:, [1, 3]] += transform.pad_y
    # and back again
    recovered = transform.to_source(forward)

    assert recovered == pytest.approx(original, abs=0.5)


def test_to_source_clips_boxes_to_the_frame():
    transform = LetterboxTransform(scale=1.0, pad_x=0.0, pad_y=0.0, src_w=100, src_h=100)
    boxes = np.array([[-50.0, -50.0, 500.0, 500.0]], dtype=np.float32)
    clipped = transform.to_source(boxes)
    assert clipped.tolist() == [[0.0, 0.0, 100.0, 100.0]]


# ====================================================================== nms ===

def test_nms_suppresses_overlapping_boxes_and_keeps_the_best():
    boxes = np.array([
        [0, 0, 100, 100],
        [5, 5, 105, 105],      # heavy overlap with the first
        [500, 500, 600, 600],  # disjoint
    ], dtype=np.float32)
    scores = np.array([0.9, 0.8, 0.7], dtype=np.float32)

    kept = nms(boxes, scores, 0.5)
    assert sorted(kept) == [0, 2]


def test_nms_on_empty_input_returns_nothing():
    assert nms(np.empty((0, 4), dtype=np.float32), np.empty(0, dtype=np.float32), 0.5) == []


# ================================================================== decode ===

def _raw_yolo_output(cx, cy, w, h, class_scores, *, transposed=True):
    """Build a single-anchor YOLOv8-style head tensor."""
    row = np.array([cx, cy, w, h] + list(class_scores), dtype=np.float32)
    arr = row[None, :]                      # (1, 4 + nc)
    return arr.T[None, ...] if transposed else arr[None, ...]


def test_decode_handles_the_channels_first_export_layout():
    transform = LetterboxTransform(scale=1.0, pad_x=0.0, pad_y=0.0, src_w=640, src_h=640)
    raw = _raw_yolo_output(320, 320, 100, 50, [0.9, 0.1], transposed=True)

    detections = decode_yolo_output(raw, transform, ["red_box", "blue_box"], confidence=0.4)

    assert len(detections) == 1
    assert detections[0].label == "red_box"
    assert detections[0].box == pytest.approx((270.0, 295.0, 370.0, 345.0), abs=0.5)


def test_decode_handles_the_already_transposed_layout():
    transform = LetterboxTransform(scale=1.0, pad_x=0.0, pad_y=0.0, src_w=640, src_h=640)
    raw = _raw_yolo_output(320, 320, 100, 50, [0.9, 0.1], transposed=False)

    detections = decode_yolo_output(raw, transform, ["red_box", "blue_box"], confidence=0.4)
    assert len(detections) == 1
    assert detections[0].label == "red_box"


def test_decode_respects_the_confidence_floor():
    transform = LetterboxTransform(scale=1.0, pad_x=0.0, pad_y=0.0, src_w=640, src_h=640)
    raw = _raw_yolo_output(320, 320, 100, 50, [0.30, 0.05])

    assert decode_yolo_output(raw, transform, ["red_box", "blue_box"], confidence=0.45) == []
    assert len(decode_yolo_output(raw, transform, ["red_box", "blue_box"], confidence=0.20)) == 1


def test_decode_suppresses_per_class_so_two_objects_can_overlap():
    """A red box in front of a blue one must not erase the blue detection.

    Class-agnostic NMS would drop the lower-scoring box here, which is exactly
    the pair the wrong-object check depends on being able to tell apart.
    """
    transform = LetterboxTransform(scale=1.0, pad_x=0.0, pad_y=0.0, src_w=640, src_h=640)
    red = np.array([320, 320, 100, 100, 0.90, 0.02], dtype=np.float32)
    blue = np.array([325, 325, 100, 100, 0.02, 0.80], dtype=np.float32)
    raw = np.stack([red, blue])[None, ...]

    detections = decode_yolo_output(raw, transform, ["red_box", "blue_box"], confidence=0.4)

    assert {d.label for d in detections} == {"red_box", "blue_box"}


def test_decode_names_unknown_classes_rather_than_crashing():
    transform = LetterboxTransform(scale=1.0, pad_x=0.0, pad_y=0.0, src_w=640, src_h=640)
    raw = _raw_yolo_output(320, 320, 100, 50, [0.1, 0.9])

    detections = decode_yolo_output(raw, transform, [], confidence=0.4)
    assert detections[0].label == "class_1"


def test_decode_rejects_a_malformed_tensor():
    transform = LetterboxTransform(scale=1.0, pad_x=0.0, pad_y=0.0, src_w=640, src_h=640)
    with pytest.raises(ValueError):
        decode_yolo_output(np.zeros((2, 3, 4, 5), dtype=np.float32), transform, ["a"])


# ================================================================== labels ===

def test_load_labels_prefers_the_json_sidecar(tmp_path):
    model = tmp_path / "objects.onnx"
    model.write_bytes(b"not really a model")
    model.with_suffix(".names.json").write_text('["red_box", "blue_box"]', encoding="utf-8")

    assert load_labels(model) == ["red_box", "blue_box"]


def test_load_labels_reads_a_plain_text_sidecar(tmp_path):
    model = tmp_path / "objects.onnx"
    model.write_bytes(b"stub")
    model.with_suffix(".txt").write_text("red_box\nblue_box\n\n", encoding="utf-8")

    assert load_labels(model) == ["red_box", "blue_box"]


def test_load_labels_returns_empty_when_nothing_is_available(tmp_path):
    model = tmp_path / "objects.onnx"
    model.write_bytes(b"stub")
    assert load_labels(model) == []


# ============================================================ graceful fail ===

@dataclass
class _Config:
    """Minimal stand-in for AppConfig."""
    objects_enabled: bool = True
    objects_confidence: float = 0.45
    objects_iou: float = 0.5
    objects_input_size: int = 0
    objects_providers: list | None = None
    _path: Path = Path("missing.onnx")

    @property
    def objects_model_file(self) -> Path:
        return self._path


def test_detector_is_null_when_disabled():
    detector = build_detector(_Config(objects_enabled=False))
    assert not detector.available
    assert detector.detect(np.zeros((10, 10, 3), dtype=np.uint8)) == []


def test_detector_is_null_when_the_model_file_is_missing(tmp_path):
    detector = build_detector(_Config(_path=tmp_path / "nope.onnx"))
    assert not detector.available
    assert "missing" in detector.describe().lower()


def test_detector_rejects_a_torch_checkpoint_with_a_useful_message(tmp_path):
    """`best.pt` is the file people naturally reach for; say what to do instead."""
    checkpoint = tmp_path / "best.pt"
    checkpoint.write_bytes(b"stub")

    detector = build_detector(_Config(_path=checkpoint))
    assert not detector.available
    assert ".onnx" in detector.describe()
    assert "train_objects" in detector.describe()


def test_null_detector_reports_stats_without_raising():
    detector = NullDetector("no model")
    assert detector.stats()["available"] is False
    detector.close()


# ============================================== object identity as evidence ===

@dataclass
class _Track:
    """Stand-in for a confirmed tracker Track."""
    track_id: int
    label: str
    centre: np.ndarray
    confidence: float = 0.9
    confirmed: bool = True
    state: str = "grasped"


def test_correct_object_in_hand_supports_the_step():
    verifier = ObjectVerifier()
    tracks = [_Track(1, "red_box", np.array([100.0, 100.0], dtype=np.float32))]

    assessment = verifier.assess("red_box", tracks, [np.array([110.0, 105.0])])

    assert assessment.match is ObjectMatch.MATCH
    assert assessment.score > 0.9
    assert assessment.as_evidence().source is Source.OBJECT


def test_wrong_object_in_hand_actively_rejects():
    """The whole point of the detector: correct gesture, wrong container."""
    verifier = ObjectVerifier()
    tracks = [_Track(1, "blue_box", np.array([100.0, 100.0], dtype=np.float32))]

    assessment = verifier.assess("red_box", tracks, [np.array([105.0, 100.0])])

    assert assessment.match is ObjectMatch.MISMATCH
    assert assessment.score < 0.15
    assert assessment.weight > 0.5          # decisive, not advisory
    assert "WRONG OBJECT" in assessment.label
    assert assessment.observed == "blue_box"


def test_an_unseen_object_is_neutral_rather_than_a_violation():
    """Absence of evidence must not become evidence of the wrong object."""
    verifier = ObjectVerifier()

    assessment = verifier.assess("red_box", [], [np.array([100.0, 100.0])])

    assert assessment.match is ObjectMatch.ABSENT
    assert 0.3 < assessment.score < 0.5     # neutral band
    assert assessment.weight < 0.2          # and barely trusted either way


def test_a_distant_object_is_absent_not_in_hand():
    verifier = ObjectVerifier(contact_px=100.0)
    tracks = [_Track(1, "red_box", np.array([1000.0, 1000.0], dtype=np.float32))]

    assessment = verifier.assess("red_box", tracks, [np.array([100.0, 100.0])])

    assert assessment.match is ObjectMatch.ABSENT
    assert assessment.distance_px > 100.0


def test_unconfirmed_tracks_are_ignored():
    """Three hits are required before anything acts on a track."""
    verifier = ObjectVerifier()
    tracks = [_Track(1, "blue_box", np.array([100.0, 100.0], dtype=np.float32), confirmed=False)]

    assessment = verifier.assess("red_box", tracks, [np.array([100.0, 100.0])])
    assert assessment.match is ObjectMatch.ABSENT


def test_a_step_naming_no_object_contributes_nothing():
    verifier = ObjectVerifier()
    assessment = verifier.assess(None, [], [])

    assert assessment.match is ObjectMatch.NOT_REQUIRED
    assert not assessment.contributes
    assert assessment.as_evidence() is None


def test_the_channel_stays_silent_when_no_detector_is_running():
    """Tier 0 sessions must not be penalised for lacking a detector."""
    verifier = ObjectVerifier()
    assessment = verifier.assess("red_box", [], [], detector_available=False)

    assert assessment.match is ObjectMatch.NO_DETECTOR
    assert not assessment.contributes
    assert assessment.as_evidence() is None


def test_a_grasped_track_wins_over_a_merely_closer_one():
    """A held object outranks one that happens to sit nearer the hand centroid."""
    verifier = ObjectVerifier()
    held = _Track(1, "red_box", np.array([120.0, 100.0], dtype=np.float32), state="objectstate.grasped")
    nearby = _Track(2, "blue_box", np.array([105.0, 100.0], dtype=np.float32), state="stored")

    assessment = verifier.assess("red_box", [held, nearby], [np.array([100.0, 100.0])])

    assert assessment.match is ObjectMatch.MATCH
    assert assessment.track_id == 1


def test_mismatch_evidence_carries_both_labels_into_the_audit_detail():
    verifier = ObjectVerifier()
    tracks = [_Track(7, "sample", np.array([100.0, 100.0], dtype=np.float32))]

    evidence = verifier.assess("red_box", tracks, [np.array([100.0, 100.0])]).as_evidence()

    assert evidence.detail["expected"] == "red_box"
    assert evidence.detail["observed"] == "sample"
    assert evidence.detail["track_id"] == 7


# ============================================================== end to end ===

def test_a_real_onnx_graph_decodes_to_the_expected_pixel_box(tmp_path):
    """Build a genuine ONNX detector, run it, and check where the box lands.

    This is the test that would catch a transposed axis or an inverted letterbox
    correction -- failures that mocks reproduce perfectly and therefore hide.
    """
    onnx = pytest.importorskip("onnx")
    ort = pytest.importorskip("onnxruntime")
    from onnx import TensorProto, helper, numpy_helper

    # A graph that ignores its input and emits one fixed detection: a 100x50 box
    # centred at (320, 320) in 640x640 network space, class 0 at score 0.9.
    constant = np.array([[[320.0], [320.0], [100.0], [50.0], [0.9], [0.1]]], dtype=np.float32)
    node = helper.make_node(
        "Constant", inputs=[], outputs=["output0"],
        value=numpy_helper.from_array(constant, name="det"),
    )
    graph = helper.make_graph(
        [node], "stub_detector",
        inputs=[helper.make_tensor_value_info("images", TensorProto.FLOAT, [1, 3, 640, 640])],
        outputs=[helper.make_tensor_value_info("output0", TensorProto.FLOAT, [1, 6, 1])],
    )
    model = helper.make_model(graph, opset_imports=[helper.make_operatorsetid("", 12)])
    model.ir_version = 8

    meta = model.metadata_props.add()
    meta.key, meta.value = "names", "{0: 'red_box', 1: 'blue_box'}"

    path = tmp_path / "objects.onnx"
    onnx.save(model, str(path))

    from aegis.perception.objects import OnnxObjectDetector
    detector = OnnxObjectDetector(path, confidence=0.4)

    assert detector.available
    assert detector.labels == ["red_box", "blue_box"]

    # A 1280x720 frame letterboxes with scale 0.5 and 140px of vertical padding,
    # so network y=320 maps to source y=(320-140)/0.5 = 360 -- the frame centre.
    detections = detector.detect(np.zeros((720, 1280, 3), dtype=np.uint8))

    assert len(detections) == 1
    assert detections[0].label == "red_box"
    assert detections[0].confidence == pytest.approx(0.9, abs=0.01)
    cx = (detections[0].box[0] + detections[0].box[2]) / 2
    cy = (detections[0].box[1] + detections[0].box[3]) / 2
    assert cx == pytest.approx(640.0, abs=2.0)
    assert cy == pytest.approx(360.0, abs=2.0)
    assert detector.stats()["inferences"] == 1


def test_detections_flow_through_the_tracker_into_confirmed_tracks():
    """The contract between detector and tracker, exercised directly."""
    from aegis.perception.tracking import ObjectTracker

    tracker = ObjectTracker()
    for _ in range(4):
        tracker.update([Detection("red_box", 0.9, (100.0, 100.0, 200.0, 200.0))])

    confirmed = tracker.confirmed_tracks()
    assert len(confirmed) == 1
    assert confirmed[0].label == "red_box"


def test_tracks_survive_the_frames_between_detector_runs():
    """objects_interval > 1 feeds [] on skipped frames; tracks must not die."""
    from aegis.perception.tracking import ObjectTracker

    tracker = ObjectTracker()
    detection = Detection("red_box", 0.9, (100.0, 100.0, 200.0, 200.0))
    for _ in range(4):
        tracker.update([detection])

    for _ in range(3):                     # three skipped frames
        tracker.update([])

    assert len(tracker.confirmed_tracks()) == 1
