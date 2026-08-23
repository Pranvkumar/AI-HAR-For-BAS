"""Documentation constants for the future custom tool-detection training dataset."""

from __future__ import annotations

from pathlib import Path

DATASET_ROOT = Path("data/sih_box_experiment")
EXPECTED_LAYOUT = """data/sih_box_experiment/
├── images/train, images/val
├── labels/train, labels/val
└── data.yaml
"""
DATA_YAML_TEMPLATE = """path: data/sih_box_experiment
train: images/train
val: images/val
names:
  0: outer_container
  1: red_box
  2: second_colored_box
  # astronaut_hand is handled by MediaPipe; include it only if YOLO hand fallback is desired.
  3: astronaut_hand
"""
ROTATION_DEGREES = 360
OBJECT_CLASSES = (
    "outer_container",
    "red_box",
    "second_colored_box",
    "astronaut_hand",
)
