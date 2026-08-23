"""Documentation constants for the future custom tool-detection training dataset."""

from __future__ import annotations

from pathlib import Path

DATASET_ROOT = Path("data/tool_detection")
EXPECTED_LAYOUT = """data/tool_detection/
├── images/train, images/val
├── labels/train, labels/val
└── data.yaml
"""
DATA_YAML_TEMPLATE = """path: data/tool_detection
train: images/train
val: images/val
names:
  0: sample_vial
  1: reagent_pipette
  2: rack_holder
  3: centrifuge_slot
  4: centrifuge_lid
  # astronaut_hand is handled by MediaPipe; include it only if YOLO hand fallback is desired.
  5: astronaut_hand
"""
ROTATION_DEGREES = 360
OBJECT_CLASSES = (
    "sample_vial",
    "reagent_pipette",
    "rack_holder",
    "centrifuge_slot",
    "centrifuge_lid",
    "astronaut_hand",
)
