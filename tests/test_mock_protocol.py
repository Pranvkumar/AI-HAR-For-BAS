"""Safety-alert tests retained for the earlier biological-fluid mock protocol."""

from har.config.loader import load_protocol
from har.events import InteractionEvent, ViolationEvent
from har.fsm.protocol_fsm import ProtocolFSM


def observed(timestamp_s: float, evidence: str) -> InteractionEvent:
    object_class, interaction = evidence.split(":", 1)
    return InteractionEvent(timestamp_s, "left", object_class, 1, interaction, False, 0.5)


def test_centrifuge_before_injection_uses_configured_warning() -> None:
    fsm = ProtocolFSM(load_protocol("configs/mock_biological_fluid_protocol.yaml"))
    emitted = fsm.handle(observed(1.0, "sample_vial:inside_centrifuge_slot"))
    assert isinstance(emitted[0], ViolationEvent)
    assert emitted[0].short_message == "Inject reagent before centrifuging."
    assert fsm.blocked


def test_empty_centrifuge_lid_warning_is_explicit() -> None:
    fsm = ProtocolFSM(load_protocol("configs/mock_biological_fluid_protocol.yaml"))
    emitted = fsm.handle(observed(1.0, "centrifuge_lid:closed_empty"))
    assert isinstance(emitted[0], ViolationEvent)
    assert "Centrifuge is empty" in emitted[0].message
