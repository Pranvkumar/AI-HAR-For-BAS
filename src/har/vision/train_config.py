"""Dataset notes for the Phase 1 Ultralytics training run."""

DATASET_LAYOUT = """
dataset/
  images/{train,val}/       # fixed-camera experiment frames
  labels/{train,val}/       # YOLO txt: class_id x_center y_center width height
  data.yaml                # path, train, val, and names
"""

# TODO: replace with the annotated BAS class names before training.
CLASS_NAMES: list[str] = []
ROTATION_AUGMENTATION_DEGREES = 360
