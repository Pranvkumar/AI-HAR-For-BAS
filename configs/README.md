# Configuration

`protocol.yaml` defines ordered experiment steps. Each `expects` mapping is
matched against relational interaction event fields such as `object` and
`state`; no absolute position is used. `debounce_frames` controls consecutive
matching events, `pending_window_s` is reserved for ambiguous evidence, and
`lookback_window_s` bounds retroactive step recovery.

`hardware.yaml` supports `yolo_backend` values `auto`, TensorRT, or portable
ONNX weights. TensorRT is faster but GPU/build-specific; ONNX Runtime is
portable but slower. `frame_skip_enabled` and `frame_skip` enable optional
linear bbox interpolation. Use `--int8 --calibration-data <data.yaml>` with
`scripts/export_engine.py` to build a calibrated INT8 engine.
