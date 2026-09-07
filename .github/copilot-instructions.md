# Copilot Instructions — AI HAR for Astronaut BAS Experiments

## Project summary

Build an offline, edge-deployed Human Activity Recognition system that observes astronaut scientific experiments through a fixed payload camera, tracks protocol steps, provides next-step guidance and spoken alerts, records structured telemetry, and supports local video streaming and monitoring. The demonstration target is a Lenovo Legion laptop with an NVIDIA RTX 4060 (8 GB VRAM, NVENC); the model layer must remain portable for future space-grade edge hardware.

## Hard constraints

- The runtime must be fully offline: no external APIs, cloud telemetry, or runtime model downloads. Models are acquired and pinned during a build/deployment step.
- Never make an up/down, gravity, surface, or absolute-position assumption. Interaction reasoning must use relational hand-to-object signals only.
- Load no more than one YOLO/TensorRT engine in a process. MediaPipe and TTS are CPU only and must not introduce a GPU dependency.
- The vision loop must not block on TTS, file writes, or streaming. Those operations use queues and dedicated worker threads.
- Protocol steps, expected actions, timeouts, and safety-critical status are YAML configuration, never Python constants.

## Required technology choices

- Ultralytics YOLOv11 (n or s), TensorRT FP16 when available, and ByteTrack or BoT-SORT through `model.track()` for tool detection and tracking.
- MediaPipe Holistic on CPU for hand/body tracking.
- `transitions` for the config-driven finite-state machine.
- Offline CPU TTS using pyttsx3 or Piper.
- OpenCV for frames and overlays; prefer NVENC-backed FFmpeg/GStreamer encoding with a `cv2.VideoWriter` fallback.
- FastAPI MJPEG streaming and Streamlit for the monitoring dashboard unless the project owner explicitly requests an alternative.
- Append-only JSON Lines telemetry using `logging` and `json`.

## Coding conventions

- Use Python 3.10+, type hints on all function signatures, and Black formatting.
- The pipeline has one thread per stage, connected by `queue.Queue`; raw frames use a max-size-two, drop-oldest queue.
- Cross-thread messages are typed dataclasses or Pydantic models, never raw dicts.
- Load configuration once at startup from `configs/*.yaml`; do not reload it unless hot reload is an explicit feature.
- Do not use bare `except`. Log frame ID, timestamp, and stage for caught vision errors, and allow an individual-frame failure without crashing the process.
- Unit-test fusion and FSM behavior with synthetic or recorded event sequences, never requiring a live camera.
- Keep accelerator-specific code behind thin interfaces.

## Completion expectations

New work must run without a GPU by gracefully using CPU YOLO and `cv2.VideoWriter`, include relevant passing tests, document new configuration keys in `configs/README.md`, and avoid secrets or hard-coded paths outside configuration.
