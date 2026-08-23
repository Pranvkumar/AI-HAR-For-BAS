# AI-HAR-For-BAS

An offline edge assistant that uses computer vision to track, validate, and
provide guidance for astronaut science experiments in space. The target demo
hardware is a Lenovo Legion laptop with an RTX 4060 and NVENC; CPU fallbacks
keep development and tests possible without a GPU.

## Status

Phase 1 and Phase 2 are implemented: the project includes the Ultralytics
tracking adapter, training/export utilities, CPU MediaPipe adapter, relational
hand-object fusion, YAML protocol loading, and a fault-tolerant protocol FSM.

## Development

```bash
python -m pip install -e '.[dev]'
pytest
```

Tests use synthetic events and do not download weights or require a camera.
Provide a trained `.pt` or TensorRT `.engine` path when using
`har.vision.yolo_wrapper.YoloDetector` in a live environment.
