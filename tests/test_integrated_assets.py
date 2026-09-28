"""Verify that the checked-in experiment and offline voice assets are wired."""

from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]


def test_red_box_protocol_and_data_are_present() -> None:
    config = yaml.safe_load((ROOT / "configs" / "app.yaml").read_text(encoding="utf-8"))
    protocol = yaml.safe_load((ROOT / "configs" / "protocol.yaml").read_text(encoding="utf-8"))

    assert config["protocol_path"] == "configs/protocol.yaml"
    assert [step["action"] for step in protocol["steps"]] == [
        "retrieve_red_box",
        "retrieve_second_colored_box",
        "return_red_box",
        "return_second_colored_box",
    ]
    assert (ROOT / "data" / "sih_box_experiment").is_dir()
    assert (ROOT / "datasets" / "red_blue_synth").is_dir()


def test_bundled_voice_model_is_complete() -> None:
    voice_dir = ROOT / "models" / "voice"

    assert (voice_dir / "model.bin").is_file()
    assert (voice_dir / "config.json").is_file()
    assert (voice_dir / "tokenizer.json").is_file()
    assert (voice_dir / "vocabulary.txt").is_file()