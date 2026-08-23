# GitHub Copilot Agent Prompt — AI HAR System (Problem Statement 26174)

**How to use this doc:**
- Paste the **"KICKOFF PROMPT"** block below as-is into Copilot's agent/auto mode (or as a repo issue assigned to the Copilot coding agent) to start the build.
- Save the **"REPO GUIDELINES"** section as `.github/copilot-instructions.md` in your repo — Copilot automatically reads this file and applies it to every subsequent task/session, so you don't have to repeat constraints each time.
- Work through **PHASE 1 → 4** as separate follow-up prompts (also included below individually) rather than dumping all four into one session — agent mode is far more reliable when given one scoped, checkable task at a time.

---

## `.github/copilot-instructions.md` — REPO GUIDELINES
*(Save this file at this exact path in the repo root before running any agent task. Copilot picks it up automatically.)*

```markdown
# Copilot Instructions — AI HAR (Human Activity Recognition) for Astronaut BAS Experiments

## Project summary
Offline, edge-deployed AI system that watches an astronaut perform a scientific
experiment via a fixed payload camera, tracks procedure steps via computer vision,
gives next-step guidance and spoken alerts for skipped/out-of-order steps, logs a
structured timestamped record, records/streams video, and shows a live monitoring UI.
Demo hardware: Lenovo Legion laptop, NVIDIA RTX 4060, 8GB VRAM, NVENC.
Eventually re-targeted to space-grade edge hardware — keep the model layer portable.

## Hard constraints (do not violate)
- 100% offline. No calls to any external API/service at runtime. No telemetry phoned
  home. No cloud model downloads at runtime (models are fetched/pinned at build time only).
- No fixed "up"/"down" assumption anywhere in the code. Never write logic that depends
  on absolute object position, gravity, or a surface an object "rests on." All
  interaction logic must be relational (hand-to-object distance/contact only).
- Target hardware has 8GB VRAM shared across YOLO inference + video encode. Never load
  more than one instance of the YOLO/TensorRT engine in the process. MediaPipe and TTS
  must run on CPU, not GPU — do not introduce a GPU dependency for either.
- Nothing may block the main vision loop. TTS calls, file writes, and network streaming
  must go through queues/worker threads — never call them synchronously from the
  frame-processing loop.
- The experiment protocol (steps, expected tool/action per step, timeouts, which steps
  are safety-critical) is config-driven (YAML), never hardcoded in Python.

## Tech stack (use these, don't substitute without asking)
- Object/tool detection: Ultralytics YOLOv11 (n or s), exported to TensorRT (fp16) for
  inference; ByteTrack/BoT-SORT for multi-object tracking (via `model.track()`).
- Hand/body tracking: MediaPipe Holistic, CPU delegate.
- FSM: `transitions` library (Python), config-driven from a YAML protocol schema.
- TTS: `pyttsx3` or `Piper` (CPU-only, offline).
- Video: OpenCV for frame handling/overlay; prefer an NVENC-backed encode path
  (`h264_nvenc` via GStreamer/FFmpeg) over CPU x264 where available, with a
  `cv2.VideoWriter` fallback if NVENC isn't present.
- Streaming: FastAPI (MJPEG `StreamingResponse`) as the default; MediaMTX (RTSP) is an
  acceptable alternative if asked for explicitly.
- GUI: Streamlit for the fastest path; a React+FastAPI dashboard only if explicitly requested.
- Telemetry: `logging` + `json`, append-only JSON Lines (`.jsonl`).

## Coding conventions
- Python 3.10+, type hints on all function signatures, `black`-formatted.
- Threading model: one thread per pipeline stage (ingestion, YOLO inference, MediaPipe
  inference, fusion, FSM, each output sink) connected via `queue.Queue`. Use
  `maxsize=2` with drop-oldest semantics on the raw-frame queue specifically.
- Every cross-thread event is a small typed object (dataclass or pydantic model), not
  a raw dict, e.g. `InteractionEvent`, `FSMTransitionEvent`, `ViolationEvent`.
- Config lives in `configs/*.yaml`, loaded once at startup, never re-read mid-run
  except where hot-reload is explicitly built as a feature.
- No bare `except:`. Log full context (frame id, timestamp, stage) on every caught
  exception in the vision pipeline; a single frame failure must never crash the process.
- Write unit tests for the FSM and fusion/interaction logic using recorded/synthetic
  event sequences (no live camera required to run these tests).
- Keep GPU-specific code (TensorRT engine loading, NVENC pipeline) isolated behind a
  thin interface so it can later be swapped for a different accelerator backend without
  touching the rest of the pipeline.

## Definition of done for any task
1. Code runs standalone (`python -m ...` or documented entry point) without errors on
   a machine with no GPU present, falling back gracefully (CPU YOLO / cv2.VideoWriter)
   — GPU accel is an optimization, not a hard runtime requirement for correctness.
2. Relevant unit tests pass (`pytest`).
3. New/changed config keys are documented in `configs/README.md`.
4. No secrets, API keys, or hardcoded file paths outside `configs/`.
```

---

## KICKOFF PROMPT (paste this into Copilot agent/auto mode first)

```
You are building an offline AI Human Activity Recognition (HAR) system for
astronauts performing scientific experiments in microgravity (Problem Statement
26174). Full project context and constraints are in `.github/copilot-instructions.md`
— read it fully before writing any code, and follow it for every file you create.

Right now, only set up the project skeleton. Do not implement pipeline logic yet.

Tasks:
1. Initialize a Python project (pyproject.toml, src-layout: `src/har/`).
2. Create this package structure with empty `__init__.py` files and one-line module
   docstrings describing each module's future responsibility:
   src/har/ingestion/      # camera frame capture thread
   src/har/vision/         # YOLO + MediaPipe wrappers
   src/har/fusion/         # hand-object interaction heuristics
   src/har/fsm/            # transitions-based state machine
   src/har/outputs/        # tts/, telemetry/, video/, stream/, gui/
   src/har/config/         # YAML loading + schema validation (pydantic)
   configs/                # protocol.yaml, hardware.yaml, app.yaml (placeholders)
   tests/
3. Add `pyproject.toml` with dependencies: ultralytics, mediapipe, transitions,
   pyttsx3, opencv-python, fastapi, uvicorn, streamlit, pydantic, pytest, black.
   Pin approximate major versions; note in a comment that exact pins should be
   finalized after Phase 1 model export testing.
4. Add a `configs/protocol.yaml` placeholder matching the schema described in
   copilot-instructions.md (steps list with id/name/expects/timeout_s/safety_critical).
5. Add a root `README.md` summarizing the project, hardware target, and how to run
   `pytest` — no implementation details yet, just orientation for a new contributor.
6. Add a `.gitignore` appropriate for Python + model weights (*.pt, *.engine, *.onnx,
   *.mp4 outputs, __pycache__, .venv).

Do not install packages or run training. Do not write pipeline logic. Stop after the
skeleton is created and summarize what you created and why, then wait for the next task.
```

---

## PHASE 1 PROMPT — Data Collection & Model Training

```
Context: read .github/copilot-instructions.md if you haven't already this session.

Goal: get a trained, exported YOLOv11n tool-detection model ready for the vision
pipeline. Do not touch FSM, fusion, or output modules in this task.

Tasks:
1. In `src/har/vision/`, add a `train_config.py` documenting (as constants/comments,
   not executed training code) the expected dataset structure Ultralytics needs
   (images/, labels/, data.yaml) for our custom tool/object classes — leave class
   names as a TODO list for me to fill in.
2. Add `scripts/export_engine.py`: a CLI script that takes a trained `best.pt`,
   exports to ONNX, then to a TensorRT engine (fp16) via `trtexec`/ultralytics export
   API, saving to `models/exported/`. Include a `--int8` flag stubbed out for later
   calibration but not implemented yet.
3. Add `scripts/augment_check.py`: a small utility that loads a sample image and
   visualizes rotation augmentation (0-360°, not just small-angle jitter) so I can
   sanity-check the augmentation config before a full training run — this matters
   because objects have no fixed orientation in microgravity.
4. Add `src/har/vision/yolo_wrapper.py`: a class `YoloDetector` that loads a given
   engine/weights path, exposes `detect(frame) -> list[Detection]` where `Detection`
   is a dataclass (cls, conf, xyxy, track_id). Use `model.track()` with
   ByteTrack/BoT-SORT for the track_id, not per-frame-only detection. Fall back to
   plain `.pt` CPU inference if no `.engine` file is found (log a warning, don't crash).
5. Write `tests/test_yolo_wrapper.py` using a tiny stock pretrained YOLO model and a
   sample image (not our custom-trained one) just to verify the wrapper's interface
   and fallback logic work — this doesn't need our real trained weights.

Definition of done: `pytest tests/test_yolo_wrapper.py` passes without a GPU present
(falls back to CPU .pt inference). Summarize what's left as manual work for me (the
actual data collection and training run itself, which needs a human in the loop).
```

---

## PHASE 2 PROMPT — Vision & FSM Integration

```
Context: read .github/copilot-instructions.md. YoloDetector from Phase 1 already
exists in src/har/vision/yolo_wrapper.py — reuse it, don't reimplement.

Goal: build the MediaPipe wrapper, the fusion/interaction engine, and the FSM,
wired together and testable via recorded event replay (no live camera needed).

Tasks:
1. `src/har/vision/mediapipe_wrapper.py`: class `HandTracker` wrapping MediaPipe
   Holistic (CPU delegate explicitly set), exposing `track(frame) -> HandState` with
   per-hand landmark list + visibility scores. No GPU usage anywhere in this file.
2. `src/har/fusion/interaction_engine.py`: given a `HandState` and a list of
   `Detection`s from the same (or closest-timestamp, within an 80ms tolerance)
   frame, compute:
   - hand-object IoU/containment
   - grasp state via thumb-tip/index-tip distance vs. a configurable threshold
   Emit an `InteractionEvent` dataclass ONLY on state change (not every frame).
   Do not use any absolute position or "resting on surface" logic anywhere here.
3. `src/har/fsm/protocol_fsm.py`: build the FSM with the `transitions` library,
   driven by `configs/protocol.yaml`. Implement fault tolerance as first-class
   behavior, not an afterthought:
   - debounce: require N consecutive confirming events (config: `debounce_frames`)
   - a `PENDING_CONFIRMATION` meta-state buffering ambiguous events for
     `pending_window_s` seconds before committing
   - look-ahead/retroactive completion: if evidence for step N+2 arrives while
     still on step N, check a rolling buffer (`lookback_window_s`) for weaker
     evidence of step N+1 before raising a violation
   - violations on non-`safety_critical` steps are logged + emit a `ViolationEvent`
     but do NOT block the FSM from continuing; `safety_critical: true` steps do block
4. `tests/test_fusion_and_fsm.py`: write tests using synthetic/recorded
   `InteractionEvent` sequences (author them by hand in the test file, no camera
   needed) covering: normal in-order completion, a single missed step that gets
   retroactively backfilled, a genuinely skipped safety-critical step (should block),
   and noisy flicker that debounce should absorb.

Definition of done: all fusion/FSM tests pass with no camera or trained model
required. Report any places you had to guess at a threshold/config value so I can
tune them against real footage later.
```

---

## PHASE 3 PROMPT — Telemetry, Video Streaming & UI

```
Context: read .github/copilot-instructions.md. FSM emits FSMTransitionEvent and
ViolationEvent objects from Phase 2 — subscribe to those, don't modify the FSM here.

Goal: wire up all output sinks as independent, non-blocking consumers.

Tasks:
1. `src/har/outputs/telemetry.py`: `TelemetryLogger` that appends one JSON line per
   FSM event to a timestamped `.jsonl` file under `logs/`. Must be safe to call from
   a worker thread; use a queue + dedicated writer thread, not direct file I/O from
   multiple threads.
2. `src/har/outputs/tts.py`: `TTSWorker` running pyttsx3 (default) with a Piper
   backend option behind a config flag, consuming an `alert_queue.Queue` on its own
   thread so it never blocks the FSM/vision loop. Keep spoken strings short
   (pull a `short_message` field from the event, separate from the full log message).
3. `src/har/outputs/video.py`: `VideoRecorder` that draws bbox + FSM-state overlays
   on frames and writes to a local `.mp4`. Attempt an NVENC (`h264_nvenc` via
   GStreamer/FFmpeg subprocess pipe) path first; fall back to `cv2.VideoWriter`
   (mp4v) with a logged warning if NVENC isn't available. Reuse the exact same
   annotated frame for the streaming sink below — do not re-render twice.
4. `src/har/outputs/stream.py`: FastAPI app exposing a `/stream` MJPEG
   `StreamingResponse` endpoint fed by the same annotated-frame queue as `video.py`.
5. `src/har/outputs/gui/dashboard.py`: a Streamlit app showing current step,
   confidence, a scrolling violation feed (tailing the `.jsonl` telemetry file), and
   the embedded MJPEG stream.
6. `src/har/pipeline.py`: the orchestrator that wires ingestion → vision → fusion →
   FSM → all output sinks via queues, matching the threading model in
   copilot-instructions.md exactly (drop-oldest raw frame queue, one thread per stage).
7. `tests/test_outputs.py`: test TelemetryLogger and TTSWorker in isolation by
   feeding synthetic events into their queues and asserting file/queue behavior
   (mock the actual TTS engine call and file paths — no audio hardware or real
   camera needed for these tests).

Definition of done: `python -m har.pipeline --config configs/app.yaml` runs
end-to-end against a webcam or a sample video file, produces a growing `.jsonl` log,
writes an `.mp4`, and serves `/stream`; the Streamlit dashboard renders it live.
```

---

## PHASE 4 PROMPT — Optimization

```
Context: read .github/copilot-instructions.md. Full pipeline from Phase 3 exists
and runs end-to-end — this task is optimization only, no new features.

Tasks:
1. Add `scripts/benchmark_pipeline.py`: runs the full pipeline against a fixed
   sample video for N seconds with all five output sinks active simultaneously,
   logging per-stage timing (ingestion, YOLO, MediaPipe, fusion, FSM, each output)
   and overall FPS, plus a note to run `nvidia-smi dmon` alongside manually.
2. Add an adaptive frame-skip option to `src/har/vision/yolo_wrapper.py`
   (config-gated, default off): run YOLO every Kth frame, interpolate bboxes for
   skipped frames via a simple Kalman filter / linear extrapolation on track
   centroids. Do not change default behavior unless the config flag is set.
3. Add INT8 calibration support to `scripts/export_engine.py` (implement the
   `--int8` stub from Phase 1) using a small calibration image set path from config.
4. Add a config flag to switch the YOLO backend between TensorRT and plain ONNX
   Runtime, so the model layer isn't hard-locked to TensorRT — this is specifically
   to keep a path open for porting to different edge hardware later. Document the
   tradeoff (TensorRT = fastest but GPU/build-specific; ONNX Runtime = portable but
   slower) in `configs/README.md`.
5. Update `tests/test_yolo_wrapper.py` to cover both backends.

Definition of done: benchmark script produces a report showing FPS with all sinks
active; document the achieved FPS and any bottleneck found in `docs/benchmark_notes.md`.
```
