# AI Human Activity Recognition (HAR) for On-board BAS Experiments
### Problem Statement 26174 — System Architecture, Improvements & Execution Plan
**Target demo hardware:** Lenovo Legion (RTX 4060, 8GB VRAM, NVENC) → later ported to space-grade edge hardware

---

## PART 1 — DETAILED SYSTEM ARCHITECTURE

### 1.0 High-Level Data Flow

```
┌─────────────┐    ┌──────────────────────┐    ┌────────────────────┐
│  Camera(s)  │───▶│  Frame Ingestion      │───▶│  Frame Queue (Q1)   │
│  (fixed rig)│    │  Thread (OpenCV)      │    │  maxsize=2, LIFO    │
└─────────────┘    └──────────────────────┘    └─────────┬──────────┘
                                                            │
                          ┌─────────────────────────────────┼─────────────────────────────────┐
                          ▼                                                                     ▼
              ┌────────────────────────┐                                        ┌────────────────────────┐
              │  YOLOv11n/s (TensorRT) │                                        │  MediaPipe Holistic     │
              │  GPU inference thread  │                                        │  CPU inference thread   │
              │  → tool/object bboxes  │                                        │  → 3D hand/pose keypts  │
              └───────────┬─────────────┘                                       └───────────┬────────────┘
                          └──────────────────────────┬──────────────────────────────────────┘
                                                       ▼
                                        ┌──────────────────────────────┐
                                        │  Fusion / Interaction Engine │
                                        │  (spatial heuristics)        │
                                        │  → symbolic events           │
                                        │  {hand, object, state, ts}   │
                                        └───────────────┬───────────────┘
                                                         ▼
                                        ┌──────────────────────────────┐
                                        │   FSM (transitions library)   │
                                        │   protocol.yaml → states      │
                                        │   → step status + violations  │
                                        └───────────────┬───────────────┘
                                                         ▼
                                ┌────────────────────────┼────────────────────────┐
                                ▼            ▼            ▼            ▼            ▼
                          ┌─────────┐  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐
                          │  TTS    │  │ Telemetry│ │  Video   │ │   IP     │ │   GUI    │
                          │pyttsx3/ │  │  JSONL   │ │ Writer   │ │  Stream  │ │Streamlit/│
                          │  Piper  │  │  logger  │ │(cv2/NVENC)│ │(FastAPI/ │ │  React   │
                          │         │  │          │ │  → .mp4  │ │ MediaMTX)│ │dashboard │
                          └─────────┘  └──────────┘ └──────────┘ └──────────┘ └──────────┘
```

Every arrow after the Fusion Engine is a **pub-sub event**, not a direct function call — this decoupling is what lets TTS, video, streaming, and the GUI run as independent consumers without blocking the vision loop.

### 1.1 Module 0 — Camera Frame Ingestion

- **Library:** `cv2.VideoCapture` (V4L2/MSMF backend), or `pyrealsense2` if a depth camera is added later for better occlusion handling.
- **Threading model:** dedicated thread, since `VideoCapture.read()` blocks. This thread does nothing but grab frames and push to a `queue.Queue(maxsize=2)`.
- **Critical detail:** use a **drop-oldest** policy, not a growing buffer. If inference falls behind, you want the *latest* frame, not a backlog — otherwise the system visibly lags behind real astronaut actions.
```python
if q.full():
    q.get_nowait()  # discard stale frame
q.put_nowait(frame)
```
- Output: raw BGR frame + monotonic timestamp (`time.monotonic()`, not wall-clock, to avoid NTP jump issues on an offline system).

### 1.2 Module 1 — Vision Pipeline

**1.2a Object/Tool Detection (YOLOv11n/s, TensorRT engine)**
- Runs in its own thread/process, pulls from Q1, outputs `[{cls, conf, xyxy, track_id}]`.
- Use **ByteTrack or BoT-SORT** (built into Ultralytics via `model.track()`) instead of raw per-frame detection — you need persistent object identity across frames for the FSM to reason about "the pipette that was just picked up," not just "a pipette."
- Fixed input size (e.g. 640×640) and fp16 precision for a stable TensorRT engine — see VRAM section below.

**1.2b Body/Hand Tracking (MediaPipe Holistic)**
- Runs on CPU (deliberately — frees the entire GPU for YOLO + NVENC). Outputs 21 hand landmarks per hand (x, y, z, visibility) plus pose landmarks for torso orientation.
- Since there's no fixed "up," pose landmarks matter less for gravity assumptions and more for **determining which astronaut is which** if two people are in frame, and for filtering false-positive hands (e.g. a hand shape printed on a checklist card).

**1.2c Synchronization**
- YOLO and MediaPipe run on the *same* frame reference (tagged by the ingestion timestamp) but don't need to finish in lockstep. Use a small **result cache keyed by frame_id**; the Fusion Engine consumes whichever pair of (YOLO, MediaPipe) results share the closest timestamp within a tolerance window (e.g. 80ms) — this decouples a fast CPU task from a slightly slower GPU task without forcing artificial sync barriers.

### 1.3 Module 2 — Fusion / Interaction Engine

This is where hand-object interaction is computed **without** heavy 3D mesh work, exactly as the stack specifies:

1. Compute a hand "occupancy region" — either a bounding box around the 21 landmarks, or (cheaper) just the fingertip cluster (thumb tip + index tip).
2. Compute IoU / containment between hand region and each YOLO tool bbox.
3. Compute **grasp state**: Euclidean distance between thumb-tip and index-tip landmarks (or thumb-tip to middle-finger-tip) below a calibrated threshold = "pinch/grasp"; above = "open hand."
4. Emit a symbolic event only on **state change** (not every frame) to keep the FSM event stream sparse and meaningful:
```json
{"hand": "right", "object": "pipette_A", "track_id": 14, "state": "grasp_start", "ts": 118423.552}
```

### 1.4 Module 3 — FSM (Python `transitions`)

- The experiment protocol is defined declaratively (YAML/JSON), not hardcoded — this is important for reusability across different BAS experiment types:
```yaml
steps:
  - id: 1
    name: "Retrieve sample vial"
    expects: {object: "vial_A", state: "grasp_start"}
    timeout_s: 30
  - id: 2
    name: "Attach vial to centrifuge"
    expects: {object: "centrifuge_slot", state: "contact"}
    timeout_s: 45
```
- `transitions.Machine` is instantiated with states = step IDs + terminal states (`COMPLETE`, `ABORTED`), and triggers driven by Fusion Engine events matched against `expects`.
- On each valid transition: telemetry event logged, GUI notified, TTS given a "next step" prompt.
- On a **mismatch** (wrong object grasped, or timeout exceeded): a violation event is raised → routed to TTS as a spoken alert and logged, but (see Part 2B) does **not** hard-block progression by default.

### 1.5 Module 4 — Output Layer

| Sink | Library | Behavior |
|---|---|---|
| TTS | `pyttsx3` (simplest, uses SAPI5/NSSpeech/espeak) or `Piper` (better offline voice quality, ONNX-based, fully local) | Runs its own worker thread consuming an `alert_queue`; never called synchronously from the FSM thread, since TTS engines can block for 1-2s |
| Telemetry | `logging` + `json` (JSON Lines format) | Append-only `.jsonl`, one structured record per event — trivial to replay or feed into a post-hoc mistake-detection analysis (PREGO-style) |
| Video storage | `cv2.VideoWriter` fed by annotated frames (bboxes + state overlay drawn via `cv2.rectangle`/`putText`) | Ideally piped through **GStreamer/FFmpeg with `h264_nvenc`** rather than raw `cv2.VideoWriter` (mp4v/XVID), since NVENC is a separate hardware block and won't compete with YOLO for CUDA cores |
| IP Stream | FastAPI `StreamingResponse` (MJPEG, simplest) or MediaMTX (RTSP, more standard/lower latency for a jury demo on a second screen) | Same annotated frame reused from the video-writer step — never re-render twice |
| GUI | Streamlit (fastest to build; polls telemetry file or a websocket) or a lightweight FastAPI + React dashboard (better for a live, low-latency checklist UI) | Displays: current step, live confidence, violation log, embedded MJPEG/RTSP view |

---

## PART 2 — ARCHITECTURE IMPROVEMENTS

### 2.A Microgravity Edge Cases

**Occlusions**
- Add a **Kalman filter or exponential moving average** on each tracked object's bbox center + hand landmark positions. When a tool is briefly occluded (astronaut's body passes in front), the tracker coasts on the predicted position for a short grace window instead of instantly reporting "object lost."
- Use MediaPipe's per-landmark **visibility/presence score** to *gate trust* — don't feed low-visibility landmarks into the grasp-distance calculation, or you'll get spurious grasp/release flicker.
- If budget allows a second camera angle later, do **late fusion**: only declare an object truly lost if *both* views lose it.

**Floating / drifting objects, no fixed orientation**
- This is the most important microgravity-specific decision: **do not use any gravity-relative heuristic** (e.g. "object resting on table," "object fell"). All interaction logic must be purely relational (hand-to-object distance/contact), which the spatial heuristic approach in 1.3 already satisfies — just be disciplined about never sneaking in an absolute-position assumption later.
- Train YOLO with **aggressive rotation augmentation** (full 0-360°, not just the ±15° default) since a tool can be presented to the camera at literally any orientation in microgravity. Also augment for objects appearing to "float" mid-frame rather than always being handled at a bench height.
- Use tracking (ByteTrack) rather than raw detection specifically because floating objects can drift out of frame and re-enter — a tracker with re-identification (appearance embedding, not just IoU-based association) recovers identity better than treating a re-entry as a brand-new object.

### 2.B FSM Fault Tolerance ("AI misses a step but the user continues")

This is a real risk with any perception-driven FSM, and a strict DFA will break immediately on a missed detection. Concrete mitigations:

1. **Debounce transitions:** require N consecutive confirming frames (e.g. 5 frames ≈ 150-200ms) before committing a state change, to avoid one noisy frame either creating or blocking a transition.
2. **Look-ahead / retroactive completion:** if the Fusion Engine reports strong evidence for step N+2's expected interaction while the FSM is still waiting on step N, don't immediately raise a hard violation. Instead, check a short rolling buffer (last ~5s of events) for weaker evidence of step N+1; if found, silently backfill N+1 as complete and advance. If not found, raise a **soft** (non-blocking) alert rather than halting.
3. **Non-blocking-by-default violations:** most experiment protocols shouldn't hard-stop on a suspected missed step — astronauts are following their own physical protocol regardless of what the camera thinks. Default behavior: log + speak a gentle correction ("Step 3 wasn't confirmed — continuing to track step 4"), and only hard-block for steps explicitly flagged `safety_critical: true` in the protocol YAML.
4. **Manual voice override:** add a small offline keyword-spotting layer (Vosk or Porcupine, both CPU-only and tiny) listening for a fixed phrase like *"confirm step"* / *"skip step."* This gives the astronaut a direct way to correct the FSM state without touching a keyboard — important since their hands are busy with the experiment.
5. **Ambiguous/pending meta-state:** instead of a binary confirmed/violated, add a third `PENDING_CONFIRMATION` state that buffers borderline-confidence events for ~2-3s before committing either way, cutting down false alarms without adding much perceived latency.

### 2.C VRAM Management on the RTX 4060 (8GB)

The stack is actually well-suited to 8GB if the workload is deliberately split across GPU compute, GPU fixed-function hardware, and CPU:

| Component | Where it runs | Approx. VRAM |
|---|---|---|
| YOLOv11n, TensorRT fp16, 640×640, batch=1 | GPU (CUDA cores) | ~300-500 MB |
| CUDA/TensorRT runtime context overhead | GPU | ~300-500 MB |
| MediaPipe Holistic | **CPU** (XNNPACK delegate) | 0 |
| pyttsx3 / Piper TTS | **CPU** (Piper uses ONNX Runtime CPU) | 0 |
| Video encode | **NVENC** (dedicated ASIC, separate from CUDA cores) | small fixed buffer, ~100-200 MB |

Practical rules to stay safely under 8GB with headroom for the demo laptop's OS/desktop overhead:
- **Never load two copies of the YOLO engine.** If both the live-inference thread and, say, a debug visualizer need it, share a single engine instance behind a lock, or run it via a single dedicated inference process with a request queue.
- Keep YOLO at **fp16**, not fp32; consider **INT8 with a small calibration set** in Phase 4 for further headroom if you later add a second model (e.g. a lightweight action-classification head).
- Route video encoding through **`h264_nvenc`** (FFmpeg/GStreamer) instead of CPU x264 — this both frees CPU cycles for MediaPipe/TTS and avoids the encode step competing with YOLO for CUDA compute (NVENC is physically separate silicon on the 4060).
- If FPS becomes GPU-bound anyway, use **adaptive frame skipping**: run YOLO on every 2nd frame and interpolate bboxes for the skipped frame using the Kalman filter from 2.A — this is a compute-time optimization, not really a VRAM one, but it's the cheapest lever if you ever see the pipeline bottlenecked.
- Monitor with `nvidia-smi dmon` during integration testing (Phase 4) rather than assuming — actual TensorRT engine memory varies with input resolution and workspace size settings.

---

## PART 3 — EXECUTION PLAN (Mid-Range / Local Models Only)

### Phase 1 — Data Collection & Model Training

- **Tools:** CVAT or Label Studio for bounding-box annotation; Roboflow (or Albumentations directly) for augmentation pipelines.
- Record footage of the actual BAS experiment tools/objects from the fixed payload camera position, deliberately varying:
  - object orientation (full rotation, since there's no "up")
  - partial occlusion by hands/body
  - objects mid-"float" vs. being actively held
- Train **YOLOv11n** first (fastest iteration, confirms the pipeline works end-to-end); move to **YOLOv11s** only if accuracy on small/similar-looking tools is insufficient — don't default to the larger model.
- Fine-tune from COCO-pretrained weights via `ultralytics` CLI/Python API; track mAP@0.5 per class, paying particular attention to tools that look similar (common failure mode for small custom datasets).
- Export: `.pt → ONNX → TensorRT engine` (fp16) using `trtexec`, validated against the same laptop GPU you'll demo on (TensorRT engines are hardware-specific and don't transfer between GPU models).
- MediaPipe Holistic needs no training — this phase for it is just threshold calibration (grasp distance, visibility cutoffs) against your actual camera's resolution/distance.

### Phase 2 — Vision & FSM Integration

- Define the protocol schema (YAML, as in 1.4) for the specific BAS experiment sequence.
- Implement the Fusion Engine (1.3): hand-region/object IoU, grasp-distance calc, event de-duplication on state change only.
- Build the FSM with `transitions`, wiring in the fault-tolerance features from 2.B (debounce, look-ahead buffer, `PENDING_CONFIRMATION` state) **from the start**, not as an afterthought — retrofitting fault tolerance onto a strict DFA is much harder than designing it in.
- Unit-test the FSM against a **replayed event log** (not live video) first — feed it synthetic/recorded event sequences including deliberately "missed" steps to validate the recovery logic before touching real camera input.

### Phase 3 — Telemetry, Video Streaming & UI

- Implement the JSONL telemetry logger (one line per FSM event + per violation).
- Wire `cv2.VideoWriter` (or the NVENC-backed FFmpeg pipe) for local `.mp4` storage with overlays.
- Stand up the FastAPI MJPEG endpoint (or MediaMTX RTSP) for the IP stream — test on a second device on the same Wi-Fi before the actual demo network.
- Build the Streamlit dashboard (fastest path): live checklist, current step, confidence bar, violation feed, embedded stream.
- Wire the TTS worker thread to the `alert_queue`, test phrasing for both step-confirmation and correction messages (keep alerts short — long TTS strings feel laggy and can queue up awkwardly if steps happen quickly).

### Phase 4 — Optimization

- Convert final YOLO weights to a TensorRT engine on the exact demo laptop; benchmark fp16 vs. INT8 (with calibration images) for speed/accuracy tradeoff.
- Profile the full pipeline under real load (`nvidia-smi dmon`, `cProfile`/`py-spy` for the Python threads) with **all five consumers running simultaneously** (YOLO + MediaPipe + TTS + video write + IP stream) — this is the first point where VRAM/CPU contention issues from Part 2C actually surface, so don't skip testing them together.
- Tune queue sizes and the adaptive frame-skip logic to hit a target FPS (e.g. 15-20 FPS is usually sufficient for this kind of procedural-task monitoring, well below what a jury would notice as "laggy").
- **Forward-compatibility note for the eventual space-grade port:** where practical, prefer **ONNX Runtime** as the inference abstraction over a hard TensorRT dependency where you can (TensorRT engines are locked to the GPU they were built on). This keeps the model layer portable to whatever accelerator the actual space-grade edge hardware uses later (Jetson-class, FPGA, or a custom NPU), while still letting you use TensorRT specifically for the demo laptop.

---

## Relevant References (from your context doc) mapped to phases

- **PREGO / Assembly101** → most directly useful in Phase 2 (FSM design) and as a post-hoc validation method: replay your JSONL telemetry through a PREGO-style expected-vs-actual comparison to catch cases your live FSM's debounce/look-ahead logic missed.
- **100DOH** → useful reference for improving the grasp-state heuristic in 1.3/2.1 beyond simple fingertip distance, if early testing shows too many false grasp detections.
- **Ego-Exo4D** → most relevant as inspiration for the telemetry log *schema* (structured, timestamped action logs) rather than something you'd run directly on this hardware.
- **MMAction2** → optional Phase 4+ stretch goal if you later want true temporal action segmentation instead of the spatial-heuristic approach; not necessary for the hackathon-scope demo.
