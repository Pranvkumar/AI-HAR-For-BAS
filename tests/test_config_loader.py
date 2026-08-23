from har.config.loader import load_protocol


def test_protocol_yaml_is_typed_and_config_driven():
    protocol = load_protocol("configs/protocol.yaml")
    assert protocol.steps[0].expects["object"] == "vial_A"
    assert protocol.steps[1].safety_critical is True
