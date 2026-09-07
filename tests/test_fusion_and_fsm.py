"""Synthetic relational interaction and protocol fault-tolerance tests."""

from __future__ import annotations

from har.config.models import ProtocolConfig
from har.events import InteractionEvent, ViolationEvent
from har.fsm.protocol_fsm import ProtocolFSM
from har.fusion.interaction_engine import InteractionEngine
from har.events import Detection, HandLandmark, HandState
from har.vision.gesture_recognizer import RecognizedGesture


def event(time_s: float, evidence: str) -> InteractionEvent:
    object_class, interaction = evidence.split(":")
    return InteractionEvent(time_s, "left", object_class, 1, interaction, interaction == "grasp", 0.5)


def protocol() -> ProtocolConfig:
    return ProtocolConfig.model_validate({"debounce_frames": 2, "steps": [
        {"id": "a", "name": "A", "expects": ["a:grasp"], "timeout_s": 5, "safety_critical": False},
        {"id": "b", "name": "B", "expects": ["b:grasp"], "timeout_s": 5, "safety_critical": False},
        {"id": "c", "name": "C", "expects": ["c:grasp"], "timeout_s": 5, "safety_critical": True},
        {"id": "d", "name": "D", "expects": ["d:grasp"], "timeout_s": 5, "safety_critical": False},
    ]})


def test_normal_in_order_completion_and_debounce() -> None:
    fsm = ProtocolFSM(protocol())
    assert not fsm.handle(event(0, "a:grasp"))
    assert fsm.current_step == "PENDING_CONFIRMATION"
    fsm.handle(event(0.1, "a:grasp"))
    fsm.handle(event(0.2, "b:grasp")); fsm.handle(event(0.3, "b:grasp"))
    fsm.handle(event(0.4, "c:grasp")); fsm.handle(event(0.5, "c:grasp"))
    fsm.handle(event(0.6, "d:grasp")); fsm.handle(event(0.7, "d:grasp"))
    assert fsm.current_step == "COMPLETE"


def test_noncritical_skip_is_logged_without_blocking() -> None:
    fsm = ProtocolFSM(protocol())
    emitted = fsm.handle(event(0, "b:grasp"))
    assert isinstance(emitted[0], ViolationEvent)
    assert not fsm.blocked


def test_safety_critical_skip_blocks() -> None:
    fsm = ProtocolFSM(protocol())
    emitted = fsm.handle(event(0, "d:grasp"))
    assert isinstance(emitted[0], ViolationEvent)
    assert fsm.blocked


def test_retroactive_lookahead_backfills_middle_step() -> None:
    fsm = ProtocolFSM(protocol())
    fsm.handle(event(0, "a:grasp")); fsm.handle(event(0.1, "a:grasp"))
    fsm.handle(event(0.2, "c:grasp"))
    fsm.handle(event(0.3, "d:grasp"))
    assert fsm.current_step == "COMPLETE"


def test_closed_fist_gesture_reinforces_hand_object_grasp() -> None:
    landmarks = tuple(HandLandmark(0.1, 0.1) for _ in range(21))
    landmarks = landmarks[:4] + (HandLandmark(0.1, 0.1),) + landmarks[5:8] + (HandLandmark(0.9, 0.9),) + landmarks[9:]
    hand_state = HandState(1.0, {"left": landmarks, "right": ()})
    events = InteractionEngine().process(
        hand_state,
        [Detection("red_box", 0.9, (0, 0, 100, 100), 1)],
        (100, 100),
        [RecognizedGesture("Left", "Closed_Fist", 0.95)],
    )
    assert events[0].grasped
    assert events[0].interaction == "grasp"
