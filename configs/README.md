# Configuration

All settings are loaded once when the offline pipeline starts.

- `protocol.yaml` contains ordered `steps`. Each step requires a stable `id`, human-readable `name`, one or more `expects` values in the form `object_class:interaction`, a positive `timeout_s`, and `safety_critical` status. `debounce_frames`, `pending_window_s`, and `lookback_window_s` tune confirmation and fault tolerance.
- `hardware.yaml` is reserved for the local camera, inference device, and encoder selection.
- `app.yaml` selects a local model and camera/video source plus local logging, recording, streaming, and TTS values.

`pipeline.backend` accepts `tensorrt` (the fastest option on the target RTX 4060) or `onnx` (a more portable but usually slower option). `adaptive_frame_skip` is `1` by default; higher values reuse the prior tracked detections between inference frames and should be benchmarked against real footage.

TensorRT engines are fastest but GPU- and build-specific. An ONNX Runtime backend remains a planned portability path for other edge hardware; it will be slower but can avoid TensorRT's GPU coupling.

## Mock biological-fluid-analysis protocol

`protocol.yaml` now encodes the supplied mock procedure: retrieve the sample vial,
retrieve the pipette, inject reagent, stow the pipette, load the centrifuge, and
secure its lid. Its event strings are relational rather than position-based:

- `sample_vial:removed_from_rack`
- `reagent_pipette:grasp`
- `reagent_pipette+sample_vial:overlap_2s`
- `reagent_pipette:stowed_in_rack`
- `sample_vial:inside_centrifuge_slot`
- `centrifuge_lid:closed_over_centrifuge_slot`

The configured safety alerts cover attempted centrifuge loading before reagent
injection and a lid-close observation when no vial has been loaded.
