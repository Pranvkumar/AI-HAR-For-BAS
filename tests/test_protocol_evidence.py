"""Tests for relational biological-fluid-analysis evidence inference."""

from har.events import Detection, InteractionEvent
from har.fusion.protocol_evidence import ProtocolEvidenceEngine


def detection(cls: str, xyxy: tuple[float, float, float, float]) -> Detection:
    return Detection(cls, 0.9, xyxy, 1)


def test_injection_requires_two_seconds_of_relational_overlap() -> None:
    engine = ProtocolEvidenceEngine(injection_dwell_s=2.0)
    frame = [detection("sample_vial", (20, 20, 100, 100)), detection("reagent_pipette", (40, 40, 80, 80))]
    assert not engine.process(frame, [], 0.0)
    events = engine.process(frame, [], 2.1)
    assert any(item.evidence == "reagent_pipette+sample_vial:overlap_2s" for item in events)


def test_lid_closure_without_loaded_vial_emits_empty_anomaly_evidence() -> None:
    engine = ProtocolEvidenceEngine()
    events = engine.process([detection("centrifuge_slot", (10, 10, 100, 100)), detection("centrifuge_lid", (20, 20, 90, 90))], [], 0.0)
    assert any(item.evidence == "centrifuge_lid:closed_empty" for item in events)
