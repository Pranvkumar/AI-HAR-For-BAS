from har.config.loader import ProtocolConfig, ProtocolStep
from har.fsm.protocol_fsm import ProtocolFSM, ViolationEvent
from har.fusion.interaction_engine import InteractionEvent


def event(object_name, state, timestamp, confidence=0.9):
    return InteractionEvent("right", object_name, 1, state, timestamp, confidence, 0.2)


def protocol(safety=False):
    return ProtocolConfig(
        [
            ProtocolStep(1, "pick", {"object": "vial", "state": "grasp_start"}, 10),
            ProtocolStep(
                2, "attach", {"object": "slot", "state": "contact"}, 10, safety
            ),
            ProtocolStep(3, "seal", {"object": "cap", "state": "contact"}, 10),
        ],
        debounce_frames=2,
        lookback_window_s=5,
    )


def test_normal_in_order_completion():
    machine = ProtocolFSM(protocol())
    assert machine.process(event("vial", "grasp_start", 1)) == []
    result = machine.process(event("vial", "grasp_start", 2))
    assert machine.completed == [1]
    assert result[0].step_id == 1


def test_lookahead_backfills_missed_middle_step():
    machine = ProtocolFSM(protocol())
    machine.process(event("vial", "grasp_start", 1))
    machine.process(event("vial", "grasp_start", 2))
    machine.process(event("slot", "contact", 3))
    result = machine.process(event("cap", "contact", 4))
    assert machine.completed == [1, 2, 3]
    assert "look-ahead" in result[0].message


def test_unconfirmed_safety_step_blocks_on_later_evidence():
    machine = ProtocolFSM(protocol(safety=True))
    machine.process(event("vial", "grasp_start", 1))
    machine.process(event("vial", "grasp_start", 2))
    result = machine.process(event("cap", "contact", 3))
    assert isinstance(result[0], ViolationEvent)
    assert result[0].blocked is True
    assert machine.state == "BLOCKED"


def test_debounce_absorbs_flicker():
    machine = ProtocolFSM(protocol())
    assert machine.process(event("vial", "grasp_start", 1)) == []
    assert machine.process(event("vial", "open", 1.1)) == []
    assert machine.process(event("vial", "grasp_start", 1.2)) == []
    assert machine.completed == []


def microgravity_protocol():
    return ProtocolConfig(
        [
            ProtocolStep(
                1,
                "open",
                {"object": "container_lid", "state": "contact"},
                20,
                False,
                ("red_box", "blue_box"),
                "Warning: State mismatch. Please ensure the main container is fully open.",
            ),
            ProtocolStep(
                2,
                "red",
                {"object": "red_box_pair", "state": "contact"},
                45,
                False,
                ("blue_box", "blue_box_stack"),
                "Warning: Sequence violation. Please extract and place both red boxes first.",
            ),
            ProtocolStep(
                3,
                "blue",
                {"object": "blue_box_stack", "state": "contact"},
                45,
                True,
                ("blue_box",),
                "Warning: Spatial error. The blue box must be stacked directly on top of the red box.",
            ),
            ProtocolStep(
                4,
                "close",
                {"object": "container_lid", "state": "contact"},
                20,
            ),
        ],
        debounce_frames=1,
        lookback_window_s=5,
    )


def test_sequence_error_blue_before_red_boxes():
    machine = ProtocolFSM(microgravity_protocol())
    machine.process(event("container_lid", "contact", 1.0))
    result = machine.process(event("blue_box", "grasp_start", 2.0))
    assert isinstance(result[0], ViolationEvent)
    assert (
        result[0].message
        == "Warning: Sequence violation. Please extract and place both red boxes first."
    )


def test_spatial_error_blue_not_stacked():
    machine = ProtocolFSM(microgravity_protocol())
    machine.process(event("container_lid", "contact", 1.0))
    machine.process(event("red_box_pair", "contact", 2.0))
    result = machine.process(event("blue_box", "contact", 3.0))
    assert isinstance(result[0], ViolationEvent)
    assert (
        result[0].message
        == "Warning: Spatial error. The blue box must be stacked directly on top of the red box."
    )


def test_state_error_extract_before_lid_open():
    machine = ProtocolFSM(microgravity_protocol())
    result = machine.process(event("red_box", "grasp_start", 1.0))
    assert isinstance(result[0], ViolationEvent)
    assert (
        result[0].message
        == "Warning: State mismatch. Please ensure the main container is fully open."
    )
