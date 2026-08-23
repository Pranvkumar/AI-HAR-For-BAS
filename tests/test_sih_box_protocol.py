"""Tests for the conservative SIH 26174 visible-box baseline."""

from har.config.loader import load_protocol
from har.events import InteractionEvent, ViolationEvent
from har.fsm.protocol_fsm import ProtocolFSM


def observed(timestamp_s: float, evidence: str) -> InteractionEvent:
    object_class, interaction = evidence.split(":", 1)
    return InteractionEvent(timestamp_s, "left", object_class, 1, interaction, False, 0.5)


def test_second_box_before_red_box_is_safety_violation() -> None:
    fsm = ProtocolFSM(load_protocol("configs/protocol.yaml"))
    emitted = fsm.handle(observed(1.0, "second_colored_box:removed_from_outer_container"))
    assert isinstance(emitted[0], ViolationEvent)
    assert emitted[0].safety_critical
    assert fsm.blocked
