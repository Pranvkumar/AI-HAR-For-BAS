# Configuration

All settings are loaded once when the offline pipeline starts.

- `protocol.yaml` contains ordered `steps`. Each step requires a stable `id`, human-readable `name`, one or more `expects` values in the form `object_class:interaction`, a positive `timeout_s`, and `safety_critical` status. `debounce_frames`, `pending_window_s`, and `lookback_window_s` tune confirmation and fault tolerance.
- `hardware.yaml` is reserved for the local camera, inference device, and encoder selection.
- `app.yaml` selects a local model and camera/video source plus local logging, recording, streaming, and TTS values.

`pipeline.backend` accepts `tensorrt` (the fastest option on the target RTX 4060) or `onnx` (a more portable but usually slower option). `adaptive_frame_skip` is `1` by default; higher values reuse the prior tracked detections between inference frames and should be benchmarked against real footage.

### Hand gestures

`pipeline.gestures.model_path` points to the locally stored MediaPipe Gesture
Recognizer task model, and `num_hands` controls whether one or two hands are
tracked. The same CPU-only MediaPipe task supplies the 21-point hand landmarks
used for hand-object contact and its gesture categories for the live overlay.
`Closed_Fist` can reinforce a landmark-based grasp only when the hand overlaps
a detected object. Gesture labels by themselves never advance protocol steps or
override a safety-critical violation.

TensorRT engines are fastest but GPU- and build-specific. An ONNX Runtime backend remains a planned portability path for other edge hardware; it will be slower but can avoid TensorRT's GPU coupling.

## SIH visible-box baseline

`protocol.yaml` is the active SIH baseline. It is based only on the visible part
of the official statement: an outer box holding a red smaller box and another
coloured smaller box. The unseen second colour is deliberately represented as
`second_colored_box`, so it can be renamed without code changes.

- `red_box:removed_from_outer_container`
- `second_colored_box:removed_from_outer_container`
- `red_box:returned_to_outer_container`
- `second_colored_box:returned_to_outer_container`

The box evidence engine derives these events only from object containment plus
hand grasp/release evidence. It makes no assumption about up/down, gravity, or
a surface. The biology mock remains available in
`mock_biological_fluid_protocol.yaml` as a non-active engineering reference.
